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
GRPC = scrtxxs.GRPC_DEV
SSL = True
VERSION = 20250713.2053

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

    
    def subscribe_to_nodes_for_plan(self, nodeaddress, duration=0, GB=0):
        error_message = "NotNone"
        
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
        
        try: 
            tx = self.sdk.nodes.SubscribeToNode(
                node_address=nodeaddress,
                gigabytes=int(GB),  # TODO: review this please
                hours=int(duration),  # TODO: review this please
                denom="udvpn",
                tx_params=tx_params,
            )
            
            if tx.get("log", None) is not None:
                return(False, tx["log"])
    
            if tx.get("hash", None) is not None:
                tx_response = self.sdk.nodes.wait_transaction(tx["hash"])
                print(tx_response)
                subscription_id = search_attribute(
                    tx_response, "sentinel.node.v2.EventCreateSubscription", "id"
                )
                if subscription_id:
                    sleep(4)
                    try:
                        sub = self.sdk.QuerySubscription(subscription_id=int(subscription_id))
                        inactive_at = datetime.fromtimestamp(sub.base.inactive_at.seconds).strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(str(e))
                        now = datetime.now()
                        inactive_at = now + timedelta(hours=scrtxxs.HOURS)
                        inactive_at = inactive_at.strftime('%Y-%m-%d %H:%M:%S')
                        
                    self.UpdateNodePlanDB(nodeaddress, inactive_at)
                        
                    return (True, subscription_id)
    
            return(False, "Tx error")
        except grpc.RpcError as e:
            print(e.details())
            
            
    def UpdateNodePlanDB(self, nodeaddress, inactive_at):
        c = self._db.cursor()
        
        q = '''
            UPDATE plan_node_subscriptions SET inactive_date = '%s' WHERE node_address = '%s';
            ''' % (inactive_at, nodeaddress)
                
        print(f"[pns]: {q}")
        c.execute(q)
        self._db.commit()
            

    def add_node_to_plan(self, plan_id, node):
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
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
            print(f"[pns]: Subscribing to {n} for {scrtxxs.HOURS} hour(s) on plan {args.uuid}...")
            response = ps.subscribe_to_nodes_for_plan(n, duration=scrtxxs.HOURS)
            print(response)
            print("[pns]: Waiting 5s...")
            sleep(5)
            print(f"[pns]: Adding {n} to plan {plan_id},{args.uuid}...")
            for pid in plan_id:
                ps.add_node_to_plan(pid, n)
            
            
        for uuid in args.uuid.split(','):
            print("[pns]: Inserting nodes in plan DB...", end='')    
            run_insert(args.file, uuid)
            sleep(2)
            print("[pns]: Done.")
            print("[pns]: Wainting...")
            sleep(20)
            print("[pns]: Updating plan_node_subscriptions...")
            run_update(uuid)
            print("[pns]: Done.")    
            
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
                    
                print(f"[pns]: Subscribing to {n} for {scrtxxs.HOURS} hour(s) on plan {plan}...")
                response = ps.subscribe_to_nodes_for_plan(n, duration=scrtxxs.HOURS)
                print(f"[pns]: {response}")
                print(f"[pns]: Linking {n} to plan {plan_id}...")
                for pid in plan_id:
                    ps.add_node_to_plan(pid, n)
        
        print("[pns]: Waiting....")
        sleep(10)
        # Run db updater script with UUIDs
        uuids = uuids.split(',')[1:]
        print(f"[pns]: uuids: {uuids}")
        for uuid in uuids:
            print(f"[pns]: Updating node subs for plan {uuid}...", end='')
            run_update(uuid)
            sleep(2)
            print("[pns]: Done.")
            