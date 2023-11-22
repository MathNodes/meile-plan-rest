import os
import jwt
import time
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

DBdir = scrtxxs.dbDIR
WalletLogDIR = scrtxxs.LogDIR
DBFile = 'sqlite:///' + DBdir + '/meile_plan.sqlite'


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
    
def GetPlanCostDenom(uuid):
    
    query = "SELECT plan_price, plan_denom FROM meile_plans;"
    
    c = GetDBCursor()
    c.execute(query)
    plan411 = c.fetchone()
    
    return plan411['plan_price'], plan411['plan_denom']

def CheckRenewalStatus(subid, wallet):
    
    query = f"SELECT subscription_id, subscription_date FROM meile_subscriptions WHERE wallet={wallet} AND subscription_id = {subid}"
    c = GetDBCursor()
    c.execute(query)
    
    results = c.fetchone()
    
    if results['subscription_date'] and results['subscription_id']:
        return True,results['subscription_date']
    else: 
        return False, None          
    
@app.route('/v1/add', methods=['POST'])
@auth.login_required
def add_wallet_to_plan():
    status  = False
    renewal = False
    try: 
        JSON      = request.json
        wallet    = JSON['data']['wallet']
        plan_id   = int(JSON['data']['planid'])     # plan ID, we should have 4 or 5 plans. Will be a UUID. 
        duration  = int(JSON['data']['duration'])   # duration of plan subscription, in months
        sub_id    = int(JSON['data']['subid'])      # subscription ID of plan
        uuid      = JSON['data']['uuid']            # uuid of subscription
        amt_paid  = int(JSON['data']['amt'])
        denom     = int(JSON['data']['denom'])
    except Exception as e:
        print(str(e))
        status = False
        tx = None
        message = "Not all POST values were present. Please try submitting your request again."
        PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : None}
        print(PlanTX)
        return jsonify(PlanTX)    
    
    cost, denom = GetPlanCostDenom(uuid)
    
    if not cost or not denom:
        status = False
        message = "No plan found in Database. Wallet not added to non-existing plan"
        tx = "None"
        PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : None}
        print(PlanTX)
        return jsonify(PlanTX)
    
    renewal,subscription_date = CheckRenewalStatus(sub_id, wallet) 
    
    now = datetime.now()
    expires = now + relativedelta(months=+duration)
    
    
    WalletLogFile = os.path.join(WalletLogDIR, "meile_plan.log")
    add_to_plan_cmd = '%s tx vpn subscription allocate --from "%s" --gas-prices "0.3udvpn" --node "%s" --keyring-dir "%s" --keyring-backend "file" --chain-id "%s" --yes %s "%s" %d' % (scrtxxs.sentinelhub,
                                                                                                                                                                      scrtxxs.WalletName,
                                                                                                                                                                      scrtxxs.RPC,
                                                                                                                                                                      scrtxxs.KeyringDIR,
                                                                                                                                                                      scrtxxs.CHAINID,
                                                                                                                                                                      sub_id,
                                                                                                                                                                      wallet,
                                                                                                                                                                      scrtxxs.BYTES)
    
    
    
    
    print(add_to_plan_cmd)
    try: 
        ofile = open(WalletLogFile, 'ab+')
        
        child = pexpect.run(add_to_plan_cmd)
        child.logfile = ofile
        
        child.expect("Enter .*")
        child.sendline(keyring_passphrase)
        child.expect(pexpect.EOF)
        
        
        ofile.flush()
        ofile.close()
        ofile.close()
        with open(WalletLogFile ,'r+') as rfile:
            last_line = rfile.readlines()[-1]
            if 'txhash' in last_line:
                tx = last_line.split(':')[-1].rstrip().lstrip()
                print(f"{wallet} added to plan: {sub_id}, plan_id: {plan_id}, {duration} months, hash: {tx}")
            else:
                tx = 'none'
        
        rfile.close()
        status = True
        message = "Success."
    except Exception as e:
        print(str(e))
        status = False
        message = "Error adding wallet to plan. Please contact support@mathnodes.com for assistance."
        expires = None
    if renewal and subscription_date is not None:
        query = '''
                UPDATE meile_subscriptions 
                SET uuid = "%s", wallet = "%s", subscription_id = %d, plan_id = %d, amt_paid = %d, amt_denom = "%s", subscribe_date = "%s", subscription_duration = %d, expires = "%s"
                WHERE wallet = "%s" AND subscription_id = %d
                ''' % (uuid, wallet, sub_id, plan_id, amt_paid, denom, subscription_date, duration, str(expires), wallet, sub_id) 
                
    else:
        query = '''
                INSERT INTO meile_subscriptions (uuid, wallet, subscription_id, plan_id, amt_paid, amt_denom, subscribe_date, subscription_duration, expires)
                VALUES("%s", "%s", %d, %d, %d, "%s", "%s", %d, "%s")
                ''' % (uuid, wallet, sub_id, plan_id, amt_paid, denom, str(now), duration, str(expires)) 


    print("Updating Subscription Table...")
    try:
        UpdateDBTable(query)    
    except Exception as e:
        print(str(e))
        status = False
        message = "Error updating subscription table. Please contact support@mathnodes.com for more information."
        tx = None
        expires = None
        
    PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : expires}
    return jsonify(PlanTX)
    
    
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