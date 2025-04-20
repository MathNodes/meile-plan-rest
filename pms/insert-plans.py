#!/bin/env python3

import pymysql
import scrtxxs
import uuid
from datetime import datetime
from dateutil.relativedelta import relativedelta

def connDB():
    db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
    return db


db = connDB()
c = db.cursor()

puuid = uuid.uuid4()

sub_id = int(input("Enter the Subscription ID: "))
plan_id = int(input("Enter the Plan ID: "))
plan_name = input("Enter the name of the plan: ")
au_plan_price = int(input("Enter the Plan price in a.u.: "))
au_plan_denom = input("Enter the denom: ")

now = datetime.now()
expires = now + relativedelta(months=+1)

q ='''
    INSERT IGNORE INTO meile_plans (uuid, subscription_id, plan_id, plan_name, plan_price, plan_denom, expiration_date)
    VALUES ("%s", %d, %d, "%s", %d, "%s", "%s");
    ''' % (puuid, sub_id, plan_id, plan_name, au_plan_price, au_plan_denom, str(expires))
try:
    print(q)
    c.execute(q)
    db.commit()
    print("Plan committed to database")
except Exception as e:
    print(str(e))