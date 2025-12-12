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
import subprocess
import json


MNAPI = "https://api.sentinel.mathnodes.com"
NODEAPI = "/sentinel/node/v3/nodes/%s"
GRPC = scrtxxs.GRPC_DEV
SSL = True
VERSION = 20251211.2234

class PlanSubscribe():
    
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
    
    def GetPlanNodes(self):
        
        c = self._db.cursor()
        q = "SELECT * FROM plan_node_subscriptions;"
        c.execute(q)
        
        return c.fetchall()
    
    def GetPlanID(self, uuid):
        c = self._db.cursor()
        q = f"SELECT plan_id FROM meile_plans WHERE uuid = '{uuid}';"
    
        c.execute(q)
        
        return c.fetchone()
                  
    def ComputeResub(self, plan_nodes):
        now = datetime.now()
        
        unique_uuids = {n['uuid'] for n in plan_nodes}
        resub_plan_nodes = {uuid: [] for uuid in unique_uuids}
        
        for n in plan_nodes:
            if n['inactive_date'] < now:
                for key in resub_plan_nodes.keys():
                    if key == n['uuid']:
                        resub_plan_nodes[key].append(n['node_address'])

        
        resub = self.__remove_duplicates(resub_plan_nodes)
        return resub
    
    def __remove_duplicates(self, test):
        for key in test:
            print(f"[pns]: plan: {key}, subs: {test[key]}")
            test[key] = [item for item in test[key] if sum(item in test[other_key] for other_key in test if other_key != key) == 0]
            test[key] = list(set(test[key]))
        
        return test

    
    def subscribe_to_nodes_for_plan(self, 
                                    nodeaddress, 
                                    base_value: str, 
                                    quote_value: str, 
                                    duration=0, 
                                    GB=0, 
                                    uuids: list() = [], 
                                    plans: list() = []):
        error_message = "NotNone"
        
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
        
        try: 
            # temporary
            price = Price(
                denom="udvpn",
                base_value=base_value,
                quote_value=quote_value
                )
            tx = self.sdk.lease.StartLease(
                node=nodeaddress.rstrip(),
                hours=scrtxxs.HOURS,
                max_price=price,
                renewal=RenewalPricePolicy.RENEWAL_PRICE_POLICY_IF_LESSER_OR_EQUAL
            )
            
            print(tx_params)
            
            if tx.get("log", None) is not None:
                return(False, tx["log"])
            
            if tx.get("hash", None) is not None:
                tx_response = self.sdk.nodes.wait_transaction(tx["hash"])
                print(tx_response)
                lease_id = search_attribute(
                    tx_response, "sentinel.lease.v1.EventCreate", "lease_id"
                )
                now = datetime.now()
                inactive_at = now + timedelta(hours=scrtxxs.HOURS)
                if self.QueryDBSubscriptions(nodeaddress):
                    self.UpdateNodePlanDB(nodeaddress.rstrip(), lease_id, inactive_at)
                    
                else:
                    self.InsertNodeInDB(uuids, 
                                        plans, 
                                        str(scrtxxs.HOURS*int(quote_value)) + "udvpn", 
                                        scrtxxs.HOURS,
                                        lease_id,
                                        inactive_at,
                                        nodeaddress.rstrip())
                    
                return (True, lease_id)
                
            '''
                if subscription_id:
                    sleep(4)
                    try:
                        sub = self.sdk.subscriptions.QuerySubscription(subscription_id=int(subscription_id))
                        inactive_at = datetime.fromtimestamp(sub.base.inactive_at.seconds).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(str(e))
                        now = datetime.now()
                        inactive_at = now + timedelta(hours=scrtxxs.HOURS)
                        inactive_at = inactive_at.strftime('%Y-%m-%d %H:%M:%S')
            '''
    
            return(False, "Tx error")
        except grpc.RpcError as e:
            print(e.details())
            
    def InsertNodeInDB(self,uuids,plans,deposit, hours, lease_id, inactive_at, nodeaddress):
        c = self._db.cursor()
        for uuid, plan in zip(uuids,plans):
            q = '''
                INSERT IGNORE INTO plan_nodes (uuid, node_address)
                VALUES ("%s", "%s");
                ''' % (uuid, nodeaddress)
                
            print(q)
            c.execute(q)
            self._db.commit()
            
            q = '''
                INSERT IGNORE INTO plan_node_subscriptions (node_address,uuid,plan_id,plan_subscription_id,node_subscription_id,deposit,hours,inactive_date)
                VALUES ("%s", "%s", %d, %d, %d, "%s", %d, "%s")
                ''' % (nodeaddress, uuid,int(plan),0, int(lease_id), deposit, hours, str(inactive_at))
            print(q)
            c.execute(q)
            self._db.commit()
                
    def QueryDBSubscriptions(self, nodeaddress): 
        c = self._db.cursor()
        query = "SELECT * from plan_node_subscriptions WHERE node_address = '%s';" % (nodeaddress)
        c.execute(query)
        result = c.fetchall()
        return bool(result)
        
               
    def UpdateNodePlanDB(self, nodeaddress, lease_id, inactive_at):
        c = self._db.cursor()
        
        q = '''
            UPDATE plan_node_subscriptions SET inactive_date = '%s', node_subscription_id = '%s' WHERE node_address = '%s';
            ''' % (inactive_at, lease_id, nodeaddress)
                
        print(f"[pns]: {q}")
        c.execute(q)
        self._db.commit()
            

    def add_node_to_plan(self, plan_id, node):
        tx_params = TxParams(
            gas_multiplier=1.15
        )
        
        
        tx = self.sdk.plans.LinkNode(
            plan_id=plan_id,
            node_address=node
            )
        
        if tx.get("log", None) is not None:
            return (False, tx["log"])
            

        if tx.get("hash", None) is not None:
            tx_response = self.sdk.nodes.wait_transaction(tx["hash"])
            print(tx_response)
            return (True, None)

        return (False,"Tx error")
    
    def get_price_of_node(self, node):
        result = self.sdk.nodes.QueryNode(address=node)
        
        k = 0
        for gb_price in result.gigabyte_prices:
            if "udvpn" == gb_price.denom:
                break
            else:
                k += 1
        
        if k > len(result.gigabyte_prices) - 1:
            print(f"No proper denomination found!")
            return {"success" : False, "base_value" : None, "quote_value" : None}
        
        
        base_value = result.hourly_prices[k].base_value
        quote_value = result.hourly_prices[k].quote_value
        
        return {"success" : True, "base_value" : base_value, "quote_value" : quote_value}
        

