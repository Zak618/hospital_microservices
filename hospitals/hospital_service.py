from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api, Resource, fields, Namespace
from functools import wraps
import jwt
import datetime
import os

app = Flask(__name__)

# Настройки базы данных
db_user = os.environ.get('POSTGRES_USER', 'user')
db_password = os.environ.get('POSTGRES_PASSWORD', 'password')
db_host = os.environ.get('POSTGRES_HOST', 'db')
db_port = os.environ.get('POSTGRES_PORT', '5432')
db_name = os.environ.get('POSTGRES_DB', 'hospitals_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # Отключение предупреждения
app.config['SECRET_KEY'] = 'your_secret_key'

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
    title="Hospitals API", 
    description="API для управления больницами и кабинетами",
    version="1.0",
    authorizations=authorizations,
    security='Bearer Auth'
)

# Создание Namespace для больниц
ns = Namespace('Hospitals', description='Операции с больницами и кабинетами', path='/api/Hospitals')

api.add_namespace(ns)

# Модель для кабинетов
room_model = api.model('Room', {
    'id': fields.Integer(readOnly=True, description='Уникальный идентификатор кабинета'),
    'name': fields.String(required=True, description='Название кабинета')
})

# Модель для больниц
hospital_model = api.model('Hospital', {
    'id': fields.Integer(readOnly=True, description='Уникальный идентификатор больницы'),
    'name': fields.String(required=True, description='Название больницы'),
    'address': fields.String(required=True, description='Адрес больницы'),
    'contactPhone': fields.String(required=True, description='Контактный телефон'),
    'rooms': fields.List(fields.String, description='Список кабинетов')
})

# Модель для обновления больницы (может отличаться от создания)
hospital_update_model = api.model('HospitalUpdate', {
    'name': fields.String(required=True, description='Название больницы'),
    'address': fields.String(required=True, description='Адрес больницы'),
    'contactPhone': fields.String(required=True, description='Контактный телефон'),
    'rooms': fields.List(fields.String, description='Список кабинетов')
})

# Модель для ответа с токенами (при необходимости)
token_model = api.model('Token', {
    'accessToken': fields.String(description='Токен доступа'),
    'refreshToken': fields.String(description='Токен обновления')
})

# Модель для сообщения
message_model = api.model('Message', {
    'message': fields.String(description='Сообщение')
})

# Модель для ошибок
error_model = api.model('Error', {
    'message': fields.String(description='Сообщение об ошибке')
})

# Декоратор для проверки JWT токена
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            api.abort(403, 'Token is missing')
        
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data  # Можно расширить для получения информации о пользователе из базы данных
        except IndexError:
            api.abort(403, 'Token is invalid')
        except jwt.ExpiredSignatureError:
            api.abort(401, 'Token expired')
        except jwt.InvalidTokenError:
            api.abort(403, 'Token is invalid')
        
        return f(*args, **kwargs)
    
    return decorated

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            api.abort(403, 'Token is missing')
        
        try:
            token = auth_header.split(" ")[1]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            if 'Admin' not in data.get('roles', []):
                api.abort(403, 'Permission denied')
        except IndexError:
            api.abort(403, 'Token is invalid')
        except jwt.ExpiredSignatureError:
            api.abort(401, 'Token expired')
        except jwt.InvalidTokenError:
            api.abort(403, 'Token is invalid')
        
        return f(*args, **kwargs)
    
    return decorated

# Модель данных для больницы в базе данных
class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    rooms = db.relationship('Room', backref='hospital', lazy=True, cascade="all, delete-orphan")

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)

# Эндпоинты для работы с больницами

