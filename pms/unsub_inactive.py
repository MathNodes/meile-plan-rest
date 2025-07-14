#!/bin/env python3

from unsubscribe import Unsubscribe
import scrtxxs
import pymysql
from sentinel_sdk.types import Status, PageRequest, TxParams
from sentinel_sdk.sdk import SDKInstance
import grpc
import requests
import pymysql
import scrtxxs
from urllib.parse import urlparse
from datetime import datetime,timedelta


'''
PlanIDs = [29,34]
GRPC = scrtxxs.GRPC_DEV

VERSION = 20250615.0000

class UnsubInactive():
    def __init__(self, unsub_class):
        self._db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
        
        self.unsub_class = unsub_class
        
    def QueryInactive(self, planid):
        plan_nodes_inactive = self.unsub_class.sdk.nodes.QueryNodesForPlan(plan_id=pid, status=Status.INACTIVE)
        
        PlanNodesInactive = [ f"{pn.address}" for pn in plan_nodes_inactive] 
        
        print(PlanNodesInactive)
        print(f'\nNodes Inactive: {len(PlanNodesInactive)}')
        
    

if __name__ == "__main__":
    unsub = Unsubscribe(keyring_passphrase=scrtxxs.HotWalletPW, wallet_name=scrtxxs.WalletName)
    
    uInactive = UnsubInactive(unsub)
    uInactive.QueryInactive(29)
'''

GRPC = scrtxxs.GRPC_DEV
MNAPI = "https://api.sentinel.mathnodes.com"
NODEAPI = "/sentinel/nodes/%s"
SSL = True

class UnsubInactive():
    def __init__(self, unsub_class):
        
        self._db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        
        self.unsub_class = unsub_class
        
    def GetPlanNodes(self):
        
        c = self._db.cursor()
        q = "SELECT * FROM plan_node_subscriptions;"
        c.execute(q)
        
        return c.fetchall()
    
    def OfflineNodes(self, plan_nodes):
        
        now = datetime.now()
        
        dayplus_resub_nodes = []
        inactive_nodes = []
        
        for n in plan_nodes:
            if n['inactive_date'] > now + timedelta(hours=24):
                dayplus_resub_nodes.append(n)
                
        for n in dayplus_resub_nodes:
            print(f"[ui]: Checking if {n['node_address']} is online...")
            try: 
                resp = requests.get(MNAPI + NODEAPI % n['node_address'])
                nodeJSON = resp.json()
                
                if nodeJSON['node']['status'] == "inactive":
                    inactive_nodes.append({'uuid': n['uuid'],
                                           'node_address' : n['node_address']
                                           })
                    
            except:
                pass
        print("Inactive Nodes: ")
        for n in inactive_nodes:
            print(n)
            
        return inactive_nodes
    
    def QuerySubscriptions(self):
        subscriptions = self.unsub_class.sdk.subscriptions.QuerySubscriptionsForAccount(address=scrtxxs.WalletAddress, pagination=PageRequest(limit=1000))
    
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
        
        
        return SubsNodesInfo
    
    def remove_node_from_plan(self, plan_id, node):
        tx_params = TxParams(
            # denom="udvpn",  # TODO: from ConfParams
            # fee_amount=20000,  # TODO: from ConfParams
            # gas=ConfParams.GAS,
            gas_multiplier=1.15
        )
        
        
        tx = self.unsub_class.sdk.plans.UnlinkNode(
            plan_id=plan_id,
            node_address=node
            )
        
        if tx.get("log", None) is not None:
            return (False, tx["log"])
            

        if tx.get("hash", None) is not None:
            tx_response = self.unsub_class.sdk.plans.wait_transaction(tx["hash"])
            print(tx_response)
            return (True, None)

        return (False,"Tx error")

    
    def get_plan_id(self, uuid):
        c = self._db.cursor()
        
        query = 'SELECT * from meile_plans WHERE uuid = "%s"' % uuid
        c.execute(query)
        
        return c.fetchone()['plan_id']
    
    def UpdatePlanNodeSubTable(self, node_address):
        c = self._db.cursor()
        now = datetime.now()
        
        query = 'UPDATE plan_node_subscriptions SET inactive_date = "%s" WHERE node_address = "%s"' % (now, node_address)
        print(query)
        c.executable(query)
        self._db.commit()
    
    def UnsubAndUnlink(self, inactive_nodes, subs):
        
        for inodes in inactive_nodes:
            for s in subs:
                if inodes['node_address'] == s['Node']:
                    plan_id = self.get_plan_id(inodes['uuid'])
                    sub_id = s['ID']
                    print(f"Unlinking ({inodes['node_address']} from plan {plan_id}...")
                    self.remove_node_from_plan(plan_id, inodes['node_address'])
                    
                    print(f"Unsubscribing from {inodes['node_address']}...")
                    try:
                        self.unsub_class.unsubscribe(int(sub_id))
                    except:
                        pass
                    
                    print("Updating database...")
                    self.UpdatePlanNodeSubTable(inodes['node_address'])
                    
if __name__ == "__main__":
    unsub = Unsubscribe(keyring_passphrase=scrtxxs.HotWalletPW, wallet_name=scrtxxs.WalletName)
    offline_nodes = UnsubInactive(unsub)
    
    inactive_nodes = offline_nodes.OfflineNodes(offline_nodees.GetPlanNodes())
    subs = offline_nodes.QuerySubscriptions()
    offline_nodes.UnsubAndUnlink(inactive_nodes, subs)
    
    
    
    