'''
def run_update(uuid):
    update_cmd = f"{scrtxxs.HELPERS}/update-node-scriptions.py --uuid  {uuid}"
    
    proc1 = Popen(update_cmd, shell=True)
    proc1.wait(timeout=30)

    proc_out,proc_err = proc1.communicate()

def run_insert(node_file, uuid):
    
    update_cmd = f"{scrtxxs.HELPERS}/insert-nodes.py --uuid  {uuid} --file {node_file}"
    
    proc1 = Popen(update_cmd, shell=True)
    proc1.wait(timeout=30)

    proc_out,proc_err = proc1.communicate()
'''
    
     
if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser(description="Meile Plan Subscriber - v0.3 - freQniK")
    
    parser.add_argument('--file', help="--file <nodefile>, absolute path of a list of sentnode... addresses separated by newline", metavar="file")
    parser.add_argument('--seed', action='store_true',help='set if you are specifying a seedphrase', default=False)
    parser.add_argument('--uuid', help="--uuid <uuid1,uuid2...>, uuid of plan(s) to subscribe nodes to", metavar="uuid")
    args = parser.parse_args()
    
    if args.seed:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, scrtxxs.WalletSeed)
    else:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, None)
    
    if args.file and args.uuid:
        plan_id = []
        for uuid in args.uuid.split(','):
            plan_id.append(ps.GetPlanID(uuid)['plan_id'])
            
        with open(args.file, 'r') as nodefile:
            nodes = nodefile.readlines()
            
        for n in nodes:
            prices = ps.get_price_of_node(node=n)
            
            if not prices['success']:
                continue
                
            base_value = int(float(prices['base_value']) * 10**18)
            quote_value = int(prices['quote_value'])
                
            print(f"base_value = {base_value}")
            print(f"quote_value = {quote_value}")
            print(f"[pns]: Subscribing to {n} for {scrtxxs.HOURS} hour(s) on plan {args.uuid}...")
            response = ps.subscribe_to_nodes_for_plan(n, 
                                                      base_value=str(base_value), 
                                                      quote_value=str(quote_value), 
                                                      duration=scrtxxs.HOURS, 
                                                      uuids=args.uuid.split(','), 
                                                      plans=plan_id)
            print(response)
            print("[pns]: Waiting 5s...")
            sleep(5)
            print(f"[pns]: Adding {n} to plan {plan_id},{args.uuid}...")
            for pid in plan_id:
                try: 
                    ps.add_node_to_plan(pid, n)
                except Exception as e:
                    print(str(e))
                    
  
    else:
        plan_id = []
        print("[pns]: Computing Resubscriptions...")
        resub_plan_nodes = ps.ComputeResub(ps.GetPlanNodes())
        print(f"[pns]: {resub_plan_nodes}")
        
        uuids = ''
        for plan,nodes in resub_plan_nodes.items():
            uuids = ','.join([uuids,plan])
            for uuid in uuids.split(',')[1:]:
                plan_id.append(ps.GetPlanID(uuid)['plan_id'])
            
            for n in nodes:
                print(f"[pns]: Checking if {n} is active...")
                try: 
                    resp = requests.get(MNAPI + NODEAPI % n)
                    nodeJSON = resp.json()
                    
                    if nodeJSON['node']['status'] == "inactive":
                        print("[pns]: Node is inactive, skipping...")
                        continue
                except Exception as e:
                    print(str(e))
                    pass
                
                prices = ps.get_price_of_node(node=n)
            
                if not prices['success']:
                    continue
                    
                base_value = int(float(prices['base_value']) * 10**18)
                quote_value = int(prices['quote_value'])
                    
                print(f"base_value = {base_value}")
                print(f"quote_value = {quote_value}")
                                    
                print(f"[pns]: Subscribing to {n} for {scrtxxs.HOURS} hour(s) on plan {plan}...")
                response = ps.subscribe_to_nodes_for_plan(n,
                                                          base_value=str(base_value), 
                                                          quote_value=str(quote_value), 
                                                          duration=scrtxxs.HOURS, 
                                                          uuids=uuids.split(',')[1:], 
                                                          plans=plan_id)
                print(f"[pns]: {response}")
                plan_id = list(set(plan_id))
                print(f"[pns]: Linking {n} to plan {plan_id}...")
                for pid in plan_id:
                    try:
                        ps.add_node_to_plan(pid, n)
                    except Exception as e:
                        print(str(e))
                sleep(2)
       