#!/bin/env python3

'''
Run in a crontab:
0 * * * * cmd
'''


import argparse
import scrtxxs
from urllib.parse import urlparse
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute
from sentinel_protobuf.sentinel.types.v1.price_pb2 import Price
from sentinel_protobuf.sentinel.types.v1.renewal_pb2 import RenewalPricePolicy
from keyrings.cryptfile.cryptfile import CryptFileKeyring
import ecdsa
import hashlib
import bech32
from os import path, getcwd
import pymysql
from datetime import datetime,timedelta
from subprocess import Popen
from time import sleep
import requests
import grpc

MNAPI = "https://api.sentinel.mathnodes.com"
NODEAPI = "/sentinel/node/v3/nodes/%s"
GRPC = scrtxxs.GRPC_DEV
SSL = True
VERSION = 20251029.1707

class V12Migration():
    def __init__(self, keyring_passphrase, wallet_name, seed_phrase = None):
        self.wallet_name = wallet_name
        
        if seed_phrase:
            seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
            bip44_def_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.COSMOS).DeriveDefaultPath()
            privkey_obj = ecdsa.SigningKey.from_string(bip44_def_ctx.PrivateKey().Raw().ToBytes(), curve=ecdsa.SECP256k1)
            pubkey  = privkey_obj.get_verifying_key()
            s = hashlib.new("sha256", pubkey.to_string("compressed")).digest()
            r = hashlib.new("ripemd160", s).digest()
            five_bit_r = bech32.convertbits(r, 8, 5)
            account_address = bech32.bech32_encode("sent", five_bit_r)
            print(account_address)
            self.keyring = self.__keyring(keyring_passphrase)
            self.keyring.set_password("meile-plan", wallet_name, bip44_def_ctx.PrivateKey().Raw().ToBytes().hex())
        else:
            self.keyring = self.__keyring(keyring_passphrase)
        
        self._db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
        private_key = self.keyring.get_password("meile-plan", self.wallet_name)
        
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        
        self.sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=SSL)
        
        
    def __keyring(self, keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr   
    
    def GetActiveSubscribers(self):
        
        c = self._db.cursor()
        q = "SELECT * FROM meile_subscriptions WHERE active = 1;"
        c.execute(q)
        
        return c.fetchall()
    
    def ShareSubscriptionWithActiveSubscribers(self, active_subscribers):
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
        for subscriber in active_subscribers:
            wallet = subscriber['wallet']
            plan_id = subscriber['plan_id']
            
            tx = self.sdk.subscriptions.StartSubscription(plan_id=plan_id,
                                                     denom="udvpn",
                                                     renewal=RenewalPricePolicy.RENEWAL_PRICE_POLICY_IF_LESSER_OR_EQUAL
                                                     )
            if tx.get("log", None) is not None:
                return(False, tx["log"])
            
            if tx.get("hash", None) is not None:
                tx_response = self.sdk.subscriptions.wait_transaction(tx["hash"])
                print(tx_response)
                sub_id = search_attribute(
                    tx_response, "sentinel.subscription.v3.EventCreate", "subscription_id"
                )
                print(f"Subscription ID: {sub_id}")
              
            sleep(3)
            tx = self.sdk.subscriptions.ShareSubscription(subscription_id=int(sub_id),
                                                     wallet_address=wallet,
                                                     bytes=str(scrtxxs.BYTES_50))
            
            if tx.get("log", None) is not None:
                return(False, tx["log"])
            
            if tx.get("hash", None) is not None:
                tx_response = self.sdk.subscriptions.wait_transaction(tx["hash"])
                print(tx_response)
                granted_bytes = search_attribute(
                    tx_response, "sentinel.subscription.v3.EventAllocate", "granted_bytes"
                )
                print(f"Granted Bytes: {granted_bytes}")
                
            answer = input(f"Update table for {wallet} (Y/n):")
            if answer.upper() == "Y":
                self.UpdateSubscriberTable(wallet,int(sub_id))
            

    def UpdateSubscriberTable(self, wallet, sub_id: int):
        c = self._db.cursor()
        
        query = 'UPDATE meile_subscriptions SET subscription_id = %d, expires = NOW() + INTERVAL 35 DAY WHERE wallet = "%s";' % (sub_id, wallet)
        c.execute(query)
        self._db.commit()
        
if __name__ == "__main__":
    v12 = V12Migration(scrtxxs.HotWalletPW, scrtxxs.WalletName, None)
    v12.ShareSubscriptionWithActiveSubscribers(v12.GetActiveSubscribers())
        
            
            
        
        
        