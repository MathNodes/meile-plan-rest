import pwd
import os

WalletAddress      = "sent..."
WalletName         = "Name"
AllocWalletName    = "Name2"
AllocSeed          = "seed phrase"
HotWalletPW        = "password"
SQLAlchemyScrtKey  = 'sql_scrt_key'
MySQLHost          = "127.0.0.1"
MySQLPort          = 3306
MySQLUsername      = 'username'
MySQLPassword      = 'password'
MySQLDB            = 'db_name'
#BYTES             = 1073741824000 # 1 TiB
BYTES              = 10995116277760 # 10 TiB
ONE_GB             = 1073741824 
HOURS              = 360 # sub amount in hours
RPC                = "https://rpc.mathnodes.com:443"
GRPC               = "http://aimokoivunen.mathnodes.com:9090"
GRPC2              = "https://grpc.dvpn.me:443"
GRPC_MN            = "https://grpc.mathnodes.com:443"
GRPC_BLUEFREN      = "https://grpc.bluefren.xyz:443"
GRPC_NCN           = "https://grpc.noncompliant.network:443"
GRPC_DEV           = "https://grpc.ungovernable.dev:443"
CHAINID            = "sentinelhub-2"
KeyringDIR         = "/home/" + str(pwd.getpwuid(os.getuid())[0])
PlanKeyringDIR     = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + "/.meile-plan"
LogDIR             = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/Logs'
dbDIR              = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/dbs'
sentinelhub        = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + "/go/bin/sentinelhub"
COINSTATS_API_KEYS = [""]
HELPERS            = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + '/api/helpers'
MAX_PRICE          = 15 # max dvpn price to allow node subs
RDN_INTERVAL       = 7 # days from last node sub
