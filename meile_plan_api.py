import os
import jwt
import time
import pexpect
from urllib.parse import urlparse
from os import path
import json
import requests
from requests.auth import HTTPBasicAuth as RequestsAuth
from requests.auth import HTTPDigestAuth

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
from sentinel_protobuf.sentinel.types.v1.renewal_pb2 import RenewalPricePolicy
from mospy import Transaction
from keyrings.cryptfile.cryptfile import CryptFileKeyring
from grpc import RpcError


from pms.plan_node_subscriptions import PlanSubscribe

import scrtxxs


VERSION=20260604.2244

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

def CheckRenewalStatus(wallet, plan_id):
    
    
    query = f"SELECT subscription_id, subscribe_date, expires FROM meile_subscriptions WHERE wallet = '{wallet}' AND plan_id = {plan_id};"
    c = GetDBCursor()
    c.execute(query)
    
    results = c.fetchone()
    print(results)
    if results:
        if results[1] and results[2]:
            return True,results[1],results[2]
        else: 
            return False, None, None          
    else: 
        return False, None, None
    
def SubToPlan(plan_id: int, wallet: str):
    # Add logging    
    WalletLogFile = os.path.join(WalletLogDIR, "meile_allocate.log") 
    log_file_descriptor = open(WalletLogFile, "a+")
    
    tx_params = TxParams(
                gas=150000,
                gas_multiplier=1.2,
                fee_amount=31415,
                denom="udvpn"
                )
    
    
    tx = sdk.subscriptions.StartSubscription(plan_id=plan_id,
                                            denom="udvpn", 
                                            renewal = RenewalPricePolicy.RENEWAL_PRICE_POLICY_IF_LESSER_OR_EQUAL, 
                                            tx_params=tx_params)
    
    if tx.get("log", None) is not None:
        log_file_descriptor.write(f"\nERROR:\n{tx.get('log')}")
        log_file_descriptor.flush()
        log_file_descriptor.close()
        message = "Error subscribing to plan. Please contact support@mathnodes.com for assistance."        
        return {"status" : False, 
                "message" : message, 
                "hash" : "0x0", 
                "tx_response" : None,
                "sub_id" : None}
    
    if tx.get("hash", None) is not None:
        tx_response = sdk.nodes.wait_transaction(tx["hash"])
        log_file_descriptor.write(f"\nSuccess:\n {tx_response}")
        subscription_id = search_attribute(
                tx_response, "sentinel.subscription.v3.EventCreate", "subscription_id"
            )
        log_file_descriptor.flush()
        log_file_descriptor.close()
        return {"status" : True, 
                "message" : "Success.",
                "hash" : tx['hash'], 
                "tx_response" : tx_response,
                'sub_id' : subscription_id}
    
