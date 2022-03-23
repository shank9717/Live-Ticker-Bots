import functools
import json
from queue import Queue
import re
import threading
import logging
import time
import requests
import websocket

import cogs.Stats.constants as constants
import credentials
import multiprocessing

class StocksApi(threading.Thread):
    def __init__(self, ticker_main: str, queue: Queue, stop_flag: bool = False):
        """
            ticker_main -> User provided ticker
            result -> Result dict with ticker as key and details as value
            symbol -> Symbol obtained from TradingView
        """
        super(StocksApi, self).__init__()
        self.final_data = {}
        self.ticker = ticker_main.upper()
        self.queue = queue
        self.stop_flag = stop_flag
        
    def __exit__(self):
        try:
            self.ws.close()
        except Exception as e:
            print("Error closing ws: ", e)

    def run(self):
        self.start_time_data = time.time()   
        ticker_cp = self.ticker
        with requests.Session() as session:
            self.symbol = self.get_symbol(session, ticker_cp, self.ticker)
            if self.symbol is None:
                return
            
            socket_url = 'wss://data.tradingview.com/socket.io/websocket'

            self.ws = websocket.WebSocketApp(
                socket_url,
                on_close=self.on_close,
                on_error=self.on_error
            )
            self.ws.on_open = functools.partial(self.on_open)
            self.ws.on_message = functools.partial(self.on_message)            
            self.ws.keep_running = True 

            self.wst = threading.Thread(target=self.ws.run_forever)
            self.wst.daemon = True
            self.wst.start()
            self.stop_flag = False

            while not self.stop_flag:          
                if (time.time() - self.start_time_data) > constants.TTL:
                    self.queue.put(['##RELOAD##'])
                    break
            self.close()
        self.queue.put(['##RELOAD##'])

    def stop(self):
        self.stop_flag = True
    
    def close(self):
        try:
            self.ws.close()
        except Exception as e:
            print("Error closing ws: ", e)

    def get_symbol(self, session, ticker, ticker_main):
        ticker_parts = ticker.split(':')
        ticker, exchange = self.process_ticker(ticker_parts)

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
            self.result[ticker_main.upper()] = None
            return None
        try:
            exchange = data['prefix']
        except:
            exchange = data['exchange']
        try:
            contracts = data['contracts']
            symbol = contracts[0]['symbol']
        except:
            symbol = data['symbol']

        symbol = symbol.replace('<em>', '').replace('</em>', '')
        symbol = f'{exchange}:{symbol}'
        return symbol

    def process_ticker(self, ticker_parts):
        exchange = ''
        if len(ticker_parts) >= 2:
            exchange = ticker_parts[0]
            ticker = ticker_parts[1]
        else:
            ticker = ticker_parts[0]

        if ticker.upper() in constants.COMMODITIES and exchange == '':
            ticker = ticker.upper()
            exchange = 'MCX'

        return ticker, exchange

    def pack_json(self, message, *args):
        return json.dumps({
            'm': message,
            'p': args,
        }, indent=None, separators=(',', ':'))

    def as_binary(self, message):
        return '~m~%d~m~%s' % (len(message), message)

    def switch_protocol(self, ws, protocol):
        message = self.as_binary(self.pack_json('switch_protocol', protocol))
        ws.send(message)

    def on_error(self, error):
        print(f'Error occured: {error}')

    def on_close(self):
        print('Closed')

    def on_open(self, ws):
        self.switch_protocol(ws, 'json')

        def run():
            message = self.as_binary(self.pack_json('set_data_quality', 'low'))
            ws.send(message)
            message = self.as_binary(self.pack_json('set_auth_token', credentials.tradingview['auth_token']))
            ws.send(message)
            message = self.as_binary(self.pack_json('quote_create_session', constants.SESSION_TOKEN))
            ws.send(message)
            message = self.as_binary(
                self.pack_json('quote_add_symbols', constants.SESSION_TOKEN, self.symbol, {'flags': ["force_permission"]}))
            ws.send(message)
            message = self.as_binary(self.pack_json('quote_fast_symbols', constants.SESSION_TOKEN, self.symbol))
            ws.send(message)
        
        thread = threading.Thread(target=run)
        thread.start()
        thread.join()

    def on_message(self, ws, message):
        if re.match(r'~m~\d*?~m~~h~\d*', message):
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
                        self.final_data[key] = value
                    except:
                        if lookup_key == 'trade.price':
                            try:
                                lookup_key = 'lp'
                                for word in lookup_key.split('.'):
                                    if value != {}:
                                        value = value[word]
                                    else:
                                        value = data[word]
                                self.final_data[key] = value
                            except:
                                pass
            except:
                pass
        

        if self.final_data != {}:
            self.final_data['Symbol'] = self.symbol
            ltp = self.final_data['Last Price']
            currency = self.final_data['Currency Code']
            cv = self.final_data['Change Value']
            cvp = self.final_data['Change Percentage']

            
            print("Internal Data: ", str(ltp), str(cv))
            if not self.queue.empty():
                self.queue.get_nowait()
            self.queue.put((ltp, currency, cv, cvp))
            
