#!/bin/bash

PLANID=$1
FILE=$2

# Edit These
WALLETNAME="BTCPay2"
KEYRINGDIR="/home/sentinel"

if [[ $# -lt 2 ]]; then
    echo " "
    echo "Add Nodes from file to Plan, v0.1 - freQniK"
    echo " "
    echo "Usage: $0 <plan_id> <node_file>"
    echo " "
    exit
fi

mapfile -t plan_nodes < <(cat $FILE)

for n in ${plan_nodes[@]}; do
    echo "Adding: $n, to plan: $PLANID"
    echo " "
    ./sentinelhub tx vpn plan add-node \
    --from "$WALLETNAME" \
    --gas-prices "0.3udvpn" \
    --node "https://rpc.mathnodes.com:443" \
    --keyring-dir "$KEYRINGDIR" \
    --keyring-backend "file" \
    --chain-id "sentinelhub-2" \
    --yes \
    $PLANID $n
    sleep 5
done
