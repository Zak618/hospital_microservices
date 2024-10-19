from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api, Resource, fields, Namespace
from functools import wraps
import jwt
import datetime
import os
import requests  # Для взаимодействия с другими микросервисами
from dateutil import parser  # Для парсинга ISO дат с 'Z'
import logging

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

# Настройки базы данных через переменные окружения
db_user = os.environ.get('POSTGRES_USER', 'user')
db_password = os.environ.get('POSTGRES_PASSWORD', 'password')
db_host = os.environ.get('POSTGRES_HOST', 'db')
db_port = os.environ.get('POSTGRES_PORT', '5432')
db_name = os.environ.get('POSTGRES_DB', 'timetable_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключаем предупреждение
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key')  # Используйте переменные окружения для секретных ключей

db = SQLAlchemy(app)

# Инициализация Flask-RESTx Api
authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization',
        'description': 'JWT Authorization header using the Bearer scheme. Example: "Authorization: Bearer <token>"'
    }
}

api = Api(
    app, 
    title="Timetable API", 
    description="API для управления расписаниями",
    version="1.0",
    authorizations=authorizations,
    security='Bearer Auth'
)

# Создание Namespace для расписаний
ns = Namespace('Timetables', description='Операции с расписаниями', path='/api/Timetable')

api.add_namespace(ns)

# Модель данных для расписания
timetable_model = api.model('Timetable', {
    'id': fields.Integer(readOnly=True, description='Уникальный идентификатор расписания'),
    'hospitalId': fields.Integer(required=True, description='ID больницы'),
    'doctorId': fields.Integer(required=True, description='ID врача'),
    'from': fields.DateTime(required=True, description='Время начала'),
    'to': fields.DateTime(required=True, description='Время окончания'),
    'room': fields.String(required=True, description='Кабинет')
})

# Модель данных для обновления расписания
timetable_update_model = api.model('TimetableUpdate', {
    'from': fields.DateTime(description='Время начала'),
    'to': fields.DateTime(description='Время окончания'),
    'room': fields.String(description='Кабинет')
})

# Модель ответа с сообщением
message_model = api.model('Message', {
    'message': fields.String(description='Сообщение')
})

# Модель ошибки
error_model = api.model('Error', {
    'message': fields.String(description='Сообщение об ошибке')
})

# Модель данных для расписания в базе данных
class Timetable(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, nullable=False)
    doctor_id = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    room = db.Column(db.String(50), nullable=False)

# Декоратор для проверки JWT токена
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            logging.debug("Authorization header is missing.")
            api.abort(403, 'Token is missing', status='fail', statusCode="403")
        
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            logging.debug(f"Token decoded successfully: {data}")
        except IndexError:
            logging.debug("Authorization header format is invalid.")
            api.abort(403, 'Token is invalid', status='fail', statusCode="403")
        except jwt.ExpiredSignatureError:
            logging.debug("Token has expired.")
            api.abort(401, 'Token expired', status='fail', statusCode="401")
        except jwt.InvalidTokenError:
            logging.debug("Token is invalid.")
            api.abort(403, 'Token is invalid', status='fail', statusCode="403")
        
        return f(*args, **kwargs)
    
    return decorated

