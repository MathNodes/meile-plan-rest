#!/bin/env python3

from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import TxParams
from sentinel_sdk.utils import search_attribute
from keyrings.cryptfile.cryptfile import CryptFileKeyring
from urllib.parse import urlparse
import ecdsa
import hashlib
import bech32
from os import path, getcwd

import argparse
import getpass
import json
import sys
from datetime import date, datetime
from time import sleep
from copy import deepcopy
import scrtxxs

#GRPC = "https://grpc.mathnodes.com:443"
#GRPC = "https://grpc.ungovernable.dev:443"
GRPC = scrtxxs.GRPC_BLUEFREN


class Unsubscribe():
    
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
        
        private_key = self.keyring.get_password("meile-plan", self.wallet_name) 
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        self.sdk = SDKInstance(grpcaddr, int(grpcport), secret=private_key, ssl=True)
        
    def __keyring(self, keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr  
    
    
    def unsubscribe(self, id):
        
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
        
        tx = self.sdk.subscriptions.Cancel(id=id, tx_params=tx_params)
        
        if tx.get("log", None) is not None:
            return(False, tx["log"])
        
        if tx.get("hash", None) is not None:
            tx_response = self.sdk.subscriptions.wait_transaction(tx["hash"])
            print(tx_response)
            return(True, tx['hash'])
        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Meile Plan Subscriber - v0.2 - freQniK")
    parser.add_argument('--seed', action='store_true',help='set if you are specifying a seedphrase', default=False)
    parser.add_argument('--file', help="--file <file.json>, absolute path of a list of subscriptions", metavar="file")
    
    args = parser.parse_args()
    
    if args.file:
        with open(args.file, "r") as sub_file:
            data = json.loads(sub_file.read())
            #print(data)
    else:
        parser.print_help()
        sys.exit(1)
    
    if args.seed:
        seed = getpass.getpass("Seed Phrase:")
        unsub = Unsubscribe(keyring_passphrase=scrtxxs.HotWalletPW, wallet_name=scrtxxs.WalletName, seed_phrase=seed)
    else:
        unsub = Unsubscribe(keyring_passphrase=scrtxxs.HotWalletPW, wallet_name=scrtxxs.WalletName)
    
    unsub_date = datetime.strptime("2024-07-28 17:00:02.000000", "%Y-%m-%d %H:%M:%S.%f")
    print(type(unsub_date))
    k=0
    prev_sub = ""
    for sub in data:
        #if k == 0:
        #    k += 1
        #    continue
        if prev_sub == sub["Node"] and sub['Node'] != "":
            if datetime.strptime(sub['Inactive Date'], "%Y-%m-%d %H:%M:%S.%f") > unsub_date and sub['Status'] == "active":
                print(f"Inactive Date: {sub['Inactive Date']}, id: {sub['ID']}")
                print("unsubscribing...")
                response = unsub.unsubscribe(int(sub['ID']))
                if response[0]:
                    print("Successful.")
                else:
                    print("Failed")
                k += 1
                sleep(20)
            else:
                print("Sub not active or invalid date")
        else:
            print(f"prev: {prev_sub},\ncur : {sub['Node']}")
            print("Not a duplicate... Skipping...")
        prev_sub = deepcopy(sub["Node"])