@ns.route('')
class HospitalList(Resource):
    @ns.doc('get_hospitals')
    @ns.expect(api.parser().add_argument('from', type=int, location='args', default=0, help='Смещение'))
    @ns.expect(api.parser().add_argument('count', type=int, location='args', default=10, help='Количество записей'))
    @ns.marshal_list_with(hospital_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(401, 'Token expired', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def get(self):
        """Получить список больниц"""
        parser = api.parser()
        parser.add_argument('from', type=int, location='args', default=0, help='Смещение')
        parser.add_argument('count', type=int, location='args', default=10, help='Количество записей')
        args = parser.parse_args()
        from_ = args.get('from', 0)
        count = args.get('count', 10)

        hospitals = Hospital.query.filter_by(is_deleted=False).offset(from_).limit(count).all()
        output = []
        for hospital in hospitals:
            hospital_data = {
                'id': hospital.id,
                'name': hospital.name,
                'address': hospital.address,
                'contactPhone': hospital.contact_phone,
                'rooms': [room.name for room in hospital.rooms]
            }
            output.append(hospital_data)
        return output, 200

    @ns.doc('create_hospital')
    @ns.expect(hospital_model, validate=True)
    @ns.marshal_with(message_model, code=201)
    @ns.response(403, 'Permission denied', model=error_model)
    @admin_required
    def post(self):
        """Создать новую больницу"""
        data = request.get_json()
        new_hospital = Hospital(
            name=data['name'],
            address=data['address'],
            contact_phone=data['contactPhone']
        )
        db.session.add(new_hospital)
        db.session.commit()

        for room_name in data.get('rooms', []):
            new_room = Room(name=room_name, hospital_id=new_hospital.id)
            db.session.add(new_room)

        db.session.commit()
        return {'message': 'New hospital created successfully'}, 201

@ns.route('/<int:id>')
@ns.response(404, 'Hospital not found', model=error_model)
@ns.param('id', 'Уникальный идентификатор больницы')
class HospitalResource(Resource):
    @ns.doc('get_hospital_by_id')
    @ns.marshal_with(hospital_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(401, 'Token expired', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def get(self, id):
        """Получить больницу по ID"""
        hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
        if not hospital:
            api.abort(404, 'Hospital not found')

        hospital_data = {
            'id': hospital.id,
            'name': hospital.name,
            'address': hospital.address,
            'contactPhone': hospital.contact_phone,
            'rooms': [room.name for room in hospital.rooms]
        }
        return hospital_data, 200

    @ns.doc('update_hospital')
    @ns.expect(hospital_update_model, validate=True)
    @ns.marshal_with(message_model)
    @ns.response(403, 'Permission denied', model=error_model)
    @admin_required
    def put(self, id):
        """Обновить информацию о больнице"""
        hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
        if not hospital:
            api.abort(404, 'Hospital not found')

        data = request.get_json()
        hospital.name = data['name']
        hospital.address = data['address']
        hospital.contact_phone = data['contactPhone']

        # Удаляем старые кабинеты
        Room.query.filter_by(hospital_id=id).delete()

        # Добавляем новые кабинеты
        for room_name in data.get('rooms', []):
            new_room = Room(name=room_name, hospital_id=hospital.id)
            db.session.add(new_room)

        db.session.commit()
        return {'message': 'Hospital updated successfully'}, 200

    @ns.doc('soft_delete_hospital')
    @ns.marshal_with(message_model)
    @ns.response(403, 'Permission denied', model=error_model)
    @admin_required
    def delete(self, id):
        """Мягко удалить больницу"""
        hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
        if not hospital:
            api.abort(404, 'Hospital not found')

        hospital.is_deleted = True
        db.session.commit()
        return {'message': 'Hospital soft deleted successfully'}, 200

@ns.route('/<int:id>/Rooms')
@ns.response(404, 'Hospital not found', model=error_model)
@ns.param('id', 'Уникальный идентификатор больницы')
class HospitalRooms(Resource):
    @ns.doc('get_hospital_rooms')
    @ns.marshal_list_with(room_model)
    @ns.response(403, 'Token is missing', model=error_model)
    @ns.response(401, 'Token expired', model=error_model)
    @ns.response(403, 'Token is invalid', model=error_model)
    @token_required
    def get(self, id):
        """Получить список кабинетов в больнице"""
        hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
        if not hospital:
            api.abort(404, 'Hospital not found')

        rooms = Room.query.filter_by(hospital_id=id).all()
        output = []
        for room in rooms:
            room_data = {
                'id': room.id,
                'name': room.name
            }
            output.append(room_data)
        return output, 200

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
