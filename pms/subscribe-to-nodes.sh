#!/bin/bash

FILE="$1"

# Edit These
DIR="/home/sentinel/go/bin/subscriptions" #Log dir of sub hashes and results
WALLETNAME="BTCPay2"
KEYRINGDIR="/home/sentinel"
HOURS=720

if [[ $# -lt 1 ]]; then
    echo " "
    echo "Subscribe To Nodes - v0.1 - freQniK"
    echo " "
    echo "Usage: $0 <node_file"
    echo " "
    exit
fi


mapfile -t nodes < <(cat $FILE)

for n in ${nodes[@]}; do
        ./sentinelhub tx vpn node subscribe \
        --from "$WALLETNAME" \
        --gas-prices "0.3udvpn" \
        --node "https://rpc.mathnodes.com:443" \
        --keyring-dir "$KEYRINGDIR" \
        --keyring-backend "file" \
        --chain-id "sentinelhub-2" \
        --yes \
        $n "udvpn" --hours $HOURS >> $DIR/$n.resp
        
        sleep 7
        hash=`cat $DIR/$n.resp | grep "txhash" | sed 's/txhash\: //g'`
        ./sentinelhub query tx --type=hash $hash --node https://rpc.mathnodes.com:443 | grep "raw_log" | sed 's/raw_log\: //g' | sed 's/^.//;s/.$//' | jq >> $DIR/$n-$hash.json
        cat $DIR/$n-$hash.json
        
done
