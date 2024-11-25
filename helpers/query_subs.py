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
    subscriptions = _sdk.subscriptions.QuerySubscriptionsForAccount(address=WalletAddress, pagination=PageRequest(limit=1000))
    
    SubsNodesInfo = [{
        'Denom': "",  # TODO: (?)
        'Deposit': f"{subscription.deposit.amount}{subscription.deposit.denom}",
        'Gigabytes': f"{subscription.gigabytes}",
        'Hours': f"{subscription.hours}",
        'ID': f"{subscription.base.id}",
        'Inactive Date': datetime.fromtimestamp(subscription.base.inactive_at.seconds).strftime('%Y-%m-%d %H:%M:%S.%f'), # '2024-03-26 19:37:52.52297981',
        'Node': subscription.node_address,
        'Owner': subscription.base.address,
        'Plan': '0',  # TODO: (?)
        'Status': ["unspecified", "active", "inactive_pending", "inactive"][subscription.base.status],
    } for subscription in subscriptions]
    
    
    print(SubsNodesInfo)
    
    
qs()