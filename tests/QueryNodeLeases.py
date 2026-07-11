#!/bin/env python3

import scrtxxs
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import PageRequest
import sys



GRPC = scrtxxs.GRPC_DEV
PROVIDER="sentprov1mrqc5hzdp7gttvrylqu060cevgfx2kaa9lh7a7"


class Leases():
    
    def __init__(self):
        #private_key = self.keyring.get_password("meile-plan", self.wallet_name)
        
        #grpcaddr, grpcport = urlparse(scrtxxs.GRPC).netloc.split(":")
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        self.sdk = SDKInstance(grpcaddr, int(grpcport), ssl=True)
        
        
    def QueryLeases(self):
        
        leases = self.sdk.lease.QueryProviderLeases(address=PROVIDER)
        print(leases)
        
        
if __name__ == "__main__":
    l = Leases()
    l.QueryLeases()
        