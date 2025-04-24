import os
import jwt
import time
import pexpect
from urllib.parse import urlparse
from os import path
import json

from datetime import datetime
from dateutil.relativedelta import relativedelta

from flaskext.mysql import MySQL
from flask import Flask, abort, request, jsonify, g, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from passlib.apps import custom_app_context as pwd_context
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute
from sentinel_protobuf.cosmos.base.v1beta1.coin_pb2 import Coin
from mospy import Transaction
from keyrings.cryptfile.cryptfile import CryptFileKeyring
from grpc import RpcError


from pms.plan_node_subscriptions import PlanSubscribe

import scrtxxs


VERSION=20241222.2127

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
app.config['MYSQL_DATABASE_HOST'] = scrtxxs.MySQLHost


db = SQLAlchemy(app)
auth = HTTPBasicAuth()

def __keyring(keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr 

keyring = __keyring(scrtxxs.HotWalletPW)
private_key = keyring.get_password("meile-plan", scrtxxs.WalletName)        
grpcaddr, grpcport = urlparse(scrtxxs.GRPC_DEV).netloc.split(":")
sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=True)
alloc_private_key = keyring.get_password("meile-plan", scrtxxs.AllocWalletName)
sdkAlloc = SDKInstance(grpcaddr, int(grpcport), secret=alloc_private_key, ssl=True)

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

@app.route('/api/users/<int:id>')
def get_user(id): 
    user = User.query.get(id)
    if not user:
        abort(400)
    return jsonify({'username': user.username})

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
    
    return plan411[0], plan411[1]

def CheckRenewalStatus(subid, wallet):
    
    query = f"SELECT subscription_id, subscribe_date, expires FROM meile_subscriptions WHERE wallet = '{wallet}' AND subscription_id = {subid}"
    c = GetDBCursor()
    c.execute(query)
    
    results = c.fetchone()
    
    if results is not None:
        if results[0] and results[1]:
            return True,results[1],results[2]
        else: 
            return False, None, None          
    else: 
        return False, None, None
    
def AllocateTX(sdk, sub_id, wallet, size=scrtxxs.BYTES):
    # Add logging
    
    tx_params = TxParams(
                gas=150000,
                gas_multiplier=1.2,
                fee_amount=31415,
                denom="udvpn"
                )
    
    tx = sdk.subscriptions.Allocate(address=wallet, bytes=str(size), id=sub_id, tx_params=tx_params)
    
    if tx.get("log", None) is not None:
        message = "Error adding wallet to plan. Please contact support@mathnodes.com for assistance."        
        return {"status" : False, "message" : message, "hash" : "0x0", "tx_response" : None}
    
    if tx.get("hash", None) is not None:
        tx_response = sdk.nodes.wait_transaction(tx["hash"])
        return {"status" : True, "message" : "Success.", "hash" : tx['hash'], "tx_response" : tx_response}
    
    
def FeeGrant(wallet):
    
    tx_params = TxParams(
                gas=150000,
                gas_multiplier=1.2,
                fee_amount=31415,
                denom="udvpn"
                )
    
    tx = Transaction(
           account=sdk._account,
           fee=Coin(denom=tx_params.denom, amount=f"{tx_params.fee_amount}"),
           gas=tx_params.gas,
           protobuf="sentinel",
           chain_id="sentinelhub-2",
           memo=f"Meile Gas Favor",
       )
    tx.add_msg(
        tx_type='transfer',
        sender=sdk._account,
        receipient=wallet,
        amount=1000000,
        denom="udvpn",
    )
    
    sdk._client.load_account_data(account=sdk._account)
    
    tx_height = 0
    
    try:
        tx = sdk._client.broadcast_transaction(transaction=tx)
    except RpcError as rpc_error:
        details = rpc_error.details()
        print("details", details)
        print("code", rpc_error.code())
        print("debug_error_string", rpc_error.debug_error_string())
        return {"tx_response" : None, "height" : None, "status" : False}

    if tx.get("log", None) is None:
        tx_response = sdk.nodes.wait_for_tx(tx["hash"])
        tx_height = tx_response.get("txResponse", {}).get("height", 0) if isinstance(tx_response, dict) else tx_response.tx_response.height
        return {"tx_response" : tx_response, "height" : tx_height, "status" : True}
        
    
@app.route('/v1/add', methods=['POST'])
@auth.login_required
def add_wallet_to_plan():
    status  = False
    renewal = False
    hash = "0x0"
    try: 
        JSON      = request.json
        wallet    = JSON['data']['wallet']
        plan_id   = int(JSON['data']['plan_id'])     # plan ID, we should have 4 or 5 plans. Will be a UUID. 
        duration  = int(JSON['data']['duration'])   # duration of plan subscription, in months
        sub_id    = int(JSON['data']['sub_id'])      # subscription ID of plan
        uuid      = JSON['data']['uuid']            # uuid of subscription
        amt_paid  = int(JSON['data']['amt'])
        denom     = JSON['data']['denom']
    except Exception as e:
        print(str(e))
        status = False
        tx = None
        message = "Not all POST values were present. Please try submitting your request again."
        PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : None}
        print(PlanTX)
        return jsonify(PlanTX)    
    
    cost, plan_denom = GetPlanCostDenom(uuid)
    print(f"Cost: {cost}, denom: {plan_denom}")
    if not cost or not plan_denom:
        status = False
        message = "No plan found in Database. Wallet not added to non-existing plan"
        tx = "None"
        PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : None}
        print(PlanTX)
        return jsonify(PlanTX)
    
    renewal,subscription_date, expiration = CheckRenewalStatus(sub_id, wallet)
    
    now = datetime.now()
    if expiration:
        if now < expiration:
            expires = expiration + relativedelta(months=+duration)
        else:
            expires = now + relativedelta(months=+duration)
    
    else:
        expires = now + relativedelta(months=+duration)
    
    WalletLogFile = os.path.join(WalletLogDIR, "meile_plan.log") 
    log_file_descriptor = open(WalletLogFile, "a+")
    
    result = AllocateTX(sdk, sub_id, wallet)
    
    if not result['status']:
        expires = None
        message = result["message"]
        PlanTX = {'status' : result["status"],
                  'wallet' : wallet, 
                  'planid' : plan_id, 
                  'id' : sub_id, 
                  'duration' : duration, 
                  'tx' : result["hash"], 
                  'message' : message, 
                  'expires' : expires}
        print(PlanTX)
        log_file_descriptor.write(json.dumps(PlanTX) + '\n')
        return jsonify(PlanTX)
    
    else:
        print(result["tx_response"])
        
        PlanTX = {'status' : result["status"],
                  'wallet' : wallet, 
                  'planid' : plan_id, 
                  'id' : sub_id, 
                  'duration' : duration, 
                  'tx' : result["hash"], 
                  'message' : message, 
                  'expires' : str(expires)}
        log_file_descriptor.write(json.dumps(result["tx_response"]) + '\n')
        log_file_descriptor.write(json.dumps(PlanTX) + '\n')
    
    if renewal and subscription_date is not None:
        query = '''
                UPDATE meile_subscriptions 
                SET uuid = "%s", wallet = "%s", subscription_id = %d, plan_id = %d, amt_paid = %d, amt_denom = "%s", subscribe_date = "%s", subscription_duration = %d, expires = "%s, active = 1"
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
        log_file_descriptor.write("ERROR ADDING WALLET TO SUBSCRIPTION DATABASE" + '\n')
        
        
        
    result = FeeGrant(wallet)
    
    if result['status']:    
        log_file_descriptor.write(json.dumps(result["tx_response"]) + '\n')
        log_file_descriptor.write(result["height"] + '\n')
        print(f'Successfully sent 1dvpn to: {wallet}, height: {result["height"]}')
    else:
        log_message = f'Error sending 1dvpn to: {wallet}, height: {result["height"]}'
        print(log_message)
        log_file_descriptor.write(log_message + '\n')


    log_file_descriptor.close()
    return jsonify(PlanTX)
    
    
    
@app.route('/v1/plans', methods=['GET'])
@auth.login_required
def get_plan_subscriptions():
    query = "SELECT * from meile_plans";
    
    c = GetDBCursor()
    c.execute(query)

    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    result = []
    for row in rows:
        row = dict(zip(columns, row))
        result.append(row)

    try: 
        return jsonify(result)
    except Exception as e:
        print(str(e))
        abort(404)

@app.route('/v1/subscription/<walletAddress>', methods=['GET'])
@auth.login_required
def get_current_subscriber(walletAddress):
    
    query = f"SELECT * from meile_subscriptions WHERE wallet = '{walletAddress}'"
    
    c = GetDBCursor()
    c.execute(query)

    rows = c.fetchall()
    columns = [desc[0] for desc in c.description]
    result = []
    for row in rows:
        row = dict(zip(columns, row))
        result.append(row)

    try: 
        return jsonify(result)
    except Exception as e:
        print(str(e))
        abort(404)
        
@app.route('/v1/nodes/<uuid>', methods=['GET'])
@auth.login_required
def get_nodes(uuid):
    
    query = f"SELECT node_address FROM plan_nodes WHERE uuid = '{uuid}'"


    c = GetDBCursor()
    c.execute(query)
    
    rows = c.fetchall()
    result = []
    for row in rows:
        result.append(row[0])
    try:
        return jsonify(result)
    except Exception as e:
        print(str(e))
        abort(404)      
        
@app.route('/v1/allocate', methods=['POST'])
@auth.login_required
def allocate():
    try: 
        JSON      = request.json
        wallet    = JSON['wallet']
        GB        = int(JSON['gb']) 
        address   = JSON['node']
    except:
        message = "error reading JSON"
        return {'status' : False, 'message' : message}
    
    ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.AllocWalletName, None)
    res = ps.subscribe_to_nodes_for_plan(address,GB=GB) # need to add logging to file for this routine
    
    if res[0]:
        sub_id = res[1]
    else:
        message = "Error subscribing to node."
        result = {"status" : False, "message" : message, "hash" : None, "tx_response" : None}
        return jsonify(result)
        
    
    res = AllocateTX(sdkAlloc, sub_id, wallet, GB*scrtxxs.ONE_GB)
    return jsonify(res)
    
def UpdateMeileSubscriberDB():
    pass


db.create_all()
