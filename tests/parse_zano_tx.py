import ast
import fcntl
import json
import os
import secrets
import tempfile
import threading
from contextlib import contextmanager
from os import path

# /v1/zano/getaddress hands out an 8 byte hex payment id per Meile wallet
# address and /v1/zano/gettxs matches transfers on that id, so the fixtures
# below carry hex payment ids rather than the wallet address itself.
JSON_TEMPLATE = '''
{
  "id": 0,
  "jsonrpc": "2.0",
  "result": {
    "pi": {
      "curent_height": 3328100
    },
    "transfers": [
      {
        "height": 3327038,
        "payment_id": "__PAYMENT_ID__",
        "comment": "",
        "employed_entries": {
          "receive": [
            {
              "amount": 1500000000000,
              "asset_id": "d6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a"
            }
          ]
        }
      },
      {
        "height": 3327999,
        "payment_id": "__PAYMENT_ID__",
        "comment": "",
        "employed_entries": {
          "receive": [
            {
              "amount": 250000,
              "asset_id": "86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f"
            }
          ]
        }
      },
      {
        "height": 3328100,
        "payment_id": "__OTHER_PAYMENT_ID__",
        "comment": "",
        "employed_entries": {
          "receive": [
            {
              "amount": 5000000000000,
              "asset_id": "d6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a"
            }
          ]
        }
      }
    ]
  }
}
'''

ASSET_IDS = {
    'zano': 'd6329b5b1f7c0805b5c345f4957554002a2f557845f64d7645dae0e051a6498a',
    'fusd': '86143388bd056a8f0bab669f78f14873fac8e2dd8d57898cdb725a2d5e2e4f8f',
}
DIVISORS = {
    'zano': 10 ** 12,
    'fusd': 10 ** 4,
}

ADDRESS = "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9sperm"
STRANGER = "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9someoneelse"
UNREGISTERED = "sent13lnc9w3dq8d3u74rxgzj8way7w4z2y3lrl9nobody"

API_SOURCE = path.join(path.dirname(path.dirname(path.abspath(__file__))),
                       'meile_plan_api.py')

ZANO_HELPER_NAMES = {
    'zano_lookup_path',
    'zano_lookup_write_lock',
    'load_zano_lookup',
    'save_zano_lookup',
    'get_zano_payment_id',
    'get_or_create_zano_payment_id',
    'normalize_zano_payment_id',
}

ZANO_HELPER_CONSTANTS = {
    'ZANO_LOOKUP_FILENAME',
    'zano_lookup_lock',
}


def extract_zano_helpers(source_path):
    """Load the payment id lookup helpers straight out of meile_plan_api.py.

    meile_plan_api cannot be imported here - it reads a keyring and opens a
    Sentinel SDK connection at import time - so the functions, and the module
    level names they rely on, are taken from the source and run in a small
    namespace instead.
    """
    with open(source_path, 'r') as source_file:
        tree = ast.parse(source_file.read(), source_path)

    body = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.name in ZANO_HELPER_NAMES:
                body.append(node)
        elif isinstance(node, ast.Assign):
            targets = [target.id for target in node.targets
                       if isinstance(target, ast.Name)]

            if targets and targets[0] in ZANO_HELPER_CONSTANTS:
                body.append(node)

    namespace = {
        '__name__': 'zano_helpers',
        'os': os,
        'json': json,
        'path': path,
        'fcntl': fcntl,
        'secrets': secrets,
        'threading': threading,
        'contextmanager': contextmanager,
    }

    exec(compile(ast.Module(body=body, type_ignores=[]), source_path, 'exec'),
         namespace)

    return namespace


ZANO = extract_zano_helpers(API_SOURCE)


def parse_zano_txs(rpc_response, address, coin, height=None):
    """Mirror of the /v1/zano/gettxs matching logic.

    The Meile wallet address is resolved to the 8 byte payment id issued for
    it by /v1/zano/getaddress and transfers are matched on that payment_id,
    because that is what the integrated address carries.
    """
    expected_payment_id = ZANO['normalize_zano_payment_id'](
        ZANO['get_zano_payment_id'](address))

    if not expected_payment_id:
        return {'result': 0.0,
                'height': None,
                'error': None}

    asset_id = ASSET_IDS[coin]
    divisor = DIVISORS[coin]

    result = rpc_response.get('result', {}) or {}
    transfers = result.get('transfers', [])

    accumulated = 0
    found = False
    txheight = None

    for tx in transfers:
        tx_payment_id = ZANO['normalize_zano_payment_id'](tx.get('payment_id'))
        current_tx_height = tx.get('height', 0)

        if tx_payment_id != expected_payment_id:
            continue

        if height is not None:
            if current_tx_height != 0 and current_tx_height <= height - 10:
                continue

        employed_entries = tx.get('employed_entries', {})
        receive_entries = employed_entries.get('receive', [])

        for receive_entry in receive_entries:
            receive_asset_id = receive_entry.get('asset_id')

            if receive_asset_id != asset_id:
                continue

            raw_amount = receive_entry.get('amount', 0)
            accumulated += float(raw_amount) / divisor
            found = True
            txheight = current_tx_height

    if found:
        return {'result': round(float(accumulated), 8),
                'height': txheight,
                'error': None}

    return {'result': 0.0,
            'height': None,
            'error': None}


