# meile-plan-rest

Meile Subscription Plan REST API

## Dependencies

* uWSGI, `sudo apt install uwsgi-plugin-python3`
* Flask, 
* FlaskMySQL, 
* pexepct, 
* PyJWT, 
* date-util 
* Werkzeug, 
* SQLAlchemy,

`pip install -r requirements.txt`

# API Documentation

[Swagger OpenAPI](https://petstore.swagger.io/?url=https://raw.githubusercontent.com/MathNodes/meile-plan-rest/main/doc/meile-api.yaml)



# Database Schema

Create a database and name it `meile`:

```sql
CREATE DATABASE meile;
```

Then use the database:

```sql
USE meile;
```

Now follow the schema in the `schema` directory to create the necessary tables used to manage Sentinel subscription plans

# Running

To run the plan API, make sure you have SSL certs for your domain and edit the following lines of `run-meile-rest.sh`:

```shell
FULLCHAIN="/home/sentinel/api/certs/fullchain.pem"
PRIVKEY="/home/sentinel/api/certs/privkey.pem"
```

Or if you prefer can you can run this without SSL certs and run it behind a nginx or Apache reverse proxy - which is a more robust setup. Som

Then run the following command to start the API server;

```shell
./run-meile-rest <ip>
```

Filling in the ip address you wish to run the server on. This will spawn the server on port 5000. It will also spawn a stats server on port 9191. 



# Helpers

Creators of Sentinel subscription plans need to manage their plans. This is not fully automated as of yet. We are looking to develope a daemon that will handle these helper files automatically. For now here is the list of helpers and what they do.

## add-nodes-to-plan.sh

Deprecated. Do not use.

## auto_price.py

Usage:

```shell
usage: auto-price.py [-h] [--plan plan] [--price price] [--days days]

Meile Plan Auto Pricer - v0.1 - freQniK

options:
  -h, --help     show this help message and exit
  --plan plan    --plan <uuid>, uuid of plan
  --price price  --price <usd>, price of plan in USD
  --days days    --days <n>, number of days to average coin price (twap)
```

This can be run in a crontab as follows:

```shell
0 0 * * * /home/sentinel/api/helpers/auto-price.py --plan 479a9af6-5401-4ed9-ac5f-95c070255e7b --price 3.14 --days 7
0 12 * * * /home/sentinel/api/helpers/auto-price.py --plan f6c079a9-f781-4751-9be4-8c498c635a8b --price 6.00 --days 7
```

Where `--plan` is followed by the UUID of the plan you created. `--days` is the time-weighted average price of $dvpn$ and `--price` is the USD price of the plan

## enforce_max_price.py

This script has no arguments and can be run at any time. A crontab job will suffice as well for now. 

This script uses the varable `MAX_PRICE` in `scrtxxs.py` as the highest $dvpn$ price allowed for nodes to be subscribed to. Any node who tries to game the plan system and set a higher price will be removed from the plans and no longer will receive plan incentives.

## meta_unsub.sh

This is a routine used to run `query_subs.py` and `unsubscribe.py` to find all node subscriptions of your plan wallet, find the duplicate subscriptions, and unsubscribe from any duplicate node subscriptions. It can be run if you suspect there are duplicate subscriptions which would cost you extra to run the plan. It is typically run in conjunction with a cronjob of `plan-node-subscriptions.py` in order to immediately remove any duplicate subscriptions mitigating loss of $dvpn$

## insert-nodes.py

This script should not be run by you. It is a script used by `plan-node-subscriptions.py`

Usage:

```shell
usage: insert-nodes.py [-h] [-f node_file] [--uuid uuid]

Plan Node Inserter v0.1 - freQniK

options:
  -h, --help            show this help message and exit
  -f node_file, --file node_file
                        file to read nodes from
  --uuid uuid           --uuid <uuid>, uuid of plan to add nodes to
```

All it does is insert the newly subscribed nodes into the database in the table `plan_nodes`

## plan-node-subscriptions.py

Usage:

```shell
usage: plan-node-subscriptions.py [-h] [--file file] [--seed] [--uuid uuid]

Meile Plan Subscriber - v0.3 - freQniK

options:
  -h, --help   show this help message and exit
  --file file  --file <nodefile>, absolute path of a list of sentnode... addresses separated by newline
  --seed       set if you are specifying a seedphrase
  --uuid uuid  --uuid <uuid>, uuid of plan to subscribe nodes to
```

This is the heart of the plan management. When run in a cronjob as follows:

```shell
30 * * * * /home/sentinel/api/helpers/plan-node-subscriptions.py >> /home/sentinel/Logs/plan-node-subs.log 2>&1 && /home/sentinel/api/helpers/meta_unsub.sh >> /home/sentinel/Logs/plan-node-subs.log 2>&1
```

It will automatically read the plan node subscriptions, find any that are lapsed, and resub to them. 

If you want to add nodes to a plan you can run this script as well on the command line. First create a file with just the `sentnode...` addresses of the nodes you wish to subscribe to.

Then run

```shell
./plan-node-subscriptions.py --file <path_to_node_file> --uuid <uuid_of_plan>
```

This will subscribe to the nodes in the file and add them to the plan but on-chain and in the database.

## purge_expired_subs.py

This helper script should be run in a cronjob as follows:

```shell
0 * * * * /home/sentinel/api/helpers/purge_expired_subs.py
```

It will remove the allocations of the subscriber if their subscription has lapsed thereby inactiving their subscription.

It will create the following logfile: `/home/sentinel/Logs/meile_unsub.log`

## query_subs.py

This can be run to show the subscriptions to nodes you have on the give plan wallet. It is run by `meta_unsub.sh` 

## remove-dead-nodes.py

This removes any nodes that are no longer active on the Sentinel blockchain within the last `RDN_INTERVAL` timeframe. Please specify how long you would like to keep nodes in the database that are inactive by setting this variable in `scrtxxs.py`

This can be run in a cronjob or run manually.

It create the following logfile: `/home/sentinel/Logs/remove-dead-nodes.log`

## subscribe-to-nodes.sh

Deprecated. Do not use.

## top-up-subscribers.py

This can be run in a cronjob as follows:

```shell
0 0 * * * /home/sentinel/api/top-up-subscribers.py
```

This will send 1 $dvpn$ to all active subscribers in order to pay for gas fees when connecting to nodes. This also allows users who did not subscribe with the native coin to use the Sentinel subscription plan without ever interacting with the Sentinel coin. 

## unsubscribe.py

This is run by `meta_unsub.sh` as a means to unsubscribe from duplicate or unwanted plan node subscriptions. You do not need to run this if you are running `meta_unsub.sh` . If on the other hand you wish to unsubscribe from nodes you can run it directly. This is not advised.

Usage:

```shell
usage: unsubscribe.py [-h] [--seed] [--file file]

Meile Plan Subscriber - v0.2 - freQniK

options:
  -h, --help   show this help message and exit
  --seed       set if you are specifying a seedphrase
  --file file  --file <file.json>, absolute path of a list of subscriptions
```

## update-node-scriptions.py

This script is ran automatically by `plan-node-subscriptions.py` to update the database and the plan on chain. It should not be run manually. 
