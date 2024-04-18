#!/bin/env python3
import json
import pymysql
import scrtxxs
from datetime import datetime
import pexpect
from os import path
from time import sleep
from urllib.parse import urlparse
import grpc

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute

from keyrings.cryptfile.cryptfile import CryptFileKeyring

VERSION = 20240417.235040

class PurgeExpiredSubs():
    
    def __init__(self):
        self.__deallocate_cmd = '%s tx vpn subscription allocate --from "%s" --gas-prices "0.3udvpn" --node "%s" --keyring-dir "%s" --keyring-backend "file" --chain-id "%s" --yes %s "%s" 0'
        self.__unsubLog = path.join(scrtxxs.LogDIR, "meile_unsub.log")
        
        keyring = self.__keyring(scrtxxs.HotWalletPW)
        private_key = keyring.get_password("meile-plan", scrtxxs.WalletName)        
        grpcaddr, grpcport = urlparse(scrtxxs.GRPC_BLUEFREN).netloc.split(":")
        self.sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=True)
    
    
    def __keyring(self, keyring_passphrase: str):
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
    
    def get_subscription_table(self,db):
        c = db.cursor()
        query = 'SELECT * FROM meile_subscriptions WHERE active = 1;'
        c.execute(query)
        
        return c.fetchall()
    def update_sub_table(self,sub,db):
        q = f"UPDATE meile_subscriptions SET active = 0 WHERE id = {sub['id']};"
        c = db.cursor()
        c.execute(q)
        db.commit()

    
    def deactivate_expired_subscriptions(self, db, subs_table):
        NOW = datetime.now()
        print("Removing Allocations...")        
        for sub in subs_table:
            if sub['expires'] < NOW:
                print("Querying allocation...")
                
                try:
                    allocation = self.sdk.subscriptions.QueryAllocation(address=sub['wallet'], 
                                                                        subscription_id=int(sub['subscription_id'])
                                                                        )
                    
                    ubytes = int(allocation.utilised_bytes)
                    print(f"Utilised bytes: {ubytes}")
                except Exception as e:
                    print(str(e))
                    print("Could not get allocation amt... skipping")
                    continue
                
                print(f"Unallocating; {sub}")
                
                try:
                
                    tx_params = TxParams(
                        gas_multiplier=1.15
                    )
                    
                    tx = self.sdk.subscriptions.Allocate(address=sub['wallet'], 
                                                         bytes=str(ubytes), 
                                                         id=sub['subscription_id'], 
                                                         tx_params=tx_params
                                                         )
                    
                    if tx.get("log", None) is not None:
                        print(tx["log"])
                        continue
                    if tx.get("hash", None) is not None:
                        tx_response = self.sdk.subscriptions.wait_for_tx(tx['hash'], timeout=30)
                        print(type(tx_response))
                        print(json.dumps(tx_response))
                    else:
                        print("Error getting tx response... Skipping...")
                        continue
                    
                        
                except grpc.RpcError as e:
                    print(e.details())
                    print("Skipping...")
                    continue
                    
                
                '''
                deallocate_cmd = self.__deallocate_cmd % (scrtxxs.sentinelhub,
                                         scrtxxs.WalletName,
                                         scrtxxs.RPC,
                                         scrtxxs.KeyringDIR,
                                         scrtxxs.CHAINID,
                                         sub['subscription_id'],
                                         sub['wallet'])
                
                print(deallocate_cmd)
                
                try: 
                    ofile = open(self.__unsubLog, 'ab+')                    
                    child = pexpect.spawn(deallocate_cmd)
                    child.logfile = ofile
                    
                    child.expect("Enter .*")
                    child.sendline(scrtxxs.HotWalletPW)
                    child.expect(pexpect.EOF)
                    
                    
                    ofile.flush()
                    ofile.close()
                except Exception as e:
                    print(f'ERROR UNSUBING: {str(e)}')
                    continue
                '''
                print("Setting sub to inactive...")
                self.update_sub_table(sub,db)
                sleep(10)                   
        print("Done.")        
                
                
if __name__ == "__main__":
    Unsub = PurgeExpiredSubs()
    db = Unsub.connDB()
    subs_table = Unsub.get_subscription_table(db)
    Unsub.deactivate_expired_subscriptions(db, subs_table)
        
        