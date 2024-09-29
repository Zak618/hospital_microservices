from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import jwt
import datetime
from functools import wraps
import requests  # Для взаимодействия с другими микросервисами

app = Flask(__name__)

# Настройки базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@db/timetable_db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# Модель расписания
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
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 403

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except:
            return jsonify({'message': 'Token is invalid'}), 403

        return f(*args, **kwargs)
    return decorated

# Проверка, существует ли врач
def doctor_exists(doctor_id):
    response = requests.get(f'http://hospital-service/api/Hospitals/Doctor/{doctor_id}')
    return response.status_code == 200

# Проверка, существует ли комната
def room_exists(hospital_id, room):
    response = requests.get(f'http://hospital-service/api/Hospitals/{hospital_id}/Room/{room}')
    return response.status_code == 200

# Создание записи в расписании
@app.route('/api/Timetable', methods=['POST'])
@token_required
def create_timetable():
    data = request.get_json()

    # Валидация существования врача и комнаты
    if not doctor_exists(data['doctorId']):
        return jsonify({'message': 'Doctor not found'}), 404

    if not room_exists(data['hospitalId'], data['room']):
        return jsonify({'message': 'Room not found'}), 404

    # Создание расписания
    new_entry = Timetable(
        hospital_id=data['hospitalId'],
        doctor_id=data['doctorId'],
        start_time=datetime.datetime.fromisoformat(data['from']),
        end_time=datetime.datetime.fromisoformat(data['to']),
        room=data['room']
    )
    
    db.session.add(new_entry)
    db.session.commit()

    return jsonify({'message': 'Timetable entry created successfully'}), 201

# Обновление записи в расписании
@app.route('/api/Timetable/<int:id>', methods=['PUT'])
@token_required
def update_timetable(id):
    timetable = Timetable.query.get(id)
    if not timetable:
        return jsonify({'message': 'Timetable not found'}), 404

    data = request.get_json()

    if 'from' in data:
        timetable.start_time = datetime.datetime.fromisoformat(data['from'])
    if 'to' in data:
        timetable.end_time = datetime.datetime.fromisoformat(data['to'])
    if 'room' in data and room_exists(timetable.hospital_id, data['room']):
        timetable.room = data['room']

    db.session.commit()
    return jsonify({'message': 'Timetable updated successfully'}), 200

# Удаление записи в расписании
@app.route('/api/Timetable/<int:id>', methods=['DELETE'])
@token_required
def delete_timetable(id):
    timetable = Timetable.query.get(id)
    if not timetable:
        return jsonify({'message': 'Timetable not found'}), 404

    db.session.delete(timetable)
    db.session.commit()
    return jsonify({'message': 'Timetable entry deleted successfully'}), 200

# Получение расписания больницы
@app.route('/api/Timetable/Hospital/<int:hospital_id>', methods=['GET'])
@token_required
def get_hospital_timetable(hospital_id):
    from_date = request.args.get('from')
    to_date = request.args.get('to')

    timetables = Timetable.query.filter(
        Timetable.hospital_id == hospital_id,
        Timetable.start_time >= from_date,
        Timetable.end_time <= to_date
    ).all()

    return jsonify([{
        'id': t.id,
        'doctor_id': t.doctor_id,
        'start_time': t.start_time.isoformat(),
        'end_time': t.end_time.isoformat(),
        'room': t.room
    } for t in timetables])

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