def ShareSubTX(sdk, sub_id: int, wallet, size=scrtxxs.BYTES):
    # Add logging    
    WalletLogFile = os.path.join(WalletLogDIR, "meile_allocate.log") 
    log_file_descriptor = open(WalletLogFile, "a+")
    
    tx_params = TxParams(
                gas=150000,
                gas_multiplier=1.2,
                fee_amount=31415,
                denom="udvpn"
                )
    
    tx = sdk.subscriptions.ShareSubscription(subscription_id=sub_id,
                                             wallet_address=wallet, 
                                             bytes=str(size), 
                                             tx_params=tx_params)
    
    if tx.get("log", None) is not None:
        log_file_descriptor.write(f"\nERROR:\n{tx.get('log')}")
        log_file_descriptor.flush()
        log_file_descriptor.close()
        message = "Error adding wallet to plan. Please contact support@mathnodes.com for assistance."        
        return {"status" : False, "message" : message, "hash" : "0x0", "tx_response" : None}
    
    if tx.get("hash", None) is not None:
        tx_response = sdk.nodes.wait_transaction(tx["hash"])
        log_file_descriptor.write(f"\nSuccess:\n {tx_response}")
        log_file_descriptor.flush()
        log_file_descriptor.close()
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
        recipient=wallet,
        amount=4000000,
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
        JSON          = request.json
        wallet        = JSON['data']['wallet']
        plan_id       = int(JSON['data']['plan_id'])     # plan ID, we should have 4 or 5 plans. Will be a UUID. 
        duration      = int(JSON['data']['duration'])   # duration of plan subscription, in months
        try: 
            old_sub_id    = int(JSON['data']['sub_id'])      # subscription ID of plan
        except:
            old_sub_id = 0
        uuid          = JSON['data']['uuid']            # uuid of subscription
        amt_paid      = float(JSON['data']['amt'])
        denom         = JSON['data']['denom']
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
    print(f"Paid: {amt_paid}, denom: {denom}")
    if not cost or not plan_denom:
        status = False
        message = "No plan found in Database. Wallet not added to non-existing plan"
        tx = "None"
        PlanTX = {'status' : status, 'wallet' : wallet, 'planid' : plan_id, 'id' : sub_id, 'duration' : duration, 'tx' : tx, 'message' : message, 'expires' : None}
        print(PlanTX)
        return jsonify(PlanTX)
    
    renewal,subscription_date, expiration = CheckRenewalStatus(wallet, plan_id)
    print(f"renewal: {renewal}, sub date: {subscription_date}") 
    try:
        print(f"User: {g.user.username}")
    except:
        pass   
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
    
    sub_result = SubToPlan(plan_id, wallet)
    if not sub_result['status']:
        PlanTX = {'status' : result["status"],
                  'wallet' : wallet, 
                  'planid' : plan_id, 
                  'duration' : duration, 
                  'tx' : result["hash"], 
                  'message' : result["message"],
                  'expires' : None}
        print(PlanTX)
        log_file_descriptor.write(json.dumps(PlanTX) + '\n')
        return jsonify(PlanTX)
    
    else:
        sub_id = int(sub_result['sub_id'])
    
    result = ShareSubTX(sdk, sub_id, wallet)
    
    if not result['status']:
        PlanTX = {'status' : result["status"],
                  'wallet' : wallet, 
                  'planid' : plan_id, 
                  'id' : sub_id, 
                  'duration' : duration, 
                  'tx' : result["hash"], 
                  'message' : result["message"],
                  'expires' : None}
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
                  'message' : result["message"], 
                  'expires' : str(expires)}
        log_file_descriptor.write(json.dumps(result["tx_response"]) + '\n')
        log_file_descriptor.write(json.dumps(PlanTX) + '\n')
    
    if renewal and subscription_date is not None:
        query = '''
                UPDATE meile_subscriptions 
                SET uuid = "%s", wallet = "%s", subscription_id = %d, plan_id = %d, amt_paid = %.8f, amt_denom = "%s", subscribe_date = "%s", subscription_duration = %d, expires = "%s", active = "1"
                WHERE wallet = "%s" AND plan_id = %d
                ''' % (uuid, wallet, sub_id, plan_id, amt_paid, denom, subscription_date, duration, str(expires), wallet, plan_id) 
                
    else:
        query = '''
                INSERT INTO meile_subscriptions (uuid, wallet, subscription_id, plan_id, amt_paid, amt_denom, subscribe_date, subscription_duration, expires)
                VALUES("%s", "%s", %d, %d, %.8f, "%s", "%s", %d, "%s")
                ''' % (uuid, wallet, sub_id, plan_id, amt_paid, denom, str(now), duration, str(expires)) 


    print("Updating Subscription Table...")
    print(query)
    
    try:
        UpdateDBTable(query)    
    except Exception as e:
        print(str(e))
        log_file_descriptor.write("ERROR ADDING WALLET TO SUBSCRIPTION DATABASE" + '\n')
        
    query = '''
            INSERT INTO itemized_subscriptions (wallet, plan_id, amt_paid, amt_denom, subscribe_date, subscription_duration, user)
            VALUES("%s", %d, %.8f, "%s", "%s", %d, "%s")
            ''' % (wallet, plan_id, amt_paid, denom, str(now), duration, g.user.username)     
            
    print("Updating Itemized Subscription Table...")
    print(query)
    
    try:
        UpdateDBTable(query)    
    except Exception as e:
        print(str(e))
        log_file_descriptor.write("ERROR ADDING WALLET TO ITEMIZED SUBSCRIPTION DATABASE" + '\n')
        
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
        sub_id = int(res[1])
    else:
        message = "Error subscribing to node."
        result = {"status" : False, "message" : message, "hash" : None, "tx_response" : None}
        return jsonify(result)
        
    sleep(4)
    res = AllocateTX(sdkAlloc, sub_id, wallet, GB*scrtxxs.ONE_GB)
    return jsonify(res)

