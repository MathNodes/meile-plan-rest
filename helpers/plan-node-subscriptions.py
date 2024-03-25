#!/bin/env python3

'''
Run in a crontab:
* * * * * cmd
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
    
    def ComputeResub(self, plan_nodes):
        now = datetime.now()
        
        resub_nodes = []
        resub_plan_nodes = {}
        
        now_plus_30 = now + timedelta(days=30)
        
        for n in plan_nodes:
            if n['inactive_date'] < now_plus_30:
                resub_nodes.append(n['node_address'])
                resub_plan_nodes[n['uuid']] = resub_nodes
        return resub_plan_nodes
    
    def subscribe_to_nodes_for_plan(self, nodeaddress, duration):
        
        private_key = self.keyring.get_password("meile-plan", self.wallet_name)
        
        grpcaddr, grpcport = urlparse(scrtxxs.GRPC).netloc.split(":")
        
        sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key)
        
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
    
        tx = sdk.nodes.SubscribeToNode(
            node_address=nodeaddress,
            gigabytes=0,  # TODO: review this please
            hours=int(duration),  # TODO: review this please
            denom="udvpn",
            tx_params=tx_params,
        )
        
        if tx.get("log", None) is not None:
            return(False, tx["log"])

        if tx.get("hash", None) is not None:
            tx_response = sdk.nodes.wait_transaction(tx["hash"])
            print(tx_response)
            subscription_id = search_attribute(
                tx_response, "sentinel.node.v2.EventCreateSubscription", "id"
            )
            if subscription_id:
                return (True,subscription_id)

        return(False, "Tx error")
    
if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser(description="Meile Plan Subscriber - v0.2 - freQniK")
    
    #parser.add_argument('--file', help="--file <nodefile>, absolute path of a list of sentnode... addresses separated by newline", metavar="file")
    parser.add_argument('--seed', action='store_true',help='set if you are specifying a seedphrase', default=False)
    
    args = parser.parse_args()
    
    if args.seed:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, scrtxxs.WalletSeed)
    else:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, None)
    
        
    resub_plan_nodes = ps.ComputeResub(ps.GetPlanNodes())
    uuids = ''
    for plan,nodes in resub_plan_nodes.items():
        uuids = ','.join([uuids,plan])
        for n in nodes:
            print(f"Subscribing to {n} for {scrtxxs.HOURS} hour(s) on plan {plan}...")
            #response = ps.subscribe_to_nodes_for_plan(n, scrtxxs.HOURS)
            #print(response)
    
    # Run db updater script with UUIDs
    uuids = uuids.split(',')[1:]
    print(uuids)
    for uuid in uuids:
        update_cmd = f"{scrtxxs.HELPERS}/update-node-scriptions.py --uuid  {uuid}"
    
        proc1 = Popen(update_cmd, shell=True)
        proc1.wait(timeout=30)

        proc_out,proc_err = proc1.communicate()