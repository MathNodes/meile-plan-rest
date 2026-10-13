#!/bin/env python3

from urllib.parse import urlparse
from datetime import datetime
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import PageRequest
import scrtxxs
import pymysql

MNAPI = "https://api.sentinel.mathnodes.com"
GRPC = scrtxxs.GRPC_MN
SSL = True
VERSION = 20241228.1324
WalletAddress = scrtxxs.WalletAddress

class UpdatePlanNodeExpiration():
    
    def __init__(self):
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        _sdk = SDKInstance(grpcaddr, int(grpcport), ssl=SSL)
        
        self.db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
        
        print(f"Querying subs on: {WalletAddress}...", end='')
        subscriptions = _sdk.subscriptions.QuerySubscriptionsForAccount(address=WalletAddress, pagination=PageRequest(limit=1000))
        
        self.SubsNodesInfo = [{
            'Denom': "",  # TODO: (?)
            'Deposit': f"{subscription.deposit.amount}{subscription.deposit.denom}",
            'Gigabytes': f"{subscription.gigabytes}",
            'Hours': f"{subscription.hours}",
            'ID': f"{subscription.base.id}",
            'Inactive Date': datetime.fromtimestamp(subscription.base.inactive_at.seconds).strftime('%Y-%m-%d %H:%M:%S'), # '2024-03-26 19:37:52',
            'Node': subscription.node_address,
            'Owner': subscription.base.address,
            'Plan': '0',  # TODO: (?)
            'Status': ["unspecified", "active", "inactive_pending", "inactive"][subscription.base.status],
        } for subscription in subscriptions]
        
        
        print("Done.")
    
    
    def UpdatePlanNodeTable(self):
        
        for sub in self.SubsNodesInfo:
        
            q = '''
                UPDATE plan_node_subscriptions SET inactive_date = '%s' WHERE node_address = '%s';
                ''' % (sub['Inactive Date'],
                       sub['Node'])
                
            
            print(q)
            
            c = self.db.cursor()
            c.execute(q)
            self.db.commit()
        

if __name__ == "__main__":
    upne = UpdatePlanNodeExpiration()
    upne.UpdatePlanNodeTable()
    