@app.route('/v1/pirate/newaddress', methods=['GET'])
@auth.login_required
def get_new_zaddress():
    url = scrtxxs.PIRATEHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id": "meile",
        "method": "z_getnewaddress",
        "params": []
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.PIRATEUSER, scrtxxs.PIRATEPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
        return jsonify(response.json())
    else:
        return jsonify({'result': None, 'error': response.status_code, 'id': 'meile'})
    
    
@app.route('/v1/pirate/getbalance', methods=['POST'])
@auth.login_required    
def get_pirate_balance():
    try:
        JSON      = request.json
        address   = JSON['address']
        conf      = JSON['conf']
    except Exception as e:
        print(str(e))
        return False
    
    url = scrtxxs.PIRATEHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id":"meile", 
        "method": "z_getbalance", 
        "params": [address, conf] 
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.PIRATEUSER, scrtxxs.PIRATEPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"address: {address}\n response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})
    
    
    
@app.route('/v1/pirate/getbalances', methods=['GET'])    
def get_pirate_balances():
    
    url = scrtxxs.PIRATEHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id":"meile", 
        "method": "z_getbalances", 
        "params": [True] 
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.PIRATEUSER, scrtxxs.PIRATEPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})
    

@app.route('/v1/firo/newsparkaddress', methods=['GET'])
@auth.login_required
def get_new_saddress():
    url = scrtxxs.FIROHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id": "meile",
        "method": "getnewsparkaddress",
        "params": []
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
        return jsonify(response.json())
    else:
        return jsonify({'result': None, 'error': response.status_code, 'id': 'meile'})
    
    
@app.route('/v1/firo/getsparkbalance', methods=['POST'])
@auth.login_required    
def get_spark_balance():
    try:
        JSON      = request.json
        address   = JSON['address']
    except Exception as e:
        print(str(e))
        return False
    
    url = scrtxxs.FIROHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id":"meile", 
        "method": "getsparkaddressbalance", 
        "params": [address] 
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"address: {address}\n response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})
    
@app.route('/v1/firo/getsparktxs', methods=['POST'])
@auth.login_required    
def get_spark_txs():
    try:
        JSON = request.json
        amount = JSON['amount']
    except Exception as e:
        print(str(e))
        return jsonify({
            "success": False,
            "chainlock": False,
            "instantlock": False,
            "error": "Invalid request body"
        }), 400

    url = scrtxxs.FIROHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id": "meile", 
        "method": "listtransactions",
        "params": ["*", 10, 0, True]  # Note: Python uses True, not true
    }

    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )

    print(response.status_code)
    if response.status_code == 200:
        try:
            rpc_response = response.json()
            transactions = rpc_response.get("result", [])
            print(transactions[-1])
            # Search for a transaction with matching amount
            for tx in transactions:
                tx_amount = tx.get("amount", 0)

                # Compare amounts (using float comparison with tolerance for precision)
                if abs(float(tx_amount) - float(amount)) < 0.00000001:
                    return jsonify({
                        "success": True,
                        "chainlock": tx.get("chainlock", False),
                        "instantlock": tx.get("instantlock", False)
                    })

            # No matching transaction found
            return jsonify({
                "success": False,
                "chainlock": False,
                "instantlock": False,
                "error": "No transaction found with matching amount"
            })

        except Exception as e:
            print(f"Error parsing response: {str(e)}")
            return jsonify({
                "success": False,
                "chainlock": False,
                "instantlock": False,
                "error": "Failed to parse RPC response"
            }), 500
    else:
        return jsonify({
            "success": False,
            "chainlock": False,
            "instantlock": False,
            "error": f"RPC request failed with status {response.status_code}"
        }), 502


