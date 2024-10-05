#!/bin/env python3

'''crontab
14 3 * * * python3 enforce_max_price.py
'''


import scrtxxs
from urllib.parse import urlparse
from datetime import datetime
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import PageRequest
from sentinel_sdk.types import TxParams
from keyrings.cryptfile.cryptfile import CryptFileKeyring
import json
import argparse
import pymysql
import sys
import re
import grpc
from os import path

UUID = ""
VERSION = 20241004.2042
GRPC = scrtxxs.GRPC_MN
SATOSHI = 1000000
MAX_PRICE = scrtxxs.MAX_PRICE
SSL = True

class EnforceMaxPrice():
    
    def __init__(self, keyring_passphrase, wallet_name):
        #private_key = self.keyring.get_password("meile-plan", self.wallet_name)
        
        #grpcaddr, grpcport = urlparse(scrtxxs.GRPC).netloc.split(":")
        self.keyring = self.__keyring(keyring_passphrase)
        private_key = self.keyring.get_password("meile-plan", wallet_name)
        
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        
        self._sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=SSL)
        self._db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
    
    def __keyring(self, keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr 
        
    def getNodesOnPlans(self):
        
        c = self._db.cursor()
        q = "SELECT node_address FROM plan_node_subscriptions;"
        c.execute(q)
        return c.fetchall()
    
    def getNodePlanInfo(self, node):
        c = self._db.cursor()
        q = f"SELECT * FROM plan_node_subscriptions WHERE node_address = '{node}'"
        c.execute(q)
        return c.fetchone()
    
        
    def QueryNodePrice(self, nodes):
        pattern = r'(\d+)udvpn'
        
        blacklisted_nodes = []
        
        for n in nodes:
            nodeData = self._sdk.nodes.QueryNode(n['node_address'])
            result = json.loads(self._sdk.nodes.QueryNodeStatus(nodeData))
            try: 
                price = result['result']['hourly_prices']
                match = re.search(pattern, price)
    
                if match:
                    if float(int(match.group(1)) / SATOSHI) > MAX_PRICE:
                        blacklisted_nodes.append(n['node_address'])
            except:
                continue
                    
        return blacklisted_nodes
    
    
            
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
                print(f"[rdn]: Removing {dn['node_address']} from plan {dn['plan_id']}, uuid {dn['uuid']}...")
                
                tx = self._sdk.plans.UnlinkNode(dn['plan_id'],
                                          dn['node_address'], 
                                          tx_params)
            
                if tx.get("log", None) is not None:
                    continue
                
                if tx.get("hash", None) is not None:
                    tx_response = self._sdk.nodes.wait_transaction(tx["hash"])
                    print(f"[rdn]: {tx_response}")
                    removed_nodes.append(node)
                
            except grpc.RpcError as e:
                print(f"[rdn]: {e.details()}")
                error_message = e.details()
                print(f"[rdn]: Sleeping for 15s...")
                sleep(15)
                continue
               
        print(f"[rdn]: {removed_nodes}")
        return removed_nodes
           
    def WinstonWolfeDeadNodes(self, deadnodes):
        c = self._db.cursor()
        
        for node in deadnodes:
            uuid = node['uuid']
            address = node['address']
            query = f"DELETE FROM plan_nodes WHERE uuid = '{uuid}' AND node_address = '{address}';"
            query2 = f"DELETE FROM plan_node_subscriptions WHERE uuid = '{uuid}' AND node_address = '{address}';"
            
            print(f"[rdn]: Removing {address} from DB...")
            print(f"[rdn]: {query}")
            print(f"[rdn]: {query2}")
            
            c.execute(query)
            self._db.commit()
            c.execute(query2)
            self._db.commit()    
            
            
if __name__ == "__main__":
    cd = EnforceMaxPrice(scrtxxs.HotWalletPW, scrtxxs.WalletName)
    naddrs = cd.getNodesOnPlans()
    blist = cd.QueryNodePrice(naddrs)
    
    deadnodes = []
    for n in blist:
        deadnodes.append(cd.getNodePlanInfo(n))
        
    
    print(f"Exploitive nodes are: {deadnodes}")
    answer = input("Continue: (Y/n) ")
    if answer.upper() == "Y":
        removed_nodes = cd.RemoveCorpseNodesFromPlan(deadnodes)
        cd.WinstonWolfeDeadNodes(removed_nodes)
            
        
    
    