# Проверка, существует ли врач
def doctor_exists(doctor_id):
    try:
        logging.debug(f"Checking existence of doctor with ID: {doctor_id}")
        
        # Здесь необходимо использовать действительный токен для межсервисных запросов
        # Например, сервисный токен или другой механизм аутентификации
        service_access_token = 'your_service_access_token'  # Замените на реальный токен
        
        headers = {
            'Authorization': f'Bearer {service_access_token}'
        }
        
        response = requests.get(f'http://localhost:5001/api/Accounts/{doctor_id}', headers=headers)
        logging.debug(f"Received response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            user_data = response.json()
            roles = user_data.get('roles', [])
            
            # Если roles хранится как строка, разделённая запятыми
            if isinstance(roles, str):
                roles = roles.split(',')
            
            logging.debug(f"User roles: {roles}")
            return 'Doctor' in roles
        elif response.status_code == 404:
            logging.debug(f"Doctor with ID {doctor_id} not found.")
            return False
        else:
            logging.error(f"Unexpected response from Accounts Service: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to Accounts Service: {e}")
        return False

# Проверка, существует ли комната
def room_exists(hospital_id, room):
    try:
        logging.debug(f"Checking existence of room '{room}' in hospital ID: {hospital_id}")
        
        # Здесь необходимо использовать действительный токен для межсервисных запросов
        # Например, сервисный токен или другой механизм аутентификации
        service_access_token = 'your_service_access_token'  # Замените на реальный токен
        
        headers = {
            'Authorization': f'Bearer {service_access_token}'
        }
        
        response = requests.get(f'http://localhost:5002/api/Hospitals/{hospital_id}/Rooms', headers=headers)
        logging.debug(f"Received response: {response.status_code} - {response.text}")
        
        if response.status_code == 200:
            rooms = response.json()
            exists = any(r['name'] == room for r in rooms)
            logging.debug(f"Room '{room}' exists: {exists}")
            return exists
        elif response.status_code == 404:
            logging.debug(f"Hospital with ID {hospital_id} not found.")
            return False
        else:
            logging.error(f"Unexpected response from Hospital Service: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to Hospital Service: {e}")
        return False

# Эндпоинты для работы с расписаниями

@ns.route('')
class TimetableList(Resource):
    @ns.doc('get_timetables')
    @ns.expect(api.parser().add_argument('hospitalId', type=int, location='args', required=True, help='ID больницы'))
    @ns.expect(api.parser().add_argument('fromDate', type=str, location='args', required=True, help='Дата начала в формате YYYY-MM-DD'))
    @ns.expect(api.parser().add_argument('toDate', type=str, location='args', required=True, help='Дата окончания в формате YYYY-MM-DD'))
    @ns.marshal_list_with(timetable_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(401, 'Token expired', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def get(self):
        """Получить расписание больницы за указанный период"""
        parser = api.parser()
        parser.add_argument('hospitalId', type=int, location='args', required=True, help='ID больницы')
        parser.add_argument('fromDate', type=str, location='args', required=True, help='Дата начала в формате YYYY-MM-DD')
        parser.add_argument('toDate', type=str, location='args', required=True, help='Дата окончания в формате YYYY-MM-DD')
        args = parser.parse_args()
        
        hospital_id = args.get('hospitalId')
        from_date_str = args.get('fromDate')
        to_date_str = args.get('toDate')
        
        try:
            from_date = datetime.datetime.strptime(from_date_str, "%Y-%m-%d")
            to_date = datetime.datetime.strptime(to_date_str, "%Y-%m-%d")
        except ValueError:
            api.abort(400, 'Invalid date format. Use YYYY-MM-DD', status='fail', statusCode="400")
        
        timetables = Timetable.query.filter(
            Timetable.hospital_id == hospital_id,
            Timetable.start_time >= from_date,
            Timetable.end_time <= to_date
        ).all()
        
        output = []
        for t in timetables:
            timetable_data = {
                'id': t.id,
                'hospitalId': t.hospital_id,
                'doctorId': t.doctor_id,
                'from': t.start_time.isoformat(),
                'to': t.end_time.isoformat(),
                'room': t.room
            }
            output.append(timetable_data)
        
        return output, 200
    
    @ns.doc('create_timetable')
    @ns.expect(timetable_model, validate=True)
    @ns.marshal_with(message_model, code=201)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @ns.response(404, 'Doctor not found', model=error_model)
    @ns.response(404, 'Room not found', model=error_model)
    @token_required
    def post(self):
        """Создать запись в расписании"""
        data = request.get_json()
        logging.debug(f"Received data for timetable creation: {data}")
        
        # Валидация существования врача и комнаты
        if not doctor_exists(data['doctorId']):
            api.abort(404, 'Doctor not found', status='fail', statusCode="404")
        
        if not room_exists(data['hospitalId'], data['room']):
            api.abort(404, 'Room not found', status='fail', statusCode="404")
        
        # Создание расписания
        try:
            start_time = parser.isoparse(data['from'])
            end_time = parser.isoparse(data['to'])
            logging.debug(f"Parsed start_time: {start_time}, end_time: {end_time}")
        except ValueError:
            api.abort(400, 'Invalid datetime format. Use ISO format.', status='fail', statusCode="400")
        
        new_entry = Timetable(
            hospital_id=data['hospitalId'],
            doctor_id=data['doctorId'],
            start_time=start_time,
            end_time=end_time,
            room=data['room']
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        logging.debug(f"Timetable entry created with ID: {new_entry.id}")
        return {'message': 'Timetable entry created successfully'}, 201

@ns.route('/<int:id>')
@ns.param('id', 'Уникальный идентификатор расписания')
class TimetableResource(Resource):
    @ns.doc('update_timetable')
    @ns.expect(timetable_update_model, validate=True)
    @ns.marshal_with(message_model)
    @ns.response(404, 'Timetable not found', model=error_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def put(self, id):
        """Обновить запись в расписании"""
        timetable = Timetable.query.get(id)
        if not timetable:
            api.abort(404, 'Timetable not found', status='fail', statusCode="404")
        
        data = request.get_json()
        logging.debug(f"Received data for timetable update: {data}")
        
        if 'from' in data:
            try:
                timetable.start_time = parser.isoparse(data['from'])
                logging.debug(f"Updated start_time: {timetable.start_time}")
            except ValueError:
                api.abort(400, 'Invalid from datetime format. Use ISO format.', status='fail', statusCode="400")
        if 'to' in data:
            try:
                timetable.end_time = parser.isoparse(data['to'])
                logging.debug(f"Updated end_time: {timetable.end_time}")
            except ValueError:
                api.abort(400, 'Invalid to datetime format. Use ISO format.', status='fail', statusCode="400")
        if 'room' in data:
            if room_exists(timetable.hospital_id, data['room']):
                timetable.room = data['room']
                logging.debug(f"Updated room: {timetable.room}")
            else:
                api.abort(404, 'Room not found', status='fail', statusCode="404")
        
        db.session.commit()
        logging.debug(f"Timetable entry with ID {id} updated successfully.")
        return {'message': 'Timetable updated successfully'}, 200
    
    @ns.doc('delete_timetable')
    @ns.marshal_with(message_model)
    @ns.response(404, 'Timetable not found', model=error_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def delete(self, id):
        """Удалить запись в расписании"""
        timetable = Timetable.query.get(id)
        if not timetable:
            api.abort(404, 'Timetable not found', status='fail', statusCode="404")
        
        db.session.delete(timetable)
        db.session.commit()
        logging.debug(f"Timetable entry with ID {id} deleted successfully.")
        return {'message': 'Timetable entry deleted successfully'}, 200

@ns.route('/Hospital/<int:hospital_id>')
@ns.param('hospital_id', 'Уникальный идентификатор больницы')
class HospitalTimetable(Resource):
    @ns.doc('get_hospital_timetable')
    @ns.expect(api.parser().add_argument('fromDate', type=str, location='args', required=True, help='Дата начала в формате YYYY-MM-DD'))
    @ns.expect(api.parser().add_argument('toDate', type=str, location='args', required=True, help='Дата окончания в формате YYYY-MM-DD'))
    @ns.marshal_list_with(timetable_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(401, 'Token expired', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def get(self, hospital_id):
        """Получить расписание больницы за указанный период"""
        parser = api.parser()
        parser.add_argument('fromDate', type=str, location='args', required=True, help='Дата начала в формате YYYY-MM-DD')
        parser.add_argument('toDate', type=str, location='args', required=True, help='Дата окончания в формате YYYY-MM-DD')
        args = parser.parse_args()
        
        from_date_str = args.get('fromDate')
        to_date_str = args.get('toDate')
        
        try:
            from_date = datetime.datetime.strptime(from_date_str, "%Y-%m-%d")
            to_date = datetime.datetime.strptime(to_date_str, "%Y-%m-%d")
        except ValueError:
            api.abort(400, 'Invalid date format. Use YYYY-MM-DD', status='fail', statusCode="400")
        
        timetables = Timetable.query.filter(
            Timetable.hospital_id == hospital_id,
            Timetable.start_time >= from_date,
            Timetable.end_time <= to_date
        ).all()
        
        output = []
        for t in timetables:
            timetable_data = {
                'id': t.id,
                'hospitalId': t.hospital_id,
                'doctorId': t.doctor_id,
                'from': t.start_time.isoformat(),
                'to': t.end_time.isoformat(),
                'room': t.room
            }
            output.append(timetable_data)
        
        return output, 200

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
