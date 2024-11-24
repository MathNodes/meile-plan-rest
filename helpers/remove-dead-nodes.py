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
NODEAPI = "/sentinel/nodes/%s"
GRPC = scrtxxs.GRPC_MN
SSL = True
VERSION = 20241124.1847

class WinstonWolfeNodes():
    
    def __init__(self, keyring_passphrase, wallet_name, seed_phrase = None):
        self.wallet_name = wallet_name
        
        unsubLog = path.join(scrtxxs.LogDIR, "remove-dead-nodes.log")
        self.LOGFILE = open(unsubLog, "a+")
        NOW = datetime.now()
        self.LOGFILE.write(f"----------------------------------{NOW}-------------------------------------\n")
        
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
        
    def QueryCorpseNodesInPlan(self):
        
        query = "SELECT * FROM plan_node_subscriptions WHERE inactive_date < NOW() - INTERVAL 7 DAY;"
        
        c = self._db.cursor()
        c.execute(query)
        
        return c.fetchall()
    
    def RemoveCorpseNodesFromPlan(self, deadnodes):
        
        removed_nodes = []
        node = {}
        
        tx_params = TxParams(
            gas_multiplier=1.15
        )
        
        for dn in deadnodes:
            node = {}
            node['uuid'] = dn['uuid']
            node['address'] = dn['node_address']
            
            try:
                self.LOGFILE.write(f"[rdn]: Removing {dn['node_address']} from plan {dn['plan_id']}, uuid {dn['uuid']}...\n")
                
                tx = self.sdk.plans.UnlinkNode(dn['plan_id'],
                                          dn['node_address'], 
                                          tx_params)
            
                if tx.get("log", None) is not None:
                    continue
                
                if tx.get("hash", None) is not None:
                    tx_response = self.sdk.nodes.wait_transaction(tx["hash"])
                    self.LOGFILE.write(f"[rdn]: {tx_response}\n")
                    removed_nodes.append(node)
                
            except grpc.RpcError as e:
                self.LOGFILE.write(f"[rdn]: {e.details()}\n")
                error_message = e.details()
                self.LOGFILE.write(f"[rdn]: Sleeping for 15s...\n")
                sleep(15)
                continue
               
        self.LOGFILE.write(f"[rdn]: {removed_nodes}\n")
        return removed_nodes
           
    def WinstonWolfeDeadNodes(self, deadnodes):
        c = self._db.cursor()
        
        for node in deadnodes:
            uuid = node['uuid']
            address = node['address']
            query = f"DELETE FROM plan_nodes WHERE uuid = '{uuid}' AND node_address = '{address}';"
            query2 = f"DELETE FROM plan_node_subscriptions WHERE uuid = '{uuid}' AND node_address = '{address}';"
            
            self.LOGFILE.write(f"[rdn]: Removing {address} from DB...\n")
            self.LOGFILE.write(f"[rdn]: {query}\n")
            self.LOGFILE.write(f"[rdn]: {query2}\n")
            
            c.execute(query)
            self._db.commit()
            c.execute(query2)
            self._db.commit()
        self.LOGFILE.write("[rdn]: Done.\n")
        self.LOGFILE.flush()
        self.LOGFILE.close()
if __name__ == "__main__":
    wwn = WinstonWolfeNodes(scrtxxs.HotWalletPW, scrtxxs.WalletName, None)
    
    removed_nodes = wwn.RemoveCorpseNodesFromPlan(wwn.QueryCorpseNodesInPlan())
    wwn.WinstonWolfeDeadNodes(removed_nodes)
    
    
            