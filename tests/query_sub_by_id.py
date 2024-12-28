#!/bin/env python3

from urllib.parse import urlparse
from datetime import datetime
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import PageRequest

#GRPC = "https://grpc.bluefren.xyz:443"
GRPC = "https://grpc.bluefren.xyz:9090"
#GRPC = "https://grpc.mathnodes.com:443"
#GRPC = "http://grpc.dvpn.me:9090"
#GRPC = "http://grpc.mathnodes.com:9000"
#GRPC = "https://grpc.noncompliant.network:443"
#GRPC = "http://noncompliant.network:9090"
#SSL = True
SSL = False
WalletAddress = "sent1mrqc5hzdp7gttvrylqu060cevgfx2kaadgt9xx"
#WalletAddress = "sent1d2ps3wvk6yzkachaden4rk7faccvq59937h2te"
def qs():
    grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
    _sdk = SDKInstance(grpcaddr, int(grpcport), ssl=SSL)
    sub = _sdk.subscriptions.QuerySubscription(subscription_id=765206)
    inactive_at = datetime.fromtimestamp(sub.base.inactive_at.seconds).strftime('%Y-%m-%d %H:%M:%S')
    print(sub)
    print(inactive_at)
    
    
    now = datetime.now()
    if datetime.strptime(inactive_at, '%Y-%m-%d %H:%M:%S') > now:
        print("IT WORKED!")
qs()
