from binance.client import Client
from binance.exceptions import BinanceAPIException


class BinanceConnector:
    def __init__(self, api_key, api_secret, testnet=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self.connected = False
        self.testnet = testnet

    def connect(self):
        """Binance API'ye bağlanır"""
        try:
            if self.testnet:
                self.client = Client(self.api_key, self.api_secret, testnet=True)
            else:
                self.client = Client(self.api_key, self.api_secret)

            # Bağlantıyı test etmek için hesap durumu
            self.client.get_account()
            self.connected = True
            return True
        except BinanceAPIException as e:
            print(f"Binance API Hatası: {e}")
            return False
        except Exception as e:
            print(f"Bağlantı hatası: {e}")
            return False

    def get_account_balance(self):
        """Hesap bakiyelerini getirir"""
        if not self.connected:
            return None

        try:
            account_info = self.client.get_account()
            balances = []
            for asset in account_info['balances']:
                if float(asset['free']) > 0 or float(asset['locked']) > 0:
                    balances.append({
                        'asset': asset['asset'],
                        'free': asset['free'],
                        'locked': asset['locked']
                    })
            return balances
        except Exception as e:
            print(f"Bakiye bilgisi alınırken hata: {e}")
            return None

    def get_ticker_prices(self, symbols=None):
        """Belirli sembollerin veya tüm sembollerin fiyatlarını getirir"""
        if not self.connected:
            return None

        try:
            if symbols:
                prices = {}
                for symbol in symbols:
                    price = self.client.get_symbol_ticker(symbol=symbol)
                    prices[symbol] = price['price']
                return prices
            else:
                return self.client.get_all_tickers()
        except Exception as e:
            print(f"Fiyat bilgisi alınırken hata: {e}")
            return None

    def get_open_orders(self):
        """Açık emirleri getirir"""
        if not self.connected:
            return None

        try:
            return self.client.get_open_orders()
        except Exception as e:
            print(f"Açık emirler alınırken hata: {e}")
            return None

    def cancel_order(self, symbol, order_id):
        """Belirli bir emri iptal eder"""
        if not self.connected:
            return False

        try:
            self.client.cancel_order(symbol=symbol, orderId=order_id)
            return True
        except Exception as e:
            print(f"Emir iptal edilirken hata: {e}")
            return False

    def get_order_history(self, symbol=None, limit=50):
        """Geçmiş emirleri getirir"""
        if not self.connected:
            return None

        try:
            params = {'limit': limit}
            if symbol:
                params['symbol'] = symbol
                orders = self.client.get_all_orders(**params)
            else:
                # Sembol belirtilmezse, birkaç popüler sembol için geçmiş emirleri alıp birleştirir
                orders = []
                for sym in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']:
                    try:
                        params['symbol'] = sym
                        sym_orders = self.client.get_all_orders(**params)
                        orders.extend(sym_orders)
                    except:
                        pass  # Bu sembol için emir yoksa geç

                # Son 50 emri alır ve sıralar
                orders.sort(key=lambda x: x['time'], reverse=True)
                orders = orders[:limit]

            return orders
        except Exception as e:
            print(f"Geçmiş emirler alınırken hata: {e}")
            return None
