from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_restx import Api, Resource, fields
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
import os
import psycopg2

app = Flask(__name__)

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}

api = Api(
    app, 
    title="Accounts API", 
    description="API for user management", 
    version="1.0",
    authorizations=authorizations,
    security='Bearer Auth'
)

# Настройки базы данных
db_user = os.environ.get('POSTGRES_USER', 'user')
db_password = os.environ.get('POSTGRES_PASSWORD', 'password')
db_host = os.environ.get('POSTGRES_HOST', 'db')
db_port = os.environ.get('POSTGRES_PORT', '5432')
db_name = os.environ.get('POSTGRES_DB', 'accounts_db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

# Модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    roles = db.Column(db.String(100), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)  # Флаг мягкого удаления

# Swagger модели для User и Login
user_model = api.model('User', {
    'firstName': fields.String(required=True, description='First name of the user'),
    'lastName': fields.String(required=True, description='Last name of the user'),
    'username': fields.String(required=True, description='Unique username'),
    'password': fields.String(required=True, description='Password of the user'),
    'roles': fields.List(fields.String, description='Roles of the user')  # Добавлено для роли
})

login_model = api.model('Login', {
    'username': fields.String(required=True, description='Username'),
    'password': fields.String(required=True, description='Password'),
})

try:
    conn = psycopg2.connect(
        dbname=db_name,
        user=db_user,
        password=db_password,
        host=db_host,
        port=db_port
    )
    cursor = conn.cursor()

    # Список пользователей для добавления
    initial_users = [
        {
            'first_name': 'Admin',
            'last_name': 'User',
            'username': 'admin',
            'password': 'admin',
            'roles': 'Admin'
        },
        {
            'first_name': 'Manager',
            'last_name': 'User',
            'username': 'manager',
            'password': 'manager',
            'roles': 'Manager'
        },
        {
            'first_name': 'Doctor',
            'last_name': 'Who',
            'username': 'doctor',
            'password': 'doctor',
            'roles': 'Doctor'
        },
        {
            'first_name': 'User',
            'last_name': 'User',
            'username': 'user',
            'password': 'user',
            'roles': 'User'
        },
    ]

    for user in initial_users:
        hashed_password = generate_password_hash(user['password'])  # Используем Werkzeug для хеширования
        cursor.execute("""
            INSERT INTO "user" (first_name, last_name, username, password, roles)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING;
        """, (user['first_name'], user['last_name'], user['username'], hashed_password, user['roles']))

    conn.commit()
    print("Users have been added successfully.")

except Exception as e:
    print(f"An error occurred: {e}")
finally:
    if cursor:
        cursor.close()
    if conn:
        conn.close()

# Декоратор для проверки JWT токена
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return {'message': 'Token is invalid'}, 403
        if not token:
            return {'message': 'Token is missing'}, 403

        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = User.query.filter_by(id=data['user_id']).first()
        except jwt.ExpiredSignatureError:
            return {'message': 'Token expired'}, 401
        except jwt.InvalidTokenError:
            return {'message': 'Token is invalid'}, 403

        return f(*args, **kwargs, current_user=current_user)

    return decorated

# Функция для создания начальных пользователей
def create_initial_users():
    if not User.query.first():
        initial_users = [
            {
                'first_name': 'Admin',
                'last_name': 'User',
                'username': 'admin',
                'password': 'admin',
                'roles': 'Admin'
            },
            {
                'first_name': 'Doctor',
                'last_name': 'Who',
                'username': 'doctor',
                'password': 'doctor',
                'roles': 'Doctor'
            },
            {
                'first_name': 'User',
                'last_name': 'Normal',
                'username': 'user',
                'password': 'user',
                'roles': 'User'
            },
        ]
        for user_data in initial_users:
            hashed_password = generate_password_hash(user_data['password'])
            new_user = User(
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                username=user_data['username'],
                password=hashed_password,
                roles=user_data['roles']
            )
            db.session.add(new_user)
        db.session.commit()

# Регистрация нового аккаунта
@api.route('/api/Authentication/SignUp')
class SignUp(Resource):
    @api.expect(user_model)
    @api.response(201, 'User created successfully')
    def post(self):
        """Sign up a new user"""
        data = request.get_json()
        hashed_password = generate_password_hash(data['password'])
        new_user = User(
            first_name=data['firstName'], 
            last_name=data['lastName'], 
            username=data['username'], 
            password=hashed_password, 
            roles="User"
        )
        db.session.add(new_user)
        db.session.commit()
        return {'message': 'User created successfully'}, 201

# Вход пользователя и генерация JWT
@api.route('/api/Authentication/SignIn')
class SignIn(Resource):
    @api.expect(login_model)
    @api.response(200, 'Success')
    @api.response(401, 'Invalid credentials')
    def post(self):
        """Sign in a user and get JWT"""
        data = request.get_json()
        user = User.query.filter_by(username=data['username']).first()
        if not user or not check_password_hash(user.password, data['password']):
            return {'message': 'Invalid credentials'}, 401
        
        access_token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }, app.config['SECRET_KEY'])
        
        refresh_token = jwt.encode({
            'user_id': user.id,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
        }, app.config['SECRET_KEY'])
        
        return {'accessToken': access_token, 'refreshToken': refresh_token}, 200

# Обновление пары токенов
@api.route('/api/Authentication/Refresh')
class RefreshToken(Resource):
    @api.response(200, 'Token refreshed successfully')
    @api.response(401, 'Invalid or expired refresh token')
    def post(self):
        """Refresh JWT token"""
        data = request.get_json()
        refresh_token = data['refreshToken']
        
        try:
            decoded = jwt.decode(refresh_token, app.config['SECRET_KEY'], algorithms=["HS256"])
            user = User.query.filter_by(id=decoded['user_id']).first()
            if not user:
                return {'message': 'User not found'}, 404
            
            new_access_token = jwt.encode({
                'user_id': user.id,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            }, app.config['SECRET_KEY'])
            
            return {'accessToken': new_access_token}, 200
        
        except jwt.ExpiredSignatureError:
            return {'message': 'Refresh token expired'}, 401
        except jwt.InvalidTokenError:
            return {'message': 'Invalid refresh token'}, 401

# Выход из системы (аннулирование токенов)
@api.route('/api/Authentication/SignOut')
class SignOut(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'User signed out')
    def put(self, current_user):
        """Sign out a user"""
        return {'message': 'User signed out'}, 200

# Интроспекция токена
@api.route('/api/Authentication/Validate')
class ValidateToken(Resource):
    @api.doc(security='Bearer Auth')
    @api.response(200, 'Valid token')
    @api.response(401, 'Invalid token')
    @api.response(403, 'Token is missing')
    def get(self):
        """Validate JWT token"""
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return {'message': 'Token is missing'}, 403
        
        try:
            token = auth_header.split(" ")[1]  # Берём часть токена после "Bearer"
            decoded = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            return {'user_id': decoded['user_id']}, 200
        except jwt.ExpiredSignatureError:
            return {'message': 'Token expired'}, 401
        except jwt.InvalidTokenError:
            return {'message': 'Invalid token'}, 401

# Получение данных о текущем аккаунте
@api.route('/api/Accounts/Me')
class GetCurrentUser(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'Success')
    def get(self, current_user):
        """Get current logged-in user information"""
        return {
            'firstName': current_user.first_name,
            'lastName': current_user.last_name,
            'username': current_user.username,
            'roles': current_user.roles
        }, 200

# Обновление своего аккаунта
@api.route('/api/Accounts/Update')
class UpdateAccount(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.expect(user_model)
    @api.response(200, 'Account updated successfully')
    def put(self, current_user):
        """Update current user account"""
        data = request.get_json()
        if 'firstName' in data:
            current_user.first_name = data['firstName']
        if 'lastName' in data:
            current_user.last_name = data['lastName']
        if 'password' in data:
            current_user.password = generate_password_hash(data['password'])

        db.session.commit()
        return {'message': 'Account updated successfully'}, 200

# Получение списка всех аккаунтов (только для администраторов)
@api.route('/api/Accounts')
class AccountList(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'Success')
    @api.response(403, 'Permission denied')
    def get(self, current_user):
        """Get list of all users (Admin only)"""
        if 'Admin' not in current_user.roles:
            return {'message': 'Permission denied'}, 403

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
        return output, 200

    @api.expect(user_model)
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(201, 'New account created successfully')
    @api.response(403, 'Permission denied')
    def post(self, current_user):
        """Create a new account (Admin only)"""
        if 'Admin' not in current_user.roles:
            return {'message': 'Permission denied'}, 403

        data = request.get_json()
        hashed_password = generate_password_hash(data['password'])
        new_user = User(
            first_name=data['firstName'], 
            last_name=data['lastName'], 
            username=data['username'], 
            password=hashed_password, 
            roles=",".join(data.get('roles', ['User']))  # Сохраняем роли через запятую
        )
        db.session.add(new_user)
        db.session.commit()
        return {'message': 'New account created successfully'}, 201

# Изменение и удаление аккаунта администратором по ID
@api.route('/api/Accounts/<int:id>')
class AccountById(Resource):
    @api.expect(user_model)
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'User updated successfully')
    @api.response(403, 'Permission denied')
    @api.response(404, 'User not found')
    def put(self, current_user, id):
        """Update an account by ID (Admin only)"""
        if 'Admin' not in current_user.roles:
            return {'message': 'Permission denied'}, 403

        user = User.query.filter_by(id=id, is_deleted=False).first()
        if not user:
            return {'message': 'User not found'}, 404

        data = request.get_json()
        if 'firstName' in data:
            user.first_name = data['firstName']
        if 'lastName' in data:
            user.last_name = data['lastName']
        if 'password' in data:
            user.password = generate_password_hash(data['password'])
        if 'roles' in data:
            user.roles = ",".join(data['roles'])

        db.session.commit()
        return {'message': 'User updated successfully'}, 200

    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'User soft deleted successfully')
    @api.response(403, 'Permission denied')
    @api.response(404, 'User not found')
    def delete(self, current_user, id):
        """Soft delete an account (Admin only)"""
        if 'Admin' not in current_user.roles:
            return {'message': 'Permission denied'}, 403

        user = User.query.filter_by(id=id, is_deleted=False).first()
        if not user:
            return {'message': 'User not found'}, 404

        user.is_deleted = True
        db.session.commit()
        return {'message': 'User soft deleted successfully'}, 200

# Получение списка докторов (авторизованные пользователи)
@api.route('/api/Doctors')
class GetDoctors(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'Success')
    def get(self, current_user):
        """Get list of all doctors"""
        name_filter = request.args.get('nameFilter', '', type=str)
        from_ = request.args.get('from', 0, type=int)
        count = request.args.get('count', 10, type=int)

        doctors = User.query.filter(
            User.roles.contains('Doctor'),
            User.first_name.like(f'%{name_filter}%'),
            User.is_deleted == False
        ).offset(from_).limit(count).all()

        output = []
        for doctor in doctors:
            doctor_data = {
                'id': doctor.id,
                'firstName': doctor.first_name,
                'lastName': doctor.last_name,
                'username': doctor.username,
            }
            output.append(doctor_data)
        return output, 200

# Получение информации о докторе по ID
@api.route('/api/Doctors/<int:id>')
class GetDoctorById(Resource):
    @token_required
    @api.doc(security='Bearer Auth')
    @api.response(200, 'Success')
    @api.response(404, 'Doctor not found')
    def get(self, current_user, id):
        """Get doctor details by ID"""
        doctor = User.query.filter_by(id=id, is_deleted=False).first()
        if not doctor or 'Doctor' not in doctor.roles:
            return {'message': 'Doctor not found'}, 404

        doctor_data = {
            'id': doctor.id,
            'firstName': doctor.first_name,
            'lastName': doctor.last_name,
            'username': doctor.username,
        }
        return doctor_data, 200

if __name__ == '__main__':
    db.create_all()
    create_initial_users()
    app.run(host='0.0.0.0', port=5000, debug=True)
