#!/bin/bash

PREFIXDIR="/home/sentinel/api/helpers"
cd $PREFIXDIR
rm subs.json subs2.json subs3.json unsub.json
python3 query_subs.py >> subs.json
cat subs.json | sed -e "s/'/\"/g" >> subs2.json
cat subs2.json | jq >> subs3.json
cat subs3.json | jq 'length'
jq 'group_by(.Node) | map(select(length > 1)) | add | .[2:]' subs3.json >> unsub.json
cat unsub.json
sleep 10
python3 unsubscribe.py --file unsub.json