if __name__ == '__main__':
    original_cwd = os.getcwd()

    # the lookup table is written to the working directory, as on the server,
    # so the checks run somewhere disposable
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)

        try:
            assert ZANO['zano_lookup_path']() == path.join(os.getcwd(),
                                                          'zano_lookup.json')
            assert ZANO['load_zano_lookup']() == {}

            # an address is given one random 8 byte (16 hex character) id
            payment_id = ZANO['get_or_create_zano_payment_id'](ADDRESS)
            print('payment id      :', payment_id)

            assert len(payment_id) == 16, payment_id
            assert payment_id == payment_id.lower(), payment_id
            assert all(char in '0123456789abcdef' for char in payment_id), payment_id

            # the same address always gets the same id back
            assert ZANO['get_or_create_zano_payment_id'](ADDRESS) == payment_id
            assert ZANO['get_zano_payment_id'](ADDRESS) == payment_id

            other_payment_id = ZANO['get_or_create_zano_payment_id'](STRANGER)
            print('other payment id:', other_payment_id)

            assert other_payment_id != payment_id, other_payment_id
            assert ZANO['load_zano_lookup']() == {ADDRESS: payment_id,
                                                  STRANGER: other_payment_id}

            # ids are put in the same shape before they are compared
            normalize = ZANO['normalize_zano_payment_id']

            assert normalize(None) == '', normalize(None)
            assert normalize(payment_id.upper()) == normalize(payment_id)
            assert normalize(f'0x{payment_id.upper()}') == normalize(payment_id)
            assert normalize(f'00{payment_id}') == normalize(payment_id)

            # a damaged table is replaced rather than fatal
            with open(ZANO['zano_lookup_path'](), 'w') as lookup_file:
                lookup_file.write('not json')

            assert ZANO['load_zano_lookup']() == {}

            with open(ZANO['zano_lookup_path'](), 'w') as lookup_file:
                lookup_file.write('[1, 2]')

            assert ZANO['load_zano_lookup']() == {}

            # nothing has been issued for an address that has not asked yet
            assert ZANO['get_zano_payment_id'](UNREGISTERED) is None

            # concurrent callers all end up on the same id
            issued = []

            def create_id():
                issued.append(ZANO['get_or_create_zano_payment_id'](UNREGISTERED))

            workers = [threading.Thread(target=create_id) for _ in range(8)]

            for worker in workers:
                worker.start()

            for worker in workers:
                worker.join()

            assert len(set(issued)) == 1, issued
            assert issued[0] == ZANO['get_zano_payment_id'](UNREGISTERED), issued

            payment_id = ZANO['get_or_create_zano_payment_id'](ADDRESS)
            other_payment_id = ZANO['get_or_create_zano_payment_id'](STRANGER)

            response = json.loads(JSON_TEMPLATE
                                  .replace('__PAYMENT_ID__', payment_id)
                                  .replace('__OTHER_PAYMENT_ID__',
                                           other_payment_id))
            height = response['result']['pi']['curent_height']

            # zano transfer matching the payment id -> 1.5 ZANO; the other
            # address's 5.0 ZANO transfer is not counted in
            zano = parse_zano_txs(response, ADDRESS, 'zano')
            print('zano            :', zano)
            assert zano == {'result': 1.5, 'height': 3327038, 'error': None}, zano

            # fusd transfer matching the payment id -> 25.0 FUSD
            fusd = parse_zano_txs(response, ADDRESS, 'fusd')
            print('fusd            :', fusd)
            assert fusd == {'result': 25.0, 'height': 3327999, 'error': None}, fusd

            # the third transfer belongs to the other address
            stranger = parse_zano_txs(response, STRANGER, 'zano')
            print('stranger        :', stranger)
            assert stranger == {'result': 5.0, 'height': 3328100, 'error': None}, stranger

            # an address that never asked for an id matches nothing
            unregistered = parse_zano_txs(response, UNREGISTERED, 'zano')
            print('unregistered    :', unregistered)
            assert unregistered == {'result': 0.0, 'height': None,
                                    'error': None}, unregistered

            # Zano may echo the id in upper case, it still matches
            response['result']['transfers'][0]['payment_id'] = payment_id.upper()
            uppercase = parse_zano_txs(response, ADDRESS, 'zano')
            print('upper case      :', uppercase)
            assert uppercase == {'result': 1.5, 'height': 3327038,
                                 'error': None}, uppercase

            # the legacy comment field is no longer used for matching
            response['result']['transfers'][0]['comment'] = ADDRESS
            response['result']['transfers'][0]['payment_id'] = ''
            legacy = parse_zano_txs(response, ADDRESS, 'zano')
            print('comment only    :', legacy)
            assert legacy == {'result': 0.0, 'height': None, 'error': None}, legacy

            # transfers older than the 10 block window are ignored
            response['result']['transfers'][0]['payment_id'] = payment_id
            windowed = parse_zano_txs(response, ADDRESS, 'zano', height=height)
            print('windowed        :', windowed)
            assert windowed == {'result': 0.0, 'height': None, 'error': None}, windowed
        finally:
            os.chdir(original_cwd)

    print('All parse_zano_tx checks passed.')

