#!/bin/bash

# Plans (EDIT)
BASIC=508130
PREMIUM=695884

# gRPC
GRPC="grpc.ungovernable.dev:443"

BYTES=`./sentinelhub q vpn allocations $BASIC --grpc-addr $GRPC | grep "utilised_bytes" | cut -d ":" -f 2 | tr -d " " | sed -e 's/\"//g' | paste -sd+ | bc`
GB=`echo "scale=3; ${BYTES} / (1024*1024*1024)" | bc`
BASICJSON=`./sentinelhub q vpn allocations $BASIC --grpc-addr $GRPC --output json`
TOTAL_BASIC_SUBS=`echo $BASICJSON | jq '.allocations | length'`
UNUSED_SUBS_BASIC=`echo $BASICJSON | jq '[.allocations[] | select(.granted_bytes | tonumber >= 0) and select(.utilised_bytes | tonumber == 0)] | length'`
echo "Utilised (Basic Plan): ${GB}GB"
echo "Total Subscribers: ${TOTAL_BASIC_SUBS}"
echo "Unused Subs (Basic Plan): $((UNUSED_SUBS_BASIC-1))"
echo 'Average Utilised: $(bc -l <<< "scale=3; $GB / ($TOTAL_BASIC_SUBS - $UNUSED_SUBS_BASIC - 1)")GB'
BYTES=`./sentinelhub q vpn allocations $PREMIUM --grpc-addr $GRPC | grep "utilised_bytes" | cut -d ":" -f 2 | tr -d " " | sed -e 's/\"//g' | paste -sd+ | bc`
GB=`echo "scale=3; ${BYTES} / (1024*1024*1024)" | bc`
PREMIUMJSON=`./sentinelhub q vpn allocations $PREMIUM --grpc-addr $GRPC --output json`
TOTAL_PREMIUM_SUBS=`echo $PREMIUMJSON | jq '.allocations | length'`
UNUSED_SUBS_PREMIUM=`echo $PREMIUMJSON | jq '[.allocations[] | select(.granted_bytes | tonumber >= 0) and select(.utilised_bytes | tonumber == 0)] | length'`
echo "Utilised (Premium Plan): ${GB}GB"
echo "Total Subscribers: ${TOTAL_PREMIUM_SUBS}"
echo "Unused Subs (Premium Plan): $((UNUSED_SUBS_PREMIUM-1))"
echo 'Average Utilised: $(bc -l <<< "scale=3; $GB / ($TOTAL_PREMIUM_SUBS - $UNUSED_SUBS_PREMIUM - 1)")GB'