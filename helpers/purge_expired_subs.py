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

VERSION = 20241124.1758

class PurgeExpiredSubs():
    
    def __init__(self):
        unsubLog = path.join(scrtxxs.LogDIR, "meile_unsub.log")
        self.LOGFILE = open(unsubLog, "a+")
        
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
        self.LOGFILE.write(f"-----------------------------{NOW}-------------------------------------\n")
        self.LOGFILE.write("[pes]: Removing Allocations...\n")        
        for sub in subs_table:
            if sub['expires'] < NOW:
                self.LOGFILE.write(f"[pes]: ({sub['wallet']}) Querying allocation...\n")
                
                try:
                    allocation = self.sdk.subscriptions.QueryAllocation(address=sub['wallet'], 
                                                                        subscription_id=int(sub['subscription_id'])
                                                                        )
                    
                    ubytes = int(allocation.utilised_bytes)
                    self.LOGFILE.write(f"({sub['wallet']}) Utilised bytes: {ubytes}\n")
                except Exception as e:
                    self.LOGFILE.write(f"{str(e)}\n")
                    self.LOGFILE.write("Could not get allocation amt... skipping\n")
                    continue
                
                self.LOGFILE.write(f"[pes]: Unallocating; {sub}\n")
                
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
                        self.LOGFILE.write(f"{tx['log']}\n")
                        continue
                    if tx.get("hash", None) is not None:
                        tx_response = self.sdk.subscriptions.wait_for_tx(tx['hash'], timeout=30)
                        self.LOGFILE.write(f"[pes]: {json.dumps(tx_response)}\n")
                    else:
                        self.LOGFILE.write("[pes]: Error getting tx response... Skipping...\n")
                        continue
                    
                        
                except grpc.RpcError as e:
                    print(e.details())
                    self.LOGFILE.write("[pes]: GRPC Error...Skipping...\n")
                    continue
                    
                self.LOGFILE.write(f"[pes]: ({sub['wallet']}) Setting sub to inactive...\n")
                self.update_sub_table(sub,db)
                sleep(10)                   
        self.LOGFILE.write("[pes]: Done.\n")
        self.LOGFILE.flush()
        self.LOGFILE.close()        
                
                
if __name__ == "__main__":
    Unsub = PurgeExpiredSubs()
    db = Unsub.connDB()
    subs_table = Unsub.get_subscription_table(db)
    Unsub.deactivate_expired_subscriptions(db, subs_table)
        
        cmd)
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
        
        