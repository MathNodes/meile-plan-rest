#!/bin/env python3

import pymysql
import scrtxxs
import uuid
import argparse
import sys


def connDB():
    db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
    return db




if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Plan Node Inserter v0.1 - freQniK")
    parser.add_argument('-f', '--file', help="file to read nodes from", metavar="node_file")
    parser.add_argument('--uuid', help="--uuid <uuid>, uuid of plan to add nodes to", metavar="uuid")
    
    args = parser.parse_args()
    
    if args.file:
        NODE_FILE = str(args.file)
    else:
        print("Please specify a nodes file")
        sys.exit(1)
    
    db = connDB()
    c = db.cursor()
    
    
    puuid = args.uuid if args.uuid else sys.exit(1)
    
    node_addresses = []
    
    with open(NODE_FILE, 'r') as nfile:
        data = nfile.readlines()
    k = 0
    for d in data:
        d = d.rstrip()
        node_addresses.append(d)
        k += 1
    
    print(f"Inserting: {k}, nodes into plan: {puuid}...")
    queries = []
    for a in node_addresses:
        q ='''
            INSERT IGNORE INTO plan_nodes (uuid, node_address)
            VALUES ("%s", "%s");
            ''' % (puuid, a)
        queries.append(q)
    k = 0
    for q in queries:
        try:
            print(q)
            c.execute(q)
            db.commit()
            k += 1
        except Exception as e:
            print(str(e))
            
    print(f"Inserted: {k}, nodes into plan: {puuid}.")