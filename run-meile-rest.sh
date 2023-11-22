#!/bin/bash

IP=$1

FULLCHAIN="/home/sentinel/api/certs/fullchain.pem"
PRIVKEY="/home/sentinel/api/certs/privkey.pem"

uwsgi --plugin python3 --https-socket $IP:5000,$FULLCHAIN,$PRIVKEY --wsgi-file uWSGI.py --callable app --processes 6 --threads 8 --stats $IP:9191
