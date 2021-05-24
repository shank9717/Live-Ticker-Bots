import copy
import functools
import json
import re
import subprocess
import threading
import time

import requests
import websocket

import cogs.Stats.constants as constants
import credentials

try:
    import thread
except ImportError:
    import _thread as thread

debug = False

final_data = threading.local()
final_data.data = {}
final_data.symbol = ''


def pack_json(message, *args):
    return json.dumps({
        'm': message,
        'p': args,
    }, indent=None, separators=(',', ':'))


def pack_pb(command, data):
    cmd = 'node pack.js'.split(' ') + [command, data]
    pipe = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out, err = pipe.communicate()
    return out


def on_error(ws, error):
    print(error)


def on_close(ws):
    print('Closed')


def as_binary(message):
    if debug:
        print('~m~{}~m~{}'.format(len(message), message))
    return '~m~%d~m~%s' % (len(message), message)


def switch_protocol(ws, protocol):
    message = as_binary(pack_json('switch_protocol', protocol))
    ws.send(message)


def on_open(ws, symbol):
    print('Opened')
    switch_protocol(ws, 'json')

    def run(*args):
        message = as_binary(pack_json('set_data_quality', 'low'))
        ws.send(message)
        message = as_binary(pack_json('set_auth_token', credentials.tradingview['auth_token']))
        ws.send(message)
        message = as_binary(pack_json('quote_create_session', constants.SESSION_TOKEN))
        ws.send(message)
        message = as_binary(
            pack_json('quote_add_symbols', constants.SESSION_TOKEN, symbol, {'flags': ["force_permission"]}))
        ws.send(message)
        header = 1
        while True:
            message = as_binary('~h~{}'.format(header))
            header += 1
            ws.send(message)
            time.sleep(10)

    thread.start_new_thread(run, ())


def on_message(ws, message):
    global debug, final_data

    if debug:
        print('{} < {}'.format(time.time(), message))

    if re.match(r'~m~4~m~~h~\d*', message):
        ws.send(message)

    main_msg = re.findall(r'(~m~\d*?~m~)(.*?)(?=(~m~\d*?~m~|$))', message)

    for msg in main_msg:
        new_msg = eval(msg[1].replace('false', 'False').replace('true', 'True').replace('null', 'None'))
        if new_msg['m'] == 'symbol_error':
            ws.close()
        try:
            data = new_msg['p'][1]['v']
            for key in constants.KEYS:
                value = {}
                lookup_key = constants.KEYS_MAP[key]
                try:
                    for word in lookup_key.split('.'):
                        if value != {}:
                            value = value[word]
                        else:
                            value = data[word]
                    if key in list(final_data.data.keys()):
                        continue
                    final_data.data[key] = value
                except:
                    if lookup_key == 'trade.price':
                        try:
                            lookup_key = 'lp'
                            for word in lookup_key.split('.'):
                                if value != {}:
                                    value = value[word]
                                else:
                                    value = data[word]
                            final_data.data[key] = value
                        except:
                            pass
        except:
            pass

    if final_data.data != {}:
        final_data.data['Symbol'] = final_data.symbol
        ltp = final_data.data['Last Price']
        currency = final_data.data['Currency Code']
        cv = final_data.data['Change Value']
        cvp = final_data.data['Change Percentage']

        with open('data.txt', 'w') as f:
            print("{}\n{}\n{}\n{}".format(ltp, currency, cv, cvp), file=f, flush=True)
            time.sleep(2)

        final_data.symbol = ''


def merge_dicts(origin_dict, *optional_dicts):
    copy_dict = copy.deepcopy(origin_dict)
    for optional in optional_dicts:
        copy_dict.update(optional)
    return copy_dict


def main(ticker_main, result):
    global debug, final_data
    final_data.data = {}
    final_data.symbol = ''
    commodities = constants.COMMODITIES
    ticker = ticker_main
    with requests.Session() as session:
        exchange = ''
        ticker_vals = ticker.split(':')
        if len(ticker_vals) >= 2:
            exchange = ticker_vals[0]
            ticker = ticker_vals[1]
        else:
            ticker = ticker_vals[0]

        if ticker.upper() in commodities and exchange == '':
            ticker = ticker.upper()
            exchange = 'MCX'

        params = {
            'text': ticker.upper(),
            'exchange': exchange.upper(),
            'type': '',
            'hl': 'true',
            'lang': 'en',
            'domain': 'production'
        }
        search_url = 'https://symbol-search.tradingview.com/symbol_search/'
        r = session.get(search_url, params=params)
        try:
            data = r.json()[0]
        except:
            result[ticker_main.upper()] = None
            return
        try:
            exchange = data['prefix']
        except:
            exchange = data['exchange']
        try:
            contracts = data['contracts']
            final_data.symbol = contracts[0]['symbol']
        except:
            final_data.symbol = data['symbol']

        final_data.symbol = final_data.symbol.replace('<em>', '').replace('</em>', '')
        final_data.symbol = f'{exchange}:{final_data.symbol}'

        socket_url = 'wss://data.tradingview.com/socket.io/websocket'
        if debug:
            websocket.enableTrace(True)

        while True:
            ws = websocket.WebSocketApp(
                socket_url,
                on_close=on_close,
                on_error=on_error,
                on_message=on_message
            )
            ws.on_open = functools.partial(on_open, symbol=final_data.symbol)

            ws.run_forever(ping_interval=10)
            result[ticker_main.upper()] = final_data.data
            final_data.data = {}
