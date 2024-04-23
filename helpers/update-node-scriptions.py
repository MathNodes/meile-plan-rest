#!/bin/env python3

import scrtxxs
from urllib.parse import urlparse
from datetime import datetime
from sentinel_sdk.sdk import SDKInstance
from sentinel_sdk.types import PageRequest
import json
import argparse
import pymysql
import sys

UUID = ""
VERSION = 20240423.0019
GRPC = scrtxxs.GRPC_MN

class UpdateNodeScriptions():
    
    def __init__(self):
        #private_key = self.keyring.get_password("meile-plan", self.wallet_name)
        
        #grpcaddr, grpcport = urlparse(scrtxxs.GRPC).netloc.split(":")
        grpcaddr, grpcport = urlparse(GRPC).netloc.split(":")
        
        self._sdk = SDKInstance(grpcaddr, int(grpcport), ssl=True)
        self._db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
    
    def qs_on_plan(self, nodes):
        subscriptions = self._sdk.subscriptions.QuerySubscriptionsForAccount(address=scrtxxs.WalletAddress, pagination=PageRequest(limit=1000))
        
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
        SubsNodesInfo.pop(0)
        
        node_subs_on_plan = []
        
        for s in SubsNodesInfo:
            for n in nodes:
                if n == s['Node']:
                    print(f"[uns]: node: {n} is on plan and is subscribed")
                    node_subs_on_plan.append(s)
                    
                    
        return node_subs_on_plan
        
    def GetNodesOnPlan(self, uuid):    
        query = f"SELECT node_address FROM plan_nodes WHERE uuid = '{uuid}';"
        
        c = self._db.cursor()
        c.execute(query)
        
        nodes = []
        
        for node in c.fetchall():
            nodes.append(node['node_address'])
            
        return nodes

    def UpdateSubsExpiration(self, subs, uuid):
        
        c = self._db.cursor()
        
        query = f"SELECT * FROM meile_plans WHERE uuid = '{uuid}';"
        
        c.execute(query)
        plan_data = c.fetchone()
        
        for s in subs:
            q = '''
            REPLACE INTO plan_node_subscriptions (node_address, uuid, plan_id, plan_subscription_id, node_subscription_id, deposit, hours, inactive_date)
            VALUES ("%s", "%s", %d, %d, %d, "%s", %d, "%s");
            ''' % (s['Node'],
                   uuid,
                   int(plan_data['plan_id']),
                   int(plan_data['subscription_id']),
                   int(s['ID']),
                   s['Deposit'],
                   int(s['Hours']),
                   str(s['Inactive Date']))
            
            c.execute(q)
            print(f"[uns]: {q}")
            self._db.commit()
        
        
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Meile Plan Sub Updater - v0.3 - freQniK")
    parser.add_argument('--uuid', help="--uuid <uuid> , plan uuid", metavar="uuid")
    
    args = parser.parse_args()
    
    if not args.uuid:
        parser.print_help()
        sys.exit(1)
        
    
    uns = UpdateNodeScriptions()
    print("[uns]: Getting Nodes on Plan...")    
    nodes = uns.GetNodesOnPlan(args.uuid)
    print(f"[uns]: {nodes}")
    print("[uns]: Querying subscriptions of nodes on plan...")
    subs_on_plan = uns.qs_on_plan(nodes)
    print("[uns]: Updating node inactive date on plan in database...")
    uns.UpdateSubsExpiration(subs_on_plan, args.uuid)