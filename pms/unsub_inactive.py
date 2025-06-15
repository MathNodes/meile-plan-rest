#!/bin/env python3

from unsubscribe import Unsubscribe
import scrtxxs
import pymysql

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