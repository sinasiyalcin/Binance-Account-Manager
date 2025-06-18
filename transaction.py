from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QLabel, QTableWidget,
                           QTableWidgetItem, QTabWidget, QGroupBox,
                           QFormLayout, QComboBox, QLineEdit, QMessageBox, QCheckBox)
from PyQt5.QtCore import Qt, QTimer
from binance_api import BinanceConnector
from binance.exceptions import BinanceAPIException
from datetime import datetime

class AccountWidget(QWidget):
    def __init__(self, account_name, account_data, parent=None):
        super().__init__(parent)
        self.account_name = account_name
        self.api_key = account_data["api_key"]
        self.api_secret = account_data["api_secret"]
        self.testnet = account_data.get("testnet", True)  # Varsayılan olarak testnet
        self.connector = BinanceConnector(self.api_key, self.api_secret, testnet=self.testnet)
        self.init_ui()
        self.connect_account()

    def init_ui(self):
        layout = QVBoxLayout()

        # Hesap başlığı
        title_layout = QHBoxLayout()
        title = QLabel(f"Account: {self.account_name}")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        title_layout.addWidget(title)

        self.status_label = QLabel("Connecting...")
        title_layout.addWidget(self.status_label, alignment=Qt.AlignRight)
        layout.addLayout(title_layout)

        # Sekme widget'ı
        self.tabs = QTabWidget()

        # Bakiye sekmesi
        self.balance_tab = QWidget()
        balance_layout = QVBoxLayout()

        # Toplam değer etiketi
        self.total_value_label = QLabel("Total Value: $0.00")
        self.total_value_label.setStyleSheet("font-size: 14px; font-weight: bold; color: green;")
        balance_layout.addWidget(self.total_value_label)

        self.balance_table = QTableWidget()
        self.balance_table.setColumnCount(4)
        self.balance_table.setHorizontalHeaderLabels(["Asset", "Free", "Locked", "USD Value"])
        self.balance_table.horizontalHeader().setStretchLastSection(True)

        refresh_balance_btn = QPushButton("Refresh")
        refresh_balance_btn.clicked.connect(self.update_balance)

        balance_layout.addWidget(self.balance_table)
        balance_layout.addWidget(refresh_balance_btn)
        self.balance_tab.setLayout(balance_layout)

        # Açık emirler sekmesi
        self.orders_tab = QWidget()
        orders_layout = QVBoxLayout()

        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(5)
        self.orders_table.setHorizontalHeaderLabels(["Symbol", "Side", "Quantity", "Price", "Status"])
        self.orders_table.horizontalHeader().setStretchLastSection(True)

        refresh_orders_btn = QPushButton("Refresh")
        refresh_orders_btn.clicked.connect(self.update_orders)

        orders_layout.addWidget(self.orders_table)
        orders_layout.addWidget(refresh_orders_btn)
        self.orders_tab.setLayout(orders_layout)

        # Emir geçmişi sekmesi
        self.history_tab = QWidget()
        history_layout = QVBoxLayout()

        # Sembol filtresi
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Symbol Filter:"))
        self.history_symbol_combo = QComboBox()
        self.history_symbol_combo.setEditable(True)
        self.history_symbol_combo.addItem("All Symbols")
        filter_layout.addWidget(self.history_symbol_combo)

        # Limit seçimi
        filter_layout.addWidget(QLabel("Display Count:"))
        self.history_limit_combo = QComboBox()
        self.history_limit_combo.addItems(["10", "20", "50", "100"])
        self.history_limit_combo.setCurrentIndex(1)  # Varsayılan 20
        filter_layout.addWidget(self.history_limit_combo)

        # Yenileme butonu
        refresh_history_btn = QPushButton("Refresh History")
        refresh_history_btn.clicked.connect(self.update_order_history)
        filter_layout.addWidget(refresh_history_btn)

        history_layout.addLayout(filter_layout)

        # Emir geçmişi tablosu
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels(["Time", "Symbol", "Side", "Type", "Quantity", "Price", "Status", "Total"])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        history_layout.addWidget(self.history_table)

        self.history_tab.setLayout(history_layout)

        # İşlem sekmesi
        self.trade_tab = QWidget()
        trade_layout = QVBoxLayout()

        # İşlem formu
        trade_form_group = QGroupBox("New Trade")
        trade_form_layout = QFormLayout()

        # Sembol seçici
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)  # Kullanıcı manuel girebilir
        trade_form_layout.addRow("Symbol:", self.symbol_combo)

        # Emir tipi
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT"])
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)
        trade_form_layout.addRow("Order Type:", self.order_type_combo)

        # Alış/Satış seçeneği
        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])
        trade_form_layout.addRow("Trade Side:", self.side_combo)

        # Miktar
        self.quantity_input = QLineEdit()
        self.quantity_input.setPlaceholderText("Ex: 0.001")
        trade_form_layout.addRow("Quantity:", self.quantity_input)

        # Fiyat (LIMIT ve STOP_LOSS_LIMIT için)
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("Ex: 50000")
        trade_form_layout.addRow("Price:", self.price_input)

        # Durdurma fiyatı (STOP_LOSS ve STOP_LOSS_LIMIT için)
        self.stop_price_input = QLineEdit()
        self.stop_price_input.setPlaceholderText("Ex: 49000")
        self.stop_price_input.setVisible(False)  # Başlangıçta gizli
        trade_form_layout.addRow("Stop Price:", self.stop_price_input)

        # Take Profit Fiyatı
        self.take_profit_price = QLineEdit()
        self.take_profit_price.setPlaceholderText("Take Profit Price (optional)")
        trade_form_layout.addRow("Take Profit:", self.take_profit_price)

        # Stop Loss Fiyatı
        self.stop_loss_price = QLineEdit()
        self.stop_loss_price.setPlaceholderText("Stop Loss Price (optional)")
        trade_form_layout.addRow("Stop Loss:", self.stop_loss_price)

        # İşlem butonu
        self.place_order_btn = QPushButton("Place Order")
        self.place_order_btn.clicked.connect(self.place_order)
        trade_form_layout.addRow("", self.place_order_btn)

        trade_form_group.setLayout(trade_form_layout)
        trade_layout.addWidget(trade_form_group)

        # Sembol bilgi paneli
        symbol_info_group = QGroupBox("Symbol Information")
        symbol_info_layout = QVBoxLayout()

        # Sembol fiyat bilgisi
        self.price_info_label = QLabel("Select a symbol to view information")
        symbol_info_layout.addWidget(self.price_info_label)

        # Sembol fiyat yenileme butonu
        refresh_price_btn = QPushButton("Update Price")
        refresh_price_btn.clicked.connect(self.update_symbol_price)
        symbol_info_layout.addWidget(refresh_price_btn)

        symbol_info_group.setLayout(symbol_info_layout)
        trade_layout.addWidget(symbol_info_group)

        # İşlem geçmişi
        trade_history_group = QGroupBox("Trade History")
        trade_history_layout = QVBoxLayout()

        self.trade_history_table = QTableWidget()
        self.trade_history_table.setColumnCount(6)
        self.trade_history_table.setHorizontalHeaderLabels(["Date", "Symbol", "Side", "Quantity", "Price", "Status"])
        self.trade_history_table.horizontalHeader().setStretchLastSection(True)

        refresh_history_btn = QPushButton("Update History")
        refresh_history_btn.clicked.connect(self.update_trade_history)

        trade_history_layout.addWidget(self.trade_history_table)
        trade_history_layout.addWidget(refresh_history_btn)

        trade_history_group.setLayout(trade_history_layout)
        trade_layout.addWidget(trade_history_group)

        self.trade_tab.setLayout(trade_layout)

        # Sekmeleri ekle
        self.tabs.addTab(self.balance_tab, "Balance")
        self.tabs.addTab(self.orders_tab, "Open Orders")
        self.tabs.addTab(self.history_tab, "Order History")
        self.tabs.addTab(self.trade_tab, "Trade")

        layout.addWidget(self.tabs)
        self.setLayout(layout)

        # Otomatik yenileme için zamanlayıcı
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh_data)
        self.timer.start(300000)  # Her 5 dakikada bir yenile

    def connect_account(self):
        """Hesaba bağlan"""
        if self.connector.connect():
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: green;")
            self.update_balance()
            self.update_orders()
            self.update_order_history()  # Ayrıca emir geçmişini güncelle
            self.load_symbols()  # Sembolleri yükle
        else:
            self.status_label.setText("Connection Error")
            self.status_label.setStyleSheet("color: red;")

    def load_symbols(self):
        """Tüm sembolleri yükle"""
        try:
            print("Sembol bilgilerini alıyor...")
            # En fazla 100 sembol ile sınırla
            popular_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'DOGEUSDT',
                              'XRPUSDT', 'LTCUSDT', 'DOTUSDT', 'LINKUSDT', 'SOLUSDT']

            self.symbol_combo.clear()
            self.symbol_combo.addItems(popular_symbols)

            # Tüm sembolleri arka planda asenkron olarak yükle
            QTimer.singleShot(5000, self.load_all_symbols)
            print("Popüler semboller yüklendi, diğerleri arka planda yüklenecek")
        except Exception as e:
            print(f"Sembol yükleme hatası: {e}")

    def load_all_symbols(self):
        """Tüm sembolleri arka planda yükle"""
        try:
            exchange_info = self.connector.client.get_exchange_info()
            all_symbols = [symbol['symbol'] for symbol in exchange_info['symbols']
                          if symbol['symbol'].endswith('USDT')]  # Sadece USDT çiftleri

            # Henüz eklenmemiş sembolleri ekle
            current_symbols = [self.symbol_combo.itemText(i) for i in range(self.symbol_combo.count())]
            new_symbols = [s for s in all_symbols if s not in current_symbols]

            self.symbol_combo.addItems(new_symbols)
            print(f"Toplam {len(all_symbols)} sembol yüklendi")
        except Exception as e:
            print(f"Tüm sembolleri yükleme hatası: {e}")

    def update_balance(self):
        """Bakiye bilgilerini güncelle ve toplam değeri hesapla"""
        print("Bakiye güncelleniyor...")
        balances = self.connector.get_account_balance()
        if not balances:
            print("Bakiye verisi alınamadı")
            return

        # Tüm fiyatları bir seferde al
        try:
            print("Fiyat bilgileri alınıyor...")
            all_prices = {ticker['symbol']: float(ticker['price'])
                         for ticker in self.connector.client.get_all_tickers()}
            print(f"{len(all_prices)} fiyat girişi alındı")
        except Exception as e:
            print(f"Fiyat bilgilerini alma hatası: {e}")
            all_prices = {}

        # Toplam değeri hesaplamak için
        total_value_usd = 0.0

        self.balance_table.setRowCount(0)
        print("Bakiye tablosu güncelleniyor...")
        row_index = 0
        for balance in balances:
            asset = balance['asset']
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked

            # Sıfır olmayan bakiyeleri göster
            if total > 0:
                self.balance_table.insertRow(row_index)
                self.balance_table.setItem(row_index, 0, QTableWidgetItem(asset))
                self.balance_table.setItem(row_index, 1, QTableWidgetItem(f"{free:.8f}"))
                self.balance_table.setItem(row_index, 2, QTableWidgetItem(f"{locked:.8f}"))

                # USD değerini hesapla
                value_usd = 0
                if asset == 'USDT':
                    value_usd = total
                else:
                    symbol = f"{asset}USDT"
                    if symbol in all_prices:
                        price = all_prices[symbol]
                        value_usd = total * price

                if value_usd > 0:
                    total_value_usd += value_usd
                    self.balance_table.setItem(row_index, 3, QTableWidgetItem(f"${value_usd:.2f}"))
                else:
                    self.balance_table.setItem(row_index, 3, QTableWidgetItem("N/A"))

                row_index += 1

        # Toplam değeri göster
        if total_value_usd > 0:
            self.total_value_label.setText(f"Total Value: ${total_value_usd:.2f}")

        print("Bakiye güncellendi")

    def update_orders(self):
        """Açık emir bilgilerini güncelle"""
        orders = self.connector.get_open_orders()
        if not orders:
            self.orders_table.setRowCount(0)
            return

        self.orders_table.setRowCount(0)
        for i, order in enumerate(orders):
            self.orders_table.insertRow(i)
            self.orders_table.setItem(i, 0, QTableWidgetItem(order['symbol']))
            self.orders_table.setItem(i, 1, QTableWidgetItem(order['side']))
            self.orders_table.setItem(i, 2, QTableWidgetItem(str(order['origQty'])))
            self.orders_table.setItem(i, 3, QTableWidgetItem(str(order['price'])))
            self.orders_table.setItem(i, 4, QTableWidgetItem(order['status']))

            # Her satır için iptal butonu ekle
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setProperty("order_id", order['orderId'])
            cancel_btn.setProperty("symbol", order['symbol'])
            cancel_btn.clicked.connect(self.cancel_selected_order)
            self.orders_table.setCellWidget(i, 5, cancel_btn)

        # Tablo başlıklarını güncelle (iptal butonu için sütun ekle)
        self.orders_table.setColumnCount(6)
        self.orders_table.setHorizontalHeaderLabels(["Symbol", "Side", "Quantity", "Price", "Status", "Action"])

    def update_order_history(self):
        """Emir geçmişi bilgilerini güncelle"""
        try:
            # Filtreler
            selected_symbol = self.history_symbol_combo.currentText()
            symbol = None if selected_symbol == "All Symbols" else selected_symbol

            limit = int(self.history_limit_combo.currentText())

            # Yükleniyor imleci göster
            self.setCursor(Qt.WaitCursor)

            # Emir geçmişini al
            orders = self.connector.get_order_history(symbol=symbol, limit=limit)
            if not orders:
                self.history_table.setRowCount(0)
                self.setCursor(Qt.ArrowCursor)  # İmleci geri yükle
                return

            # Tabloyu temizle
            self.history_table.setRowCount(0)

            # Tarihe göre sırala (en yeniler önce)
            orders.sort(key=lambda x: x['time'], reverse=True)

            for i, order in enumerate(orders):
                self.history_table.insertRow(i)

                # Zaman
                timestamp = order['time'] / 1000  # milisaniyeden saniyeye
                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                self.history_table.setItem(i, 0, QTableWidgetItem(date_str))

                # Diğer bilgiler
                self.history_table.setItem(i, 1, QTableWidgetItem(order['symbol']))
                self.history_table.setItem(i, 2, QTableWidgetItem(order['side']))
                self.history_table.setItem(i, 3, QTableWidgetItem(order['type']))

                qty = float(order['origQty'])
                self.history_table.setItem(i, 4, QTableWidgetItem(f"{qty:.8f}".rstrip('0').rstrip('.')))

                price = float(order['price']) if float(order['price']) > 0 else 0
                self.history_table.setItem(i, 5, QTableWidgetItem(f"{price:.8f}".rstrip('0').rstrip('.')))

                self.history_table.setItem(i, 6, QTableWidgetItem(self.get_status_text(order['status'])))

                # Toplam değer (Miktar * Fiyat)
                if price > 0:
                    total = qty * price
                    self.history_table.setItem(i, 7, QTableWidgetItem(f"{total:.8f}".rstrip('0').rstrip('.')))
                else:
                    self.history_table.setItem(i, 7, QTableWidgetItem("-"))

                # İlk 3 sütunu sola hizala
                for col in range(3):
                    item = self.history_table.item(i, col)
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)

                # Miktar, fiyat ve toplam sütunlarını sağa hizala
                for col in range(4, 8):
                    if self.history_table.item(i, col):
                        self.history_table.item(i, col).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            # Sembol listesini güncelle (filtreleme için)
            self.update_history_symbols(orders)

        except Exception as e:
            print(f"Emir geçmişi alma hatası: {e}")
        finally:
            self.setCursor(Qt.ArrowCursor)  # İmleci geri yükle

    def update_history_symbols(self, orders):
        """Emir geçmişinden sembolleri filtre listesine ekle"""
        current_symbols = set()
        for i in range(1, self.history_symbol_combo.count()):
            current_symbols.add(self.history_symbol_combo.itemText(i))

        new_symbols = set()
        for order in orders:
            new_symbols.add(order['symbol'])

        # Eksik sembolleri ekle
        for symbol in new_symbols:
            if symbol not in current_symbols:
                self.history_symbol_combo.addItem(symbol)

    def cancel_selected_order(self):
        """Seçilen emri iptal et"""
        try:
            sender = self.sender()
            order_id = sender.property("order_id")
            symbol = sender.property("symbol")

            reply = QMessageBox.question(
                self,
                "Cancel Order",
                f"Are you sure you want to cancel order ID {order_id} for {symbol}?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.Yes:
                if self.connector.cancel_order(symbol, order_id):
                    QMessageBox.information(self, "Success", "Order successfully canceled.")
                    self.update_orders()  # Açık emirleri güncelle
                    self.update_balance()  # Bakiyeleri güncelle
                else:
                    QMessageBox.critical(self, "Error", "An error occurred while canceling the order.")
        except Exception as e:
            print(f"Emir iptali sırasında beklenmeyen hata: {e}")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")

    def update_symbol_price(self):
        """Seçilen sembol için fiyat bilgilerini güncelle"""
        symbol = self.symbol_combo.currentText()
        if not symbol:
            return

        try:
            #opsiyon piyasaları için fiyatları alır
            options_data = self.connector.client.get_ticker(symbol=symbol)

            # Cevabın liste olduğu durumu kontrol eder
            if isinstance(options_data, list) and options_data:
                options_data = options_data[0]

            # Opsiyon piyasa veri tipinde verileri kontrol eder
            price = options_data.get('lastPrice', 'N/A')
            change = options_data.get('priceChangePercent', 'N/A')
            high = options_data.get('high', 'N/A')
            low = options_data.get('low', 'N/A')


            self.price_info_label.setText(
                f"Symbol: {symbol}\n"
                f"Current Price: {price}\n"
                f"24h Change: {change}%\n"
                f"24h High: {high}\n"
                f"24h Low: {low}\n"
            )
        except Exception as e:
            self.price_info_label.setText(f"Error getting price info: {e}")

    def update_trade_history(self):
        """İşlem geçmişini güncelle"""
        try:
            # Mevcut sembolü kontrol eder
            symbol = self.symbol_combo.currentText()

            if not symbol:
                self.trade_history_table.setRowCount(0)
                QMessageBox.warning(self, "Warning", "Please select a symbol first to view trade history.")
                return

            self.table_headers = ["Date", "Symbol", "Side", "Quantity", "Price", "Status"]

            # Son 10 işlemi alır
            trades = self.connector.client.get_my_trades(symbol=symbol, limit=10)

            self.trade_history_table.setRowCount(0)
            for i, trade in enumerate(trades):
                self.trade_history_table.insertRow(i)

                # Unix zaman damgasını okunabilir tarihe dönüştür
                timestamp = trade['time'] / 1000  # milisaniyeden saniyeye
                date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')

                self.trade_history_table.setItem(i, 0, QTableWidgetItem(date_str))
                self.trade_history_table.setItem(i, 1, QTableWidgetItem(trade['symbol']))
                self.trade_history_table.setItem(i, 2, QTableWidgetItem(trade['isBuyer'] and "BUY" or "SELL"))
                self.trade_history_table.setItem(i, 3, QTableWidgetItem(str(trade['qty'])))
                self.trade_history_table.setItem(i, 4, QTableWidgetItem(str(trade['price'])))
                self.trade_history_table.setItem(i, 5, QTableWidgetItem(trade['isBestMatch'] and "Best Match" or ""))

        except Exception as e:
            print(f"İşlem geçmişi alma hatası: {e}")
            QMessageBox.warning(self, "Error", f"Failed to retrieve trade history: {e}")

    def refresh_data(self):
        """Tüm verileri yenile"""
        if self.connector.connected:
            current_tab = self.tabs.currentIndex()

            # Bakiye sekmesi
            if current_tab == 0:
                self.update_balance()
            # Açık emirler sekmesi
            elif current_tab == 1:
                self.update_orders()
            # Emir geçmişi sekmesi
            elif current_tab == 2:
                self.update_order_history()
            # İşlem sekmesi
            elif current_tab == 3:
                self.update_symbol_price()
                self.update_trade_history()

    def on_order_type_changed(self, order_type):
        """Emir tipi değiştiğinde UI'yi güncelle"""
        # MARKET emirleri için fiyat girdisini gizle
        price_visible = order_type != "MARKET"
        self.price_input.setVisible(price_visible)

        # Alınacak fiyat için label kontrolü yapılır
        price_label = self.price_input.parentWidget().layout().labelForField(self.price_input)
        if price_label:
            price_label.setVisible(price_visible)

        # STOP_LOSS ve STOP_LOSS_LIMIT için durdurma fiyatını göster
        stop_price_visible = "STOP_LOSS" in order_type
        self.stop_price_input.setVisible(stop_price_visible)

        stop_price_label = self.stop_price_input.parentWidget().layout().labelForField(self.stop_price_input)
        if stop_price_label:
            stop_price_label.setVisible(stop_price_visible)

    def place_order(self):
        """Yeni bir emir ver"""
        symbol = self.symbol_combo.currentText()
        order_type = self.order_type_combo.currentText()
        side = self.side_combo.currentText()

        try:
            quantity = float(self.quantity_input.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Please enter a valid quantity.")
            return

        # Emir tipine göre parametreleri ayarla
        params = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity
        }

        # LIMIT ve STOP_LOSS_LIMIT emirleri fiyat gerektirir
        if order_type in ["LIMIT", "STOP_LOSS_LIMIT"]:
            try:
                price = float(self.price_input.text())
                params["price"] = price
                # LIMIT emirleri timeInForce parametresi gerektirir
                params["timeInForce"] = "GTC"  # Good Till Canceled
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid price.")
                return

        # STOP_LOSS ve STOP_LOSS_LIMIT emirleri durdurma fiyatı gerektirir
        if "STOP_LOSS" in order_type:
            try:
                stop_price = float(self.stop_price_input.text())
                params["stopPrice"] = stop_price
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid stop price.")
                return

        # Take Profit seçiliyse emir girer
        take_profit_text = self.take_profit_price.text().strip()
        if take_profit_text:
            try:
                take_profit_price = float(take_profit_text)
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid Take Profit price.")
                return

        # Stop Loss seçiliyse emir girer
        stop_loss_text = self.stop_loss_price.text().strip()
        if stop_loss_text:
            try:
                stop_loss_price = float(stop_loss_text)
            except ValueError:
                QMessageBox.warning(self, "Error", "Please enter a valid Stop Loss price.")
                return

        try:
            # Test emri gönder (gerçekten çalıştırmaz)
            self.connector.client.create_test_order(**params)

            # Gerçek emri gönder
            response = self.connector.client.create_order(**params)

            QMessageBox.information(
                self,
                "Success",
                f"Order placed successfully.\n"
                f"Order ID: {response['orderId']}\n"
                f"Status: {response['status']}"
            )

            # Gerçek Emir Sonrası TP/SL emirlerini gir
            try:
                if take_profit_text:
                    # Kar Gerçekleştirme Emri
                    self.connector.client.create_order(
                        symbol=symbol,
                        side="SELL" if side == "BUY" else "BUY",
                        type="LIMIT",
                        timeInForce="GTC",
                        quantity=quantity,
                        price=take_profit_price
                    )

                if stop_loss_text:
                    # Zarar Durdurma Emri
                    self.connector.client.create_order(
                        symbol=symbol,
                        side="SELL" if side == "BUY" else "BUY",
                        type="STOP_LOSS",
                        quantity=quantity,
                        stopPrice=stop_loss_price
                    )
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to set TP/SL: {e}")

            # Formu temizle
            self.quantity_input.clear()
            self.price_input.clear()
            self.stop_price_input.clear()

            # Verileri güncelle
            self.update_orders()
            self.update_balance()
            self.update_trade_history()

        except BinanceAPIException as e:
            QMessageBox.critical(self, "API Error", f"Order failed: {e.message}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Order failed: {e}")

    def get_status_text(self, status):
        """Emir durumunu görüntüleme metnine dönüştür"""
        status_map = {
            "NEW": "New",
            "PARTIALLY_FILLED": "Partially Filled",
            "FILLED": "Completed",
            "CANCELED": "Canceled",
            "PENDING_CANCEL": "Pending Cancel",
            "REJECTED": "Rejected",
            "EXPIRED": "Expired"
        }
        return status_map.get(status, status)