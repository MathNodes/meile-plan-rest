#!/bin/env python3
import argparse
import scrtxxs
import pymysql
import sys

from datetime import datetime,timedelta, timezone
import random
import requests
import time
from statistics import mean


COINSTATS_API = "https://openapiv1.coinstats.app/coins/price/avg?coinId=%s&timestamp=%s"
COINS = {'sentinel' : 'dvpn' }
SATOSHI = 1000000
VERSION = 20241124.1851

class AutoPrice():
    
        
    def connDB(self):
        db = pymysql.connect(host=scrtxxs.MySQLHost,
                         port=scrtxxs.MySQLPort,
                         user=scrtxxs.MySQLUsername,
                         passwd=scrtxxs.MySQLPassword,
                         db=scrtxxs.MySQLDB,
                         charset='utf8mb4',
                         cursorclass=pymysql.cursors.DictCursor)
        return db
    
    def __CoinStatsPrices(self, days):
        today = datetime.now(timezone.utc)
        CoinPrices = {}
        price_data = {coin: [] for coin in list(COINS.keys())}
        for k in range(1,days+1):
            N = random.randint(0,len(scrtxxs.COINSTATS_API_KEYS)-1)
            API_KEY = scrtxxs.COINSTATS_API_KEYS[N]
            headers = {
                "accept": "application/json",
                "X-API-KEY": f"{API_KEY}"
            }
            for coin in list(COINS.keys()):    
                day_delta = today - timedelta(days=k)
                ts = int(day_delta.timestamp())
                try:
                    response = requests.get(COINSTATS_API % (coin, ts), headers=headers)
                    r = response.json()
                    print(r)
                except Exception as e:
                    print(str(e))
                    time.sleep(5)
                    continue
                price_data[coin].append(r['USD'])
                #print(price_data[coin])
                time.sleep(3)
                
        for coin in list(COINS.keys()):
            CoinPrices[coin] = mean(price_data[coin])
        #print(CoinPrices)
        return CoinPrices
    
    def adjust_plan_price(self, plan, price, denom, days, db):
        coin_prices = self.__CoinStatsPrices(days)
        
        dvpn_price = coin_prices['sentinel']
        
        plan_price = int((float(price) / float(dvpn_price))*SATOSHI)
        print(f"{plan_price}{COINS['sentinel']}")
              
        query = f"UPDATE meile_plans SET plan_price = {plan_price} WHERE uuid = '{plan}';"
        
        c = db.cursor()
        c.execute(query)
        db.commit()
        
    
    
    
if __name__ == "__main__":
    
    
    parser = argparse.ArgumentParser(description="Meile Plan Auto Pricer - v0.1 - freQniK")
        
    parser.add_argument('--plan', help="--plan <uuid>, uuid of plan", metavar="plan")
    parser.add_argument('--price', help="--price <usd>, price of plan in USD", metavar="price")
    #parser.add_argument('--denom', help="--denom currency_ticker_symbol, ticker symbol of denom for plan", metavar="denom")
    parser.add_argument('--days', help="--days <n>, number of days to average coin price (twap)", metavar="days")
    
    args = parser.parse_args()
        
    if not args.plan or not args.price  or not args.days:
        parser.print_help()
        sys.exit(1)
        
    else:
        ap = AutoPrice()
        ap.adjust_plan_price(args.plan, float(args.price), COINS['sentinel'], int(args.days), ap.connDB())
        
        
        
    
        
        
        
        

