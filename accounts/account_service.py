from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps

app = Flask(__name__)

# Настройки базы данных
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://user:password@db/accounts_db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    roles = db.Column(db.String(100), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)  # Флаг мягкого удаления

# Модель токенов для работы с рефреш токенами
class Token(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(500), nullable=False)

# Декоратор для проверки JWT токена
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 403

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except:
            return jsonify({'message': 'Token is invalid'}), 403

        return f(current_user, *args, **kwargs)

    return decorated

# Регистрация нового аккаунта
@app.route('/api/Authentication/SignUp', methods=['POST'])
def signup():
    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(
        first_name=data['firstName'], 
        last_name=data['lastName'], 
        username=data['username'], 
        password=hashed_password, 
        roles="User"
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'User created successfully'}), 201

# Вход пользователя и генерация JWT
@app.route('/api/Authentication/SignIn', methods=['POST'])
def signin():
    data = request.get_json()
    user = User.query.filter_by(username=data['username']).first()
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    access_token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
    }, app.config['SECRET_KEY'])
    
    refresh_token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }, app.config['SECRET_KEY'])
    
    return jsonify({'accessToken': access_token, 'refreshToken': refresh_token})

# Обновление пары токенов
@app.route('/api/Authentication/Refresh', methods=['POST'])
def refresh_token():
    data = request.get_json()
    refresh_token = data['refreshToken']
    
    try:
        decoded = jwt.decode(refresh_token, app.config['SECRET_KEY'], algorithms=["HS256"])
        user = User.query.filter_by(id=decoded['user_id']).first()
        if not user:
            return jsonify({'message': 'User not found'}), 404
        
        new_access_token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }, app.config['SECRET_KEY'])
        
        return jsonify({'accessToken': new_access_token})
    
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Refresh token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid refresh token'}), 401

# Выход из системы (аннулирование токенов)
@app.route('/api/Authentication/SignOut', methods=['PUT'])
@token_required
def signout(current_user):
    return jsonify({'message': 'User signed out'}), 200

# Интроспекция токена
@app.route('/api/Authentication/Validate', methods=['GET'])
def validate_token():
    auth_header = request.headers.get('Authorization')
    
    if not auth_header:
        return jsonify({'message': 'Token is missing'}), 403
    
    try:
        token = auth_header.split(" ")[1]  # Берём часть токена после "Bearer"
        decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        return jsonify({'user_id': decoded['user_id']}), 200
    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token expired'}), 401
    except jwt.InvalidTokenError:
        return jsonify({'message': 'Invalid token'}), 401

# Получение данных о текущем аккаунте
@app.route('/api/Accounts/Me', methods=['GET'])
@token_required
def get_current_user(current_user):
    return jsonify({
        'firstName': current_user.first_name,
        'lastName': current_user.last_name,
        'username': current_user.username,
        'roles': current_user.roles
    }), 200

# Обновление своего аккаунта
@app.route('/api/Accounts/Update', methods=['PUT'])
@token_required
def update_account(current_user):
    data = request.get_json()
    if 'firstName' in data:
        current_user.first_name = data['firstName']
    if 'lastName' in data:
        current_user.last_name = data['lastName']
    if 'password' in data:
        current_user.password = generate_password_hash(data['password'], method='sha256')

    db.session.commit()
    return jsonify({'message': 'Account updated successfully'}), 200

# Получение списка всех аккаунтов (только для администраторов)
@app.route('/api/Accounts', methods=['GET'])
@token_required
def get_all_accounts(current_user):
    if 'Admin' not in current_user.roles:
        return jsonify({'message': 'Permission denied'}), 403

    from_ = request.args.get('from', 0, type=int)
    count = request.args.get('count', 10, type=int)

    users = User.query.filter_by(is_deleted=False).offset(from_).limit(count).all()
    output = []
    for user in users:
        user_data = {
            'id': user.id,
            'firstName': user.first_name,
            'lastName': user.last_name,
            'username': user.username,
            'roles': user.roles
        }
        output.append(user_data)
    return jsonify(output)

# Создание нового аккаунта администратором
@app.route('/api/Accounts', methods=['POST'])
@token_required
def create_account(current_user):
    if 'Admin' not in current_user.roles:
        return jsonify({'message': 'Permission denied'}), 403

    data = request.get_json()
    hashed_password = generate_password_hash(data['password'], method='sha256')
    new_user = User(
        first_name=data['firstName'], 
        last_name=data['lastName'], 
        username=data['username'], 
        password=hashed_password, 
        roles=",".join(data['roles'])  # Сохраняем роли через запятую
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'New account created successfully'}), 201

# Изменение аккаунта администратором по ID
@app.route('/api/Accounts/<id>', methods=['PUT'])
@token_required
def update_account_by_id(current_user, id):
    if 'Admin' not in current_user.roles:
        return jsonify({'message': 'Permission denied'}), 403

    user = User.query.filter_by(id=id, is_deleted=False).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.get_json()
    if 'firstName' in data:
        user.first_name = data['firstName']
    if 'lastName' in data:
        user.last_name = data['lastName']
    if 'password' in data:
        user.password = generate_password_hash(data['password'], method='sha256')
    if 'roles' in data:
        user.roles = ",".join(data['roles'])

    db.session.commit()
    return jsonify({'message': 'User updated successfully'})

# Мягкое удаление аккаунта администратором
@app.route('/api/Accounts/<id>', methods=['DELETE'])
@token_required
def soft_delete_account(current_user, id):
    if 'Admin' not in current_user.roles:
        return jsonify({'message': 'Permission denied'}), 403

    user = User.query.filter_by(id=id, is_deleted=False).first()
    if not user:
        return jsonify({'message': 'User not found'}), 404

    user.is_deleted = True
    db.session.commit()
    return jsonify({'message': 'User soft deleted successfully'}), 200

# Получение списка докторов (авторизованные пользователи)
@app.route('/api/Doctors', methods=['GET'])
@token_required
def get_doctors(current_user):
    name_filter = request.args.get('nameFilter', '', type=str)
    from_ = request.args.get('from', 0, type=int)
    count = request.args.get('count', 10, type=int)

    doctors = User.query.filter(User.roles.contains('Doctor'), User.first_name.like(f'%{name_filter}%')).offset(from_).limit(count).all()

    output = []
    for doctor in doctors:
        doctor_data = {
            'id': doctor.id,
            'firstName': doctor.first_name,
            'lastName': doctor.last_name,
            'username': doctor.username,
        }
        output.append(doctor_data)
    return jsonify(output)

# Получение информации о докторе по ID
@app.route('/api/Doctors/<id>', methods=['GET'])
@token_required
def get_doctor_by_id(current_user, id):
    doctor = User.query.filter_by(id=id, roles='Doctor', is_deleted=False).first()
    if not doctor:
        return jsonify({'message': 'Doctor not found'}), 404

    doctor_data = {
        'id': doctor.id,
        'firstName': doctor.first_name,
        'lastName': doctor.last_name,
        'username': doctor.username,
    }
    return jsonify(doctor_data)

if __name__ == '__main__':
    db.create_all()
    app.run(host='0.0.0.0', port=5001, debug=True)
