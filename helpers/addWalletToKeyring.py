from keyrings.cryptfile.cryptfile import CryptFileKeyring
from bip_utils import Bip39SeedGenerator, Bip44, Bip44Coins
from Crypto.Hash import RIPEMD160
from os import path

import ecdsa
import hashlib
import bech32
import scrtxxs

VERSION = 20250328.1755

class AddToKeyring():
    def __init__(self, keyring_passphrase, wallet_name, seed_phrase = None):
        self.wallet_name = wallet_name
        
        if seed_phrase:
            seed_bytes = Bip39SeedGenerator(seed_phrase).Generate()
            bip44_def_ctx = Bip44.FromSeed(seed_bytes, Bip44Coins.COSMOS).DeriveDefaultPath()
            privkey_obj = ecdsa.SigningKey.from_string(bip44_def_ctx.PrivateKey().Raw().ToBytes(), curve=ecdsa.SECP256k1)
            pubkey  = privkey_obj.get_verifying_key()
            s = hashlib.new("sha256", pubkey.to_string("compressed")).digest()
            r = self.ripemd160(s)
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
    
    def ripemd160(self, contents: bytes) -> bytes:
        """
        Get ripemd160 hash using PyCryptodome.
    
        :param contents: bytes contents.
    
        :return: bytes ripemd160 hash.
        """
        h = RIPEMD160.new()
        h.update(contents)
        return h.digest()