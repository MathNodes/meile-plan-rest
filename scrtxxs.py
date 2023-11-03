import pwd
import os

WalletAddress     = "sent..."
WalletName        = "Name"
HotWalletPW       = "password"
SQLAlchemyScrtKey = 'sql_scrt_key'
MySQLUsername     = 'username'
MySQLPassword     = 'password'
MySQLDB           = 'db_name'
BYTES             = 1073741824000 # 1 TB
RPC               = "https://rpc.mathnodes.com:443"
CHAINID           = "sentinelhub-2"
KeyringDIR        = "/home/" + str(pwd.getpwuid(os.getuid())[0])
LogDIR            = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/Logs'
dbDIR             = '/home/' + str(pwd.getpwuid(os.getuid())[0]) + '/dbs'
sentinelhub       = "/home/" + str(pwd.getpwuid(os.getuid())[0]) + "/go/bin/sentinelhub"
