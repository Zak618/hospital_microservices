from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import jwt
import datetime

app = Flask(__name__)

# Настройки базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@db/hospitals_db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# Модель для больниц
class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    contact_phone = db.Column(db.String(20), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)

# Модель для кабинетов в больнице
class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    hospital = db.relationship('Hospital', backref=db.backref('rooms', lazy=True))

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

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 403

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            if 'Admin' not in data['roles']:
                return jsonify({'message': 'Permission denied'}), 403
        except:
            return jsonify({'message': 'Token is invalid'}), 403

        return f(*args, **kwargs)

    return decorated

# Эндпоинты для работы с больницами

@app.route('/api/Hospitals', methods=['GET'])
@token_required
def get_hospitals():
    from_ = request.args.get('from', 0, type=int)
    count = request.args.get('count', 10, type=int)

    hospitals = Hospital.query.filter_by(is_deleted=False).offset(from_).limit(count).all()
    output = []
    for hospital in hospitals:
        hospital_data = {
            'id': hospital.id,
            'name': hospital.name,
            'address': hospital.address,
            'contact_phone': hospital.contact_phone
        }
        output.append(hospital_data)
    return jsonify(output)

@app.route('/api/Hospitals/<id>', methods=['GET'])
@token_required
def get_hospital_by_id(id):
    hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
    if not hospital:
        return jsonify({'message': 'Hospital not found'}), 404

    hospital_data = {
        'id': hospital.id,
        'name': hospital.name,
        'address': hospital.address,
        'contact_phone': hospital.contact_phone
    }
    return jsonify(hospital_data)

@app.route('/api/Hospitals/<id>/Rooms', methods=['GET'])
@token_required
def get_hospital_rooms(id):
    hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
    if not hospital:
        return jsonify({'message': 'Hospital not found'}), 404

    rooms = Room.query.filter_by(hospital_id=id).all()
    output = []
    for room in rooms:
        room_data = {
            'id': room.id,
            'name': room.name
        }
        output.append(room_data)
    return jsonify(output)

@app.route('/api/Hospitals', methods=['POST'])
@admin_required
def create_hospital():
    data = request.get_json()
    new_hospital = Hospital(
        name=data['name'],
        address=data['address'],
        contact_phone=data['contactPhone']
    )
    db.session.add(new_hospital)
    db.session.commit()

    for room_name in data['rooms']:
        new_room = Room(name=room_name, hospital_id=new_hospital.id)
        db.session.add(new_room)

    db.session.commit()
    return jsonify({'message': 'New hospital created successfully'}), 201

@app.route('/api/Hospitals/<id>', methods=['PUT'])
@admin_required
def update_hospital(id):
    hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
    if not hospital:
        return jsonify({'message': 'Hospital not found'}), 404

    data = request.get_json()
    hospital.name = data['name']
    hospital.address = data['address']
    hospital.contact_phone = data['contactPhone']

    Room.query.filter_by(hospital_id=id).delete()  # Удаляем старые кабинеты
    for room_name in data['rooms']:
        new_room = Room(name=room_name, hospital_id=hospital.id)
        db.session.add(new_room)

    db.session.commit()
    return jsonify({'message': 'Hospital updated successfully'}), 200

@app.route('/api/Hospitals/<id>', methods=['DELETE'])
@admin_required
def soft_delete_hospital(id):
    hospital = Hospital.query.filter_by(id=id, is_deleted=False).first()
    if not hospital:
        return jsonify({'message': 'Hospital not found'}), 404

    hospital.is_deleted = True
    db.session.commit()
    return jsonify({'message': 'Hospital soft deleted successfully'}), 200

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
