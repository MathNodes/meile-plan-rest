import pwd
import os

WalletAddress      = "sent..."
WalletName         = "Name"
HotWalletPW        = "password"
SQLAlchemyScrtKey  = 'sql_scrt_key'
MySQLHost          = "127.0.0.1"
MySQLPort          = 3306
MySQLUsername      = 'username'
MySQLPassword      = 'password'
MySQLDB            = 'db_name'
BYTES              = 1073741824000 # 1 TB
HOURS              = 360
RPC                = "https://rpc.mathnodes.com:443"
GRPC               = "http://aimokoivunen.mathnodes.com:9090"
GRPC2              = "https://grpc.dvpn.me:443"
GRPC_MN            = "https://grpc.mathnodes.com:443"
GRPC_BLUEFREN      = "https://grpc.bluefren.xyz:443"
CHAINID            = "sentinelhub-2"
KeyringDIR         = "/home/" + str(pwd.getpwuid(os.getuid())[0])
LogDIR             = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/Logs'
dbDIR              = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/dbs'
sentinelhub        = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + "/go/bin/sentinelhub"
COINSTATS_API_KEYS = [""]
HELPERS            = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + '/api/helpers'
MAX_PRICE          = 15
