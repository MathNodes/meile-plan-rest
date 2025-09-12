import json

JSON = '''
{
  "id": 0,
  "jsonrpc": "2.0",
  "result": {
    "last_item_index": 0,
    "pi": {
      "balance": 1000000000,
      "curent_height": 3327335,
      "transfer_entries_count": 1,
      "transfers_count": 1,
      "unlocked_balance": 1000000000
    },
    "total_transfers": 1,
    "transfers": [{
      "amount": 1000000000,
      "comment": "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9spm",
      "employed_entries": {
        "receive": [{
          "amount": 1000000000,
          "asset_id": "d6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a",
          "index": 0
        }]
      },
      "fee": 10000000000,
      "height": 3327038,
      "is_income": true,
      "is_mining": false,
      "is_mixing": false,
      "is_service": false,
      "payment_id": "",
      "show_sender": false,
      "subtransfers": [{
        "amount": 1000000000,
        "asset_id": "d6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a",
        "is_income": true
      }],
      "timestamp": 1757362503,
      "transfer_internal_index": 0,
      "tx_blob_size": 1207,
      "tx_hash": "27b1a2716d5ebc5d4543d3fab797aa3ab8a85ab3fb6809d5da0dfbae8d2cdc4d",
      "tx_type": 0,
      "unlock_time": 0
    },
    {
      "amount": 999000000000,
      "comment": "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9sperm",
      "employed_entries": {
        "receive": [{
          "amount": 99999000000000,
          "asset_id": "86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f",
          "index": 0
        }]
      },
      "fee": 10000000000,
      "height": 3327999,
      "is_income": true,
      "is_mining": false,
      "is_mixing": false,
      "is_service": false,
      "payment_id": "",
      "show_sender": false,
      "subtransfers": [{
        "amount": 1000000000,
        "asset_id": "d6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a",
        "is_income": true
      }],
      "timestamp": 1757362503,
      "transfer_internal_index": 0,
      "tx_blob_size": 1207,
      "tx_hash": "27b1a2716d5ebc5d4543d3fab797aa3ab8a85ab3fb6809d5da0dfbae8d2cdc4d",
      "tx_type": 0,
      "unlock_time": 0
    }]
  }
}
'''

SATOSHI = 1000000000000
ASSET_IDS = {'zano' : 'd6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a',
             'fusd' : '86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f'}

address = "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9sperm"
asset_id = "86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f"


result = json.loads(JSON)

for tx in result['result']['transfers']:
    if tx['comment'] == address and tx['employed_entries']['receive'][0]['asset_id'] == asset_id:
        print({'result' : round((float(tx['employed_entries']['receive'][0]['amount']) / SATOSHI),4),
                        'height' : tx['height'],
                        'error' : None})
        
        
print({'result' : 0.0,
                'height' : None,
                'error' : None})