@app.route('/v1/firo/getsparkwalletbalance', methods=['GET'])
def get_spark_wallet_balance():
    url = scrtxxs.FIROHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id": "meile",
        "method": "getsparkbalance",
        "params": []
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
        return jsonify(response.json())
    else:
        return jsonify({'result': None, 'error': response.status_code, 'id': 'meile'})
    
   
@app.route('/v1/pivx/newaddress', methods=['GET'])
@auth.login_required
def get_new_paddress():
    url = scrtxxs.PIVXHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id": "meile",
        "method": "getnewshieldaddress",
        "params": []
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
        return jsonify(response.json())
    else:
        return jsonify({'result': None, 'error': response.status_code, 'id': 'meile'})
    

@app.route('/v1/pivx/getbalance', methods=['POST'])
@auth.login_required    
def get_pivx_balance():
    try:
        JSON      = request.json
        address   = JSON['address']
        conf      = JSON['conf']
    except Exception as e:
        print(str(e))
        return False
    
    url = scrtxxs.PIVXHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id":"meile", 
        "method": "getshieldbalance", 
        "params": [address, conf] 
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"address: {address}\n response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})
    
@app.route('/v1/pivx/getbalances', methods=['GET'])    
def get_pivx_balances():
    
    url = scrtxxs.PIVXHOST
    headers = {'content-type': 'text/plain;'}
    data = {
        "jsonrpc": "1.0",
        "id":"meile", 
        "method": "listshieldunspent", 
        "params": [] 
    }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=RequestsAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})
    
'''
@app.route('/v1/zano/gettxs', methods=['POST'])
@auth.login_required    
def get_zano_txs():
    SATOSHI = 1000000000000
    SATOSHI_FUSD = 10000
    SATOSHI_BNB = 1000000
    SATOSHI_BCH = 100000000
    SATOSHI_BTC = SATOSHI_BCH
    SATOSHI_DAI = SATOSHI_BNB
    SATOSHI_ETH = SATOSHI_BNB
    SATOSHI_SOL = SATOSHI_BNB
    SATOSHI_TON = SATOSHI_BNB
    accumulated = 0
    FOUND = False
    ASSET_IDS = {'zano' : 'd6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a',
                 'fusd' : '86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f',
                 'bchx' : '3de9ad7243afa49e0ade6839e97a9f10a527c4958ece2fc9cb1b87a44032167d',
                 'bnbx' : '6ca3fa07f1b6a75b6e195d2918c32228765968b54ea691c75958affa1c4073fb',
                 'btcx' : '040a180aca4194a158c17945dd115db42086f6f074c1f77838621a4927fffa91',
                 'daix' : '24819c4b65786c3ac424e05d9ef4ab212de6222cc73bc5c4b012df5a3107eea4',
                 'ethx' : '93da681503353509367e241cda3234299dedbbad9ec851de31e900490807bf0c',
                 'solx' : '65b3bc549c8bc2c773781d5436f25f7af84644e61baaabd675d9867b007d17b4',
                 'tonx' : 'bfa6609a94e39f418d9adb000f89edc7bd180fd120f1cd272201220e3070fb4f'}
    
    try:
        JSON      = request.json
        address   = JSON['address']
        coin      = JSON['coin']
    except Exception as e:
        print(str(e))
        return False
    
    asset_id = ASSET_IDS[coin]
    
    url = scrtxxs.ZANOHOST
    headers = {'content-type': 'text/plain;'}
    data = {
          "id": 0,
          "jsonrpc": "2.0",
          "method": "get_recent_txs_and_info",
          "params": {
            "count": 10,
            "exclude_mining_txs": False,
            "exclude_unconfirmed": False,
            "offset": 0,
            "order": "FROM_END_TO_BEGIN",
            "update_provision_info": True
          }
        }
    

    try:
        response = requests.post(
            url,
            json=data,
            headers=headers,
        )
    except Exception as e:
        print(str(e))
        return jsonify({'result' : 0.0,
                        'height' : None,
                        'error' : None})
    
    print(response.status_code)
    if response.status_code == 200:
        result = response.json()
        height = result['result']['pi']['curent_height']
        print(f"Height: {height}")
        print(f"address: {address}\n response: {response.json()}")
        for tx in result['result']['transfers']:
            if tx['comment'] == address and tx['employed_entries']['receive'][0]['asset_id'] == asset_id and (tx['height'] == 0 or tx['height'] > height - 10):
                FOUND = True
                txheight = tx['height']
                if asset_id == ASSET_IDS['fusd']:
                    accumulated += float(tx['employed_entries']['receive'][0]['amount']) / SATOSHI_FUSD
                else:
                    accumulated += float(tx['employed_entries']['receive'][0]['amount']) / SATOSHI
                
        if FOUND:
            return jsonify({'result' : round(float(accumulated),8),
                            'height' : txheight,
                            'error' : None})
        else:
            return jsonify({'result' : 0.0,
                            'height' : None,
                            'error' : None})
    else:
        return jsonify({'result': 0.0, 
                        'error': response.status_code,  
                        'height' : None})
'''
    
