from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@db/documents_db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# Модель для хранения истории посещений
class History(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False)
    pacient_id = db.Column(db.Integer, nullable=False)
    hospital_id = db.Column(db.Integer, nullable=False)
    doctor_id = db.Column(db.Integer, nullable=False)
    room = db.Column(db.String(50), nullable=False)
    data = db.Column(db.String(500), nullable=False)

# Получение истории посещений по аккаунту
@app.route('/api/History/Account/<int:id>', methods=['GET'])
def get_history_by_account(id):
    histories = History.query.filter_by(pacient_id=id).all()
    if not histories:
        return jsonify({'message': 'No history found'}), 404

    output = []
    for history in histories:
        output.append({
            'date': history.date,
            'hospitalId': history.hospital_id,
            'doctorId': history.doctor_id,
            'room': history.room,
            'data': history.data
        })
    return jsonify(output), 200

# Получение подробной информации по истории посещения
@app.route('/api/History/<int:id>', methods=['GET'])
def get_history_by_id(id):
    history = History.query.get(id)
    if not history:
        return jsonify({'message': 'No history found'}), 404

    return jsonify({
        'date': history.date,
        'hospitalId': history.hospital_id,
        'doctorId': history.doctor_id,
        'room': history.room,
        'data': history.data
    }), 200

# Создание новой записи в истории
@app.route('/api/History', methods=['POST'])
def create_history():
    data = request.get_json()
    new_history = History(
        date=datetime.fromisoformat(data['date']),
        pacient_id=data['pacientId'],
        hospital_id=data['hospitalId'],
        doctor_id=data['doctorId'],
        room=data['room'],
        data=data['data']
    )
    db.session.add(new_history)
    db.session.commit()
    return jsonify({'message': 'History record created'}), 201

# Обновление существующей записи в истории
@app.route('/api/History/<int:id>', methods=['PUT'])
def update_history(id):
    history = History.query.get(id)
    if not history:
        return jsonify({'message': 'No history found'}), 404

    data = request.get_json()
    history.date = datetime.fromisoformat(data['date'])
    history.pacient_id = data['pacientId']
    history.hospital_id = data['hospitalId']
    history.doctor_id = data['doctorId']
    history.room = data['room']
    history.data = data['data']
    
    db.session.commit()
    return jsonify({'message': 'History record updated'}), 200

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000)
