#!/bin/env python3
import json
import pymysql
import scrtxxs
from datetime import datetime
import pexpect
from os import path
import requests
from time import sleep

VERSION = 20240309.1613

API_DVPN_BALANCE = "https://api.sentinel.mathnodes.com/cosmos/bank/v1beta1/balances/%s/by_denom?denom=udvpn"
SATOSHI = 1000000

keyring_passphrase = scrtxxs.HotWalletPW

class TopUpSubscribers():
    
    def __init__(self):
        self.__transfer_cmd = '%s tx bank send --gas auto --gas-prices 0.2udvpn --gas-adjustment 2.0 --yes %s %s 1000000udvpn --node "%s"' 
        
        
        
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
        
        query = "select * from meile_subscriptions where subscribe_date > '2024-03-04';"
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
            
            if balance < 0.1:
                print(f"Balance: {balance}, Sending 1dvpn to: {s['wallet']}")
                transfer_cmd = self.__transfer_cmd % (scrtxxs.sentinelhub,scrtxxs.WalletAddress,s['wallet'],scrtxxs.RPC)
                
                print(transfer_cmd)
                try: 
                    child = pexpect.spawn(transfer_cmd)
                    
                    child.expect("Enter .*")
                    child.sendline(keyring_passphrase)
                    child.expect(pexpect.EOF)    
                except Exception as e:
                    print(str(e))
                    
                sleep(6)
    
if __name__ == "__main__":
    topup = TopUpSubscribers()
    subscribers = topup.get_subscribers(topup.connDB())
    print(subscribers)
    topup.top_up(subscribers)
    