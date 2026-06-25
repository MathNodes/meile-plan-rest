#!/bin/env python3

import os
import time
from os import path
import json
import pymysql
from urllib.parse import urlparse

from datetime import datetime
from dateutil.relativedelta import relativedelta

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute
from sentinel_protobuf.cosmos.base.v1beta1.coin_pb2 import Coin
from sentinel_protobuf.sentinel.types.v1.renewal_pb2 import RenewalPricePolicy
from mospy import Transaction
from keyrings.cryptfile.cryptfile import CryptFileKeyring
from grpc import RpcError

import scrtxxs

WalletLogDIR = scrtxxs.LogDIR
HotWalletAddress = scrtxxs.WalletAddress
keyring_passphrase = scrtxxs.HotWalletPW
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
db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)


def UpdateDBTable(query):
    
    cursor = db.cursor()
    cursor.execute(query)
    db.commit()
    db.close()

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
    
def ShareSubTX(sub_id: int, wallet, size=scrtxxs.BYTES_50):
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
    
def CheckRenewalStatus(wallet, plan_id):
    
    
    query = f"SELECT subscription_id, subscribe_date, expires FROM meile_subscriptions WHERE wallet = '{wallet}' AND plan_id = {plan_id};"
    c = db.cursor()
    c.execute(query)
    
    results = c.fetchone()
    
    if results:
        if results['subscribe_date'] and results['expires']:
            return True,results['subscribe_date'],results['expires']
        else: 
            return False, None, None          
    else: 
        return False, None, None
        
        
def manual_sub(uuid, plan_id, wallet, amt_paid, denom, duration):
    
    WalletLogFile = os.path.join(WalletLogDIR, "meile_plan.log") 
    log_file_descriptor = open(WalletLogFile, "a+")
    
    renewal,subscription_date, expiration = CheckRenewalStatus(wallet, plan_id)
    
    print(f"renewal: {renewal}, sub date: {subscription_date}")
    now = datetime.now()
    if expiration:
        if now < expiration:
            expires = expiration + relativedelta(months=+duration)
        else:
            expires = now + relativedelta(months=+duration)
    
    else:
        expires = now + relativedelta(months=+duration)
    
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
    
    result = ShareSubTX(sub_id, wallet)
    
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
            INSERT INTO itemized_subscriptions (wallet, plan_id, amt_paid, amt_denom, subscribe_date, subscription_duration)
            VALUES("%s", %d, %.8f, "%s", "%s", %d)
            ''' % (wallet, plan_id, amt_paid, denom, str(now), duration)     
            
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
    
if __name__ == "__main__":
    uuid = input("Plan UUID: ")
    plan_id = input("Plan ID: ")
    wallet = input("Wallet address: ")
    amt_paid = input("Amount paid: ")
    denom = input("Denom paid: ")
    duration = input("Duration (months): ")
    
    manual_sub(uuid, int(plan_id), wallet, int(amt_paid), denom, int(duration))
    
    