from addWalletToKeyring import AddToKeyring
import scrtxxs

VERSION = 20250328.1755

AddToKeyring(scrtxxs.HotWalletPW, scrtxxs.AllocWalletName, seed_phrase=scrtxxs.AllocSeed)