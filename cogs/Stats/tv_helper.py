import functools
import json
import logging
import re
import threading
import time
from queue import Queue
from typing import List, Tuple, Dict, Optional

import requests
import websocket

import cogs.Stats.constants as constants
import credentials


class StockData:
    def __init__(self, last_traded_price: float, currency: str, change_value: float, change_val_perc: float) -> None:
        self.last_traded_price: float = last_traded_price
        self.currency: str = currency
        self.change_value: float = change_value
        self.change_val_perc: float = change_val_perc


class StocksApi(threading.Thread):
    def __init__(self, ticker_main: str, queue: Queue, stop_flag: bool = False) -> None:
        """
            ticker_main -> User provided ticker
            result -> Result dict with ticker as key and details as value
            symbol -> Symbol obtained from TradingView
        """
        super(StocksApi, self).__init__()
        self.final_data: Dict[str, object] = {}
        self.ticker: str = ticker_main.upper()
        self.queue: Queue = queue
        self.stop_flag: bool = stop_flag
        self.start_time_data = None
        self.symbol = None
        self.ws = None
        self.wst = None

    def run(self) -> None:
        self.start_time_data = time.time()
        ticker_cp: str = self.ticker
        with requests.Session() as session:
            self.symbol = self.get_symbol(session, ticker_cp, self.ticker)
            if self.symbol is None:
                raise Exception(f'Symbol not found - {ticker_cp}')

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

    def get_symbol(self, session: requests.Session, ticker: str, ticker_main: str) -> Optional[str]:
        ticker_parts: List[str] = ticker.split(':')
        ticker, exchange = self.process_ticker(ticker_parts)

        params = {
            'text': ticker.upper(),
            'exchange': exchange.upper(),
            'type': '',
            'hl': 'true',
            'lang': 'en',
            'domain': 'production'
        }
        search_url: str = 'https://symbol-search.tradingview.com/symbol_search/'
        r: requests.Response = session.get(search_url, params=params)
        try:
            data = r.json()[0]
        except IndexError:
            return None
        try:
            exchange = data['prefix']
        except KeyError:
            exchange = data['exchange']
        try:
            contracts = data['contracts']
            symbol = contracts[0]['symbol']
        except KeyError:
            symbol = data['symbol']

        symbol = symbol.replace('<em>', '').replace('</em>', '')
        symbol = f'{exchange}:{symbol}'
        return symbol

    @staticmethod
    def process_ticker(ticker_parts: List[str]) -> Tuple[str, str]:
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

    @staticmethod
    def pack_json(message: str, *args) -> str:
        return json.dumps({
            'm': message,
            'p': args,
        }, indent=None, separators=(',', ':'))

    @staticmethod
    def as_binary(message: str) -> str:
        return '~m~%d~m~%s' % (len(message), message)

    def switch_protocol(self, ws: websocket.WebSocketApp, protocol: str) -> None:
        message = self.as_binary(self.pack_json('switch_protocol', protocol))
        ws.send(message)

    def on_open(self, ws: websocket.WebSocketApp) -> None:
        self.switch_protocol(ws, 'json')

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

    def on_message(self, ws: websocket.WebSocketApp, message: str) -> None:
        try:
            if re.match(r'~m~\d*?~m~~h~\d*', message):
                ws.send(message)

            main_msg = re.findall(r'(~m~\d*?~m~)(.*?)(?=(~m~\d*?~m~|$))', message)

            for msg in main_msg:
                try:
                    new_msg = eval(msg[1].replace('false', 'False').replace('true', 'True').replace('null', 'None'))
                    if 'm' in new_msg and new_msg['m'] == 'symbol_error':
                        ws.close()
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
                        except KeyError:
                            if lookup_key == 'trade.price':
                                try:
                                    lookup_key = 'lp'
                                    value = data[lookup_key]
                                    self.final_data[key] = value
                                except KeyError:
                                    continue
                except:
                    pass

            if self.final_data != {}:
                self.final_data['Symbol'] = self.symbol
                if not 'Last Price' in self.final_data:
                    return
                ltp = self.final_data['Last Price']
                currency = self.final_data['Currency Code']
                cv = self.final_data['Change Value']
                cvp = self.final_data['Change Percentage']

                logging.debug("Internal Data: ", str(ltp), str(cv))
                if not self.queue.empty():
                    self.queue.get_nowait()
                self.queue.put((ltp, currency, cv, cvp))

        except Exception as e:
            logging.error(e)

    def stop(self) -> None:
        self.stop_flag = True

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception as e:
            logging.error("Error closing ws: ", e)

    @staticmethod
    def on_error(error) -> None:
        logging.error(f'Error occurred: {error}')

    @staticmethod
    def on_close() -> None:
        logging.warning('Closed socket')

    def __exit__(self) -> None:
        try:
            self.ws.close()
        except Exception as e:
            logging.error("Error closing ws: ", e)
