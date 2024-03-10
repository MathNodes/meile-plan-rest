#!/bin/env python3
import argparse
import scrtxxs
from urllib.parse import urlparse
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
from sentinel_protobuf.sentinel.subscription.v2.msg_pb2 import MsgCancelRequest, MsgCancelResponse

from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import NodeType, TxParams, Status
from sentinel_sdk.utils import search_attribute
from pywgkey import WgKey
from mnemonic import Mnemonic
from keyrings.cryptfile.cryptfile import CryptFileKeyring
import ecdsa
import hashlib
import bech32
from os import path
from getpass import getpass
import sys

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
        
        
    def __keyring(self, keyring_passphrase: str):
        kr = CryptFileKeyring()
        kr.filename = "keyring.cfg"
        kr.file_path = path.join(scrtxxs.PlanKeyringDIR, kr.filename)
        kr.keyring_key = keyring_passphrase
        return kr   
    
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
    
    
    parser = argparse.ArgumentParser(description="Meile Plan Subscriber - v0.1 - freQniK")
    
    parser.add_argument('--file', help="--file <nodefile>, absolute path of a list of sentnode... addresses separated by newline", metavar="file")
    parser.add_argument('--seed', action='store_true',help='set if you are specifying a seedphrase', default=False)
    
    args = parser.parse_args()
    
    if args.seed:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, scrtxxs.WalletSeed)
    else:
        ps = PlanSubscribe(scrtxxs.HotWalletPW, scrtxxs.WalletName, None)
    
    if args.file:
        with open(args.file, 'r') as nodefile:
            nodes = nodefile.readlines()
            
    else:
        sys.exit(1)
        
    for n in nodes:
        print(f"Subscribing to {n} for {scrtxxs.HOURS} hour(s)...")
        response = ps.subscribe_to_nodes_for_plan(n, scrtxxs.HOURS)
        print(response)
        
        