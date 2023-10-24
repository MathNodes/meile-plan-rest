import pwd
import os
import jwt
import time
import stripe
import pexpect

from datetime import datetime
from dateutil.relativedelta import relativedelta

from flaskext.mysql import MySQL
from flask import Flask, abort, request, jsonify, g, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

import scrtxxs

VERSION=20231024.0250

app = Flask(__name__)
mysql = MySQL()
mysql.init_app(app)

 

HotWalletAddress = scrtxxs.WalletAddress
keyring_passphrase = scrtxxs.HotWalletPW

DBdir = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/dbs'
WalletLogDIR = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/Logs'
DBFile = 'sqlite:///' + DBdir + '/dvpn_stripe.sqlite'


# SQLAlchemy Configurations
app.config['SECRET_KEY'] = scrtxxs.SQLAlchemyScrtKey
app.config['SQLALCHEMY_DATABASE_URI'] = DBFile
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFCATIONS'] = False

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = scrtxxs.MySQLUsername
app.config['MYSQL_DATABASE_PASSWORD'] = scrtxxs.MySQLPassword
app.config['MYSQL_DATABASE_DB'] = scrtxxs.MySQLDB
app.config['MYSQL_DATABASE_HOST'] = 'localhost'


db = SQLAlchemy(app)
auth = HTTPBasicAuth()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), index=True)
    password_hash = db.Column(db.String(128))

    def hash_password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_auth_token(self, expires_in=600):
        return jwt.encode(
            {'id': self.id, 'exp': time.time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_auth_token(token):
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'],
                              algorithms=['HS256'])
        except:
            return
        return User.query.get(data['id'])
 
@auth.verify_password
def verify_password(username_or_token, password):
    # first try to authenticate by token
    user = User.verify_auth_token(username_or_token)
    if not user:
        # try to authenticate with username/password
        user = User.query.filter_by(username=username_or_token).first()
        if not user or not user.verify_password(password):
            return False
    g.user = user
    return True

@app.route('/api/users', methods=['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400)    # missing arguments
    if User.query.filter_by(username=username).first() is not None:
        abort(400)    # existing user
    user = User(username=username)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return (jsonify({'username': user.username}), 201,
            {'Location': url_for('get_user', id=user.id, _external=True)})

'''
@app.route('/api/users/<int:id>')
def get_user(id): 
    user = User.query.get(id)
    if not user:
        abort(400)
    return jsonify({'username': user.username})
'''
@app.route('/api/token')
@auth.login_required
def get_auth_token():
    token = g.user.generate_auth_token(600)
    return jsonify({'token': token.decode('ascii'), 'duration': 600})

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404</h1><p>The resource could not be found.</p>", 404

def UpdateDBTable(query):
    conn = mysql.connect()
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()
    
def GetDBCursor():
    conn = mysql.connect()
    return conn.cursor()
    
@app.route('/v1/add', methods=['POST'])
@auth.login_required
def add_wallet_to_plan():
    wallet    = request.json.get('wallet')
    plan_uuid = request.json.get('uuid')     # plan ID, we should have 4 or 5 plans. Will be a UUID. 
    duration  = request.json.get('duration') # duration of plan subscription, in months
    sub_id    = request.json.get('subid')
    
    now = datetime.now()
    plan_expirary = now + relativedelta(months=+duration)
    
    
@app.route('/v1/plans', methods=['GET'])
@auth.login_required
def get_plan_subscriptions():
    query = "SELECT * from meile_plans";
    
    c = GetDBCursor()
    c.execute(query)

    try: 
        return Response(jsonify(data=c.fetchall()), status=200, mimetype='application/json')
    except:
        abort(404)

@app.route('/v1/subscription/<walletAddress>', methods=['GET'])
@auth.login_required
def get_current_subscriber(walletAddress):
    
    query = f"SELECT * from meile_subscriptions WHERE wallet = {walletAddress}"
    
    c = GetDBCursor()
    c.execute(query)
    
    try: 
        return Response(jsonify(data=c.fetchall()), status=200, mimetype='application/json')
    except:
        abort(404)

def UpdateMeileSubscriberDB():
    pass


db.create_all()