@app.route('/v1/zano/gettxs', methods=['POST'])
@auth.login_required
def get_zano_txs():
    ASSETS = {
        'zano': {
            'asset_id': 'd6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a',
            'divisor': 10 ** 12,
        },
        'fusd': {
            'asset_id': '86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f',
            'divisor': 10 ** 4,
        },
        'bchx': {
            'asset_id': '3de9ad7243afa49e0ade6839e97a9f10a527c4958ece2fc9cb1b87a44032167d',
            'divisor': 10 ** 8,
        },
        'bnbx': {
            'asset_id': '6ca3fa07f1b6a75b6e195d2918c32228765968b54ea691c75958affa1c4073fb',
            'divisor': 10 ** 6,
        },
        'btcx': {
            'asset_id': '040a180aca4194a158c17945dd115db42086f6f074c1f77838621a4927fffa91',
            'divisor': 10 ** 8,
        },
        'daix': {
            'asset_id': '24819c4b65786c3ac424e05d9ef4ab212de6222cc73bc5c4b012df5a3107eea4',
            'divisor': 10 ** 6,
        },
        'ethx': {
            'asset_id': '93da681503353509367e241cda3234299dedbbad9ec851de31e900490807bf0c',
            'divisor': 10 ** 6,
        },
        'solx': {
            'asset_id': '65b3bc549c8bc2c773781d5436f25f7af84644e61baaabd675d9867b007d17b4',
            'divisor': 10 ** 6,
        },
        'tonx': {
            'asset_id': 'bfa6609a94e39f418d9adb000f89edc7bd180fd120f1cd272201220e3070fb4f',
            'divisor': 10 ** 6,
        },
    }

    try:
        body = request.get_json(force=True)

        address = body.get('address')
        coin = body.get('coin', '').lower()

        if not address:
            return jsonify({
                'result': 0.0,
                'height': None,
                'error': 'Missing address',
            }), 400

        if coin not in ASSETS:
            return jsonify({
                'result': 0.0,
                'height': None,
                'error': f'Unsupported coin: {coin}',
            }), 400

    except Exception as e:
        print(str(e))
        return jsonify({
            'result': 0.0,
            'height': None,
            'error': 'Invalid JSON request',
        }), 400

    asset_id = ASSETS[coin]['asset_id']
    divisor = ASSETS[coin]['divisor']

    url = scrtxxs.ZANOHOST

    headers = {
        'Content-Type': 'application/json',
    }

    data = {
        'id': 0,
        'jsonrpc': '2.0',
        'method': 'get_recent_txs_and_info',
        'params': {
            'count': 10,
            'exclude_mining_txs': False,
            'exclude_unconfirmed': False,
            'offset': 0,
            'order': 'FROM_END_TO_BEGIN',
            'update_provision_info': True,
        },
    }

    try:
        response = requests.post(
            url,
            json=data,
            headers=headers,
            timeout=20,
        )
    except Exception as e:
        print(str(e))
        return jsonify({
            'result': 0.0,
            'height': None,
            'error': str(e),
        }), 500

    if response.status_code != 200:
        return jsonify({
            'result': 0.0,
            'height': None,
            'error': response.status_code,
        }), response.status_code

    try:
        rpc_response = response.json()
    except Exception as e:
        print(str(e))
        return jsonify({
            'result': 0.0,
            'height': None,
            'error': 'Invalid JSON response from Zano RPC',
        }), 500

    try:
        result = rpc_response.get('result', {})
        pi = result.get('pi', {})
        height = pi.get('curent_height')

        transfers = result.get('transfers', [])

        accumulated = 0
        found = False
        txheight = None

        print(f'Height: {height}')
        print(f'Address: {address}')
        print(f'Coin: {coin}')
        print(f'Asset ID: {asset_id}')

        for tx in transfers:
            tx_comment = tx.get('comment')
            current_tx_height = tx.get('height', 0)

            if tx_comment != address:
                continue

            if height is not None:
                if current_tx_height != 0 and current_tx_height <= height - 10:
                    continue

            employed_entries = tx.get('employed_entries', {})
            receive_entries = employed_entries.get('receive', [])

            for receive_entry in receive_entries:
                receive_asset_id = receive_entry.get('asset_id')

                if receive_asset_id != asset_id:
                    continue

                raw_amount = receive_entry.get('amount', 0)
                amount = float(raw_amount) / divisor

                accumulated += amount
                found = True
                txheight = current_tx_height

        if found:
            return jsonify({
                'result': round(float(accumulated), 8),
                'height': txheight,
                'error': None,
            })

        return jsonify({
            'result': 0.0,
            'height': None,
            'error': None,
        })

    except Exception as e:
        print(str(e))
        return jsonify({
            'result': 0.0,
            'height': None,
            'error': str(e),
        }), 500
        
@app.route('/v1/zano/getbalances', methods=['GET'])    
def get_zano_balances():
    url = scrtxxs.ZANOHOST
    headers = {'content-type': 'text/plain;'}
    data = {
              "id": 0,
              "jsonrpc": "2.0",
              "method": "getbalance",
              "params": {
              }                                                                               
            }
    
    response = requests.post(
        url,
        json=data,
        headers=headers)
    
    print(response.status_code)
    if response.status_code == 200:
        print(f"response: {response.json()}")
        return jsonify(response.json())
    else:
        return jsonify({'result': 0.0, 'error': response.status_code, 'id': 'meile'})

@app.route('/v1/zephyr/newaddress', methods=['GET'])
@auth.login_required
def get_new_zeph_address():
    url = scrtxxs.ZEPHYRHOST
    headers = {'content-type': 'application/json'}
    data = {
            "jsonrpc": "2.0",
            "id": "0",
            "method": "create_address",
            "params": {
              "account_index": 0,
              "label": "meile payment"
            }
          }
    
    response = requests.post(
        url,
        json=data,
        headers=headers,
        auth=HTTPDigestAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
    )
    print(response.status_code)
    if response.status_code == 200:
        print(response.json())
        result = response.json()
        return jsonify({
            "success" : True,
            "address" : result['result']['address'],
            "index"   : result['result']['address_index']
            })
        #return jsonify(response.json())
    else:
        return jsonify({
            "success" : False,
            "address" : None,
            "index"   : None
            })
        
@app.route('/v1/zephyr/getbalance', methods=['POST'])
@auth.login_required
def get_zephyr_balance():
    try:
        data   = request.json
        index  = data['index']
        amount = data['amount']
        asset  = data['asset']
    except Exception as e:
        print(str(e))
        return jsonify({
            'success': False,
            'confirmations': None,
            'difference': None,
            'error': 'Invalid request parameters'
        }), 400

    url = scrtxxs.ZEPHYRHOST
    headers = {'content-type': 'application/json'}

    payload = {
        "jsonrpc": "2.0",
        "id": "0",
        "method": "get_transfers",
        "params": {
            "in": True,
            "pool": True,
            "out": False,
            "pending": False,
            "failed": False,
            "account_index": 0,
            "subaddr_indices": [index]
        }
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            auth=HTTPDigestAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD)
        )
        result = response.json().get('result', {})
    except Exception as e:
        print(str(e))
        return jsonify({
            'success': False,
            'confirmations': None,
            'difference': None,
            'error': 'RPC request failed'
        }), 500

    confirmed_txs = result.get('in', [])
    pool_txs = result.get('pool', [])

    all_txs = []

    for tx in confirmed_txs:
        if tx.get('asset_type') == asset:
            all_txs.append({
                'amount': tx.get('amount', 0),
                'confirmations': tx.get('confirmations', 0),
                'in_pool': False
            })

    for tx in pool_txs:
        if tx.get('asset_type') == asset:
            all_txs.append({
                'amount': tx.get('amount', 0),
                'confirmations': 0,
                'in_pool': True
            })

    if not all_txs:
        return jsonify({
            'success': False,
            'confirmations': 0,
            'difference': amount
        })

    total_received = sum(tx['amount'] for tx in all_txs)
    print(f"Total Received: {total_received}")
    total_received_decimal = total_received / 1e12
    print(f"Total Received Decimal: {total_received_decimal}")
    difference = amount - total_received_decimal 
    print(f"difference: {difference}")
    
    min_confirmations = min(tx['confirmations'] for tx in all_txs)
    success = total_received_decimal >= amount
    print(f"Success: {success}")
    return jsonify({
        'success': success,
        'confirmations': min_confirmations,
        'difference': difference
    })

@app.route('/v1/zephyr/getallbalances', methods=['GET'])
#@auth.login_required
def get_zephyr_all_balances():
    url = scrtxxs.ZEPHYRHOST
    headers = {'Content-Type': 'application/json'}

    all_balances = []

    for asset in ['ZPH', 'ZSD', 'ZRS']:
        response = requests.post(url, json={
            "jsonrpc": "2.0",
            "id": "0",
            "method": "get_balance",
            "params": {
                "account_index": 0,
                "asset_type": asset
            }
        }, headers=headers, auth=HTTPDigestAuth(scrtxxs.FIROUSER, scrtxxs.FIROPASSWORD))

        result = response.json().get('result', {})
        for bal in result.get('balances', []):
            for sub in bal.get('per_subaddress', []):
                all_balances.append({
                    'index': sub['address_index'],
                    'address': sub['address'],
                    'asset_type': asset,
                    'balance': sub['balance'] / 1e12,
                    'label': sub.get('label', '')
                })

    return jsonify({'result': all_balances})

        
def UpdateMeileSubscriberDB():
    pass


db.create_all()

