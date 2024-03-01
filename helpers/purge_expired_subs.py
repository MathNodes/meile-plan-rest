#!/bin/env python3
import json
import pymysql
import scrtxxs
from datetime import datetime
import pexpect
from os import path

from time import sleep

VERSION = 20240301.0001


class PurgeExpiredSubs():
    
    def __init__(self):
        self.__deallocate_cmd = '%s tx vpn subscription allocate --from "%s" --gas-prices "0.3udvpn" --node "%s" --keyring-dir "%s" --keyring-backend "file" --chain-id "%s" --yes %s "%s" 0'
        self.__unsubLog = path.join(scrtxxs.LogDIR, "meile_unsub.log")
        
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
        query = 'SELECT * FROM meile_subscriptions;'
        c.execute(query)
        
        return c.fetchall()
    
    def deactivate_expired_subscriptions(self, db, subs_table):
        NOW = datetime.now()
        
        for sub in subs_table:
            if sub['expires'] < NOW:
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
                   
                sleep(10)
                
                
if __name__ == "__main__":
    Unsub = PurgeExpiredSubs()
    db = Unsub.connDB()
    subs_table = Unsub.get_subscription_table(db)
    Unsub.deactivate_expired_subscriptions(db, subs_table)
        
        