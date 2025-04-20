#!/bin/env python3
import json
import pymysql
import scrtxxs
from datetime import datetime
import pexpect
from os import path
import requests
from time import sleep
from urllib.parse import urlparse
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute
from sentinel_protobuf.cosmos.base.v1beta1.coin_pb2 import Coin
from mospy import Transaction
from keyrings.cryptfile.cryptfile import CryptFileKeyring
from grpc import RpcError


VERSION = 20240710.0033

API_DVPN_BALANCE = "https://api.sentinel.mathnodes.com/cosmos/bank/v1beta1/balances/%s/by_denom?denom=udvpn"
SATOSHI = 1000000

class TopUpSubscribers():
    
    def __init__(self):
        #self.__transfer_cmd = '%s tx bank send --gas auto --gas-prices 0.2udvpn --gas-adjustment 2.0 --yes %s %s 1000000udvpn --node "%s"' 
        
        keyring = self.__keyring(scrtxxs.HotWalletPW)
        private_key = keyring.get_password("meile-plan", scrtxxs.WalletName)        
        grpcaddr, grpcport = urlparse(scrtxxs.GRPC_DEV).netloc.split(":")
        self.sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=True)
        
        
    def __keyring(self,keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr 
        
        
    def connDB(self): 
        db = pymysql.connect(host=scrtxxs.MySQLHost,
                             port=scrtxxs.MySQLPort,
                             user=scrtxxs.MySQLUsername,
                             passwd=scrtxxs.MySQLPassword,
                             db=scrtxxs.MySQLDB,
                             charset="utf8mb4",
                             cursorclass=pymysql.cursors.DictCursor
                             )
    
        return db
    
    def get_subscribers(self, db):
        
        c = db.cursor()
        
        query = "select * from meile_subscriptions where subscribe_date > '2024-03-04' and active = 1;"
        c.execute(query)
        
        return c.fetchall()
    
    def top_up(self, subscribers):
        
        for s in subscribers:
            print(s)
            API_URL = API_DVPN_BALANCE % s['wallet']
            try: 
                r = requests.get(API_URL)
                amtjson = r.json()
                
            except Exception as e:
                print(str(e))
                continue
            
            balance = float(int(amtjson['balance']['amount']) / SATOSHI)
            print(f"{s['wallet']}: {balance}")
            if balance < 0.1:
                print(f"Balance: {balance}, Sending 1dvpn to: {s['wallet']}")
                
                
                tx_params = TxParams(
                                    gas=150000,
                                    gas_multiplier=1.2,
                                    fee_amount=31415,
                                    denom="udvpn"
                                    )
                
                tx = Transaction(
                               account=self.sdk._account,
                               fee=Coin(denom=tx_params.denom, amount=f"{tx_params.fee_amount}"),
                               gas=tx_params.gas,
                               protobuf="sentinel",
                               chain_id="sentinelhub-2",
                               memo=f"Meile Gas Favor",
                           )
                
                tx.add_msg(
                            tx_type='transfer',
                            sender=self.sdk._account,
                            receipient=s['wallet'],
                            amount=1000000,
                            denom="udvpn",
                          )
                
                self.sdk._client.load_account_data(account=self.sdk._account)
    
                tx_height = 0
                try:
                    tx = self.sdk._client.broadcast_transaction(transaction=tx)
                except RpcError as rpc_error:
                    details = rpc_error.details()
                    print("details", details)
                    print("code", rpc_error.code())
                    print("debug_error_string", rpc_error.debug_error_string())
                    continue
            
                if tx.get("log", None) is None:
                    tx_response = self.sdk.nodes.wait_for_tx(tx["hash"])
                    tx_height = tx_response.get("txResponse", {}).get("height", 0) if isinstance(tx_response, dict) else tx_response.tx_response.height
                    with open(path.join(scrtxxs.LogDIR, "top-up.log"), "a+") as log_file_descriptor:
                        log_file_descriptor.write(json.dumps(tx_response) + '\n')
                        log_file_descriptor.write(tx_height + '\n')
                    print(f'Successfully sent 1dvpn to: {s["wallet"]}, height: {tx_height}')
                 
                sleep(6)
    
if __name__ == "__main__":
    topup = TopUpSubscribers()
    subscribers = topup.get_subscribers(topup.connDB())
    print(subscribers)
    topup.top_up(subscribers)
    