from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api, Resource, fields
from datetime import datetime
import jwt

app = Flask(__name__)
api = Api(app, title="Documents API", description="API for managing medical visit history", version="1.0")
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

# Swagger модели для истории посещений
history_model = api.model('History', {
    'date': fields.String(required=True, description='Date of the visit in ISO format'),
    'pacientId': fields.Integer(required=True, description='Patient ID'),
    'hospitalId': fields.Integer(required=True, description='Hospital ID'),
    'doctorId': fields.Integer(required=True, description='Doctor ID'),
    'room': fields.String(required=True, description='Room number'),
    'data': fields.String(required=True, description='Details about the visit')
})

# Получение истории посещений по аккаунту
@api.route('/api/History/Account/<int:id>')
class GetHistoryByAccount(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No history found')
    def get(self, id):
        """Get medical visit history by patient ID"""
        histories = History.query.filter_by(pacient_id=id).all()
        if not histories:
            return {'message': 'No history found'}, 404

        output = []
        for history in histories:
            output.append({
                'date': history.date.isoformat(),
                'hospitalId': history.hospital_id,
                'doctorId': history.doctor_id,
                'room': history.room,
                'data': history.data
            })
        return output, 200

# Получение подробной информации по истории посещения
@api.route('/api/History/<int:id>')
class GetHistoryById(Resource):
    @api.response(200, 'Success')
    @api.response(404, 'No history found')
    def get(self, id):
        """Get visit history details by history ID"""
        history = History.query.get(id)
        if not history:
            return {'message': 'No history found'}, 404

        return {
            'date': history.date.isoformat(),
            'hospitalId': history.hospital_id,
            'doctorId': history.doctor_id,
            'room': history.room,
            'data': history.data
        }, 200

# Создание новой записи в истории
@api.route('/api/History')
class CreateHistory(Resource):
    @api.expect(history_model)
    @api.response(201, 'History record created')
    def post(self):
        """Create a new history record"""
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
        return {'message': 'History record created'}, 201


# Обновление существующей записи в истории
@api.route('/api/History/<int:id>')
class UpdateHistory(Resource):
    @api.expect(history_model)
    @api.response(200, 'History record updated')
    @api.response(404, 'No history found')
    def put(self, id):
        """Update an existing history record by history ID"""
        history = History.query.get(id)
        if not history:
            return {'message': 'No history found'}, 404

        data = request.get_json()
        history.date = datetime.fromisoformat(data['date'])
        history.pacient_id = data['pacientId']
        history.hospital_id = data['hospitalId']
        history.doctor_id = data['doctorId']
        history.room = data['room']
        history.data = data['data']
        
        db.session.commit()
        return {'message': 'History record updated'}, 200

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
