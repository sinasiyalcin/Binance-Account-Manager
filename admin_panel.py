from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QPushButton, QLabel, QTableWidget, QTableWidgetItem,
                             QTabWidget, QGroupBox, QFormLayout, QComboBox,
                             QLineEdit, QMessageBox, QCheckBox, QRadioButton,
                             QButtonGroup, QSpinBox, QDoubleSpinBox, QHeaderView,
                             QSplitter, QDialog, QDialogButtonBox, QProgressBar,
                             QTextEdit, QApplication, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QPropertyAnimation, QRect
from PyQt5.QtGui import QColor, QPainter, QMovie
import sys
import os
from binance.exceptions import BinanceAPIException
from transaction import AccountWidget
from datetime import datetime
import uuid


class LoadingWidget(QWidget):
    """Loading spinner widget"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100)
        self.angle = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.rotate)

    def start_animation(self):
        """Start the loading animation"""
        self.timer.start(50)  # Update every 50ms
        self.show()

    def stop_animation(self):
        """Stop the loading animation"""
        self.timer.stop()
        self.hide()

    def rotate(self):
        """Rotate the spinner"""
        self.angle = (self.angle + 10) % 360
        self.update()

    def paintEvent(self, event):
        """Paint the loading spinner"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Set up the painter
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)

        # Draw the spinner
        painter.setPen(Qt.NoPen)
        for i in range(8):
            alpha = 255 * (i + 1) / 8
            color = QColor(0, 120, 215, int(alpha))
            painter.setBrush(color)

            painter.drawEllipse(-5, -25, 10, 15)
            painter.rotate(45)


class LoadingOverlay(QWidget):
    """Loading overlay with spinner and message"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 128);")

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        # Loading spinner
        self.spinner = LoadingWidget()
        layout.addWidget(self.spinner, alignment=Qt.AlignCenter)

        # Loading message
        self.message_label = QLabel("Loading...")
        self.message_label.setStyleSheet("""
            color: white; 
            font-size: 16px; 
            font-weight: bold;
            background-color: rgba(0, 0, 0, 180);
            padding: 10px;
            border-radius: 5px;
        """)
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label, alignment=Qt.AlignCenter)

        self.setLayout(layout)
        self.hide()

    def show_loading(self, message="Loading..."):
        """Show loading overlay with message"""
        self.message_label.setText(message)
        self.spinner.start_animation()
        self.show()
        QApplication.processEvents()

    def hide_loading(self):
        """Hide loading overlay"""
        self.spinner.stop_animation()
        self.hide()

    def update_message(self, message):
        """Update loading message"""
        self.message_label.setText(message)
        QApplication.processEvents()


class InitializationThread(QThread):
    """Thread for initializing admin panel data"""
    progress_update = pyqtSignal(str)  # message
    accounts_loaded = pyqtSignal(dict)  # accounts data
    summary_loaded = pyqtSignal(list)  # summary data
    initialization_complete = pyqtSignal()

    def __init__(self, account_manager, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager

    def run(self):
        """Initialize all data in background"""
        try:
            # Step 1: Load accounts
            self.progress_update.emit("Loading accounts...")
            accounts = self.account_manager.get_all_accounts()

            # Step 2: Test connections
            self.progress_update.emit("Testing connections...")
            accounts_status = {}

            for i, (name, data) in enumerate(accounts.items()):
                self.progress_update.emit(f"Testing connection {i + 1}/{len(accounts)}: {name}")

                try:
                    temp_widget = AccountWidget(name, data)
                    if temp_widget.connector and temp_widget.connector.connected:
                        accounts_status[name] = {
                            "data": data,
                            "status": "Connected",
                            "color": "green"
                        }
                    else:
                        accounts_status[name] = {
                            "data": data,
                            "status": "Connection Failed",
                            "color": "red"
                        }
                    temp_widget.deleteLater()
                except Exception as e:
                    accounts_status[name] = {
                        "data": data,
                        "status": f"Error: {str(e)[:20]}",
                        "color": "red"
                    }

            self.accounts_loaded.emit(accounts_status)

            # Step 3: Load summary data
            self.progress_update.emit("Loading account summaries...")
            summary_data = []

            for i, (name, account_info) in enumerate(accounts_status.items()):
                self.progress_update.emit(f"Loading summary {i + 1}/{len(accounts_status)}: {name}")

                summary_row = {
                    "name": name,
                    "status": account_info["status"],
                    "status_color": account_info["color"],
                    "total_value": "-",
                    "open_orders": "-"
                }

                if account_info["status"] == "Connected":
                    try:
                        temp_widget = AccountWidget(name, account_info["data"])
                        if temp_widget.connector and temp_widget.connector.connected:
                            # Get balance
                            balances = temp_widget.connector.get_account_balance()
                            total_value = 0

                            if balances:
                                for balance in balances:
                                    if balance["asset"] == "USDT":
                                        total_value += float(balance["free"])

                            # Get open orders
                            open_orders = temp_widget.connector.get_open_orders()
                            open_count = len(open_orders) if open_orders else 0

                            summary_row["total_value"] = f"{total_value:.2f}"
                            summary_row["open_orders"] = str(open_count)

                        temp_widget.deleteLater()
                    except Exception as e:
                        summary_row["status"] = "Error"
                        summary_row["status_color"] = "red"

                summary_data.append(summary_row)

            self.summary_loaded.emit(summary_data)

            # Step 4: Complete
            self.progress_update.emit("Initialization complete!")
            self.initialization_complete.emit()

        except Exception as e:
            self.progress_update.emit(f"Error during initialization: {str(e)}")


class BulkOrderThread(QThread):
    """Toplu emir işlemlerini arka planda çalıştıran thread"""
    progress_update = pyqtSignal(str, str)  # account_name, message
    finished = pyqtSignal(dict)  # results

    def __init__(self, accounts_data, order_params, parent=None):
        super().__init__(parent)
        self.accounts_data = accounts_data
        self.order_params = order_params
        self.results = {}

    def run(self):
        """Thread'in ana çalışma metodu"""
        total_accounts = len(self.accounts_data)
        success_count = 0
        error_count = 0

        for i, (account_name, account_data) in enumerate(self.accounts_data.items()):
            self.progress_update.emit(account_name, f"İşleniyor... ({i + 1}/{total_accounts})")

            try:
                # Mevcut AccountWidget'ı kullan
                temp_widget = AccountWidget(account_name, account_data)

                if not temp_widget.connector or not temp_widget.connector.connected:
                    self.results[account_name] = {
                        "status": "Error",
                        "message": "Bağlantı kurulamadı"
                    }
                    self.progress_update.emit(account_name, "Bağlantı hatası")
                    error_count += 1
                    continue

                # Emir parametrelerini hazırla
                symbol = self.order_params["symbol"]
                side = self.order_params["side"]
                order_type = self.order_params["type"]
                quantity = self.order_params["quantity"]

                # Miktarı hesapla (yüzde bazlı ise)
                if self.order_params.get("quantity_type") == "percentage":
                    percentage = quantity / 100.0

                    if side == "BUY":
                        # USDT bakiyesi al
                        balances = temp_widget.connector.get_account_balance()
                        usdt_balance = 0
                        for balance in balances:
                            if balance["asset"] == "USDT":
                                usdt_balance = float(balance["free"])
                                break

                        if usdt_balance <= 0:
                            self.results[account_name] = {
                                "status": "Error",
                                "message": "Yetersiz USDT bakiyesi"
                            }
                            error_count += 1
                            continue

                        # Güncel fiyatı al
                        ticker = temp_widget.connector.client.get_symbol_ticker(symbol=symbol)
                        price = float(ticker["price"])
                        quantity = (usdt_balance * percentage) / price
                    else:
                        # Kripto asset bakiyesi al
                        asset = symbol.replace("USDT", "")
                        balances = temp_widget.connector.get_account_balance()
                        asset_balance = 0
                        for balance in balances:
                            if balance["asset"] == asset:
                                asset_balance = float(balance["free"])
                                break

                        if asset_balance <= 0:
                            self.results[account_name] = {
                                "status": "Error",
                                "message": f"Yetersiz {asset} bakiyesi"
                            }
                            error_count += 1
                            continue

                        quantity = asset_balance * percentage

                # Emir parametrelerini oluştur
                params = {
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "quantity": self.round_quantity(quantity, symbol)
                }

                # Fiyat parametrelerini ekle
                if order_type in ["LIMIT", "STOP_LOSS_LIMIT"]:
                    params["price"] = self.order_params["price"]
                    params["timeInForce"] = self.order_params.get("timeInForce", "GTC")

                if "STOP_LOSS" in order_type:
                    params["stopPrice"] = self.order_params["stop_price"]

                # Test emri
                temp_widget.connector.client.create_test_order(**params)

                # Gerçek emir
                response = temp_widget.connector.client.create_order(**params)

                # Birincil emir başarılı, TP/SL emirlerini kontrol et
                primary_order_result = {
                    "status": "Success" if response["status"] == "FILLED" else "Pending",
                    "message": f"Emir oluşturuldu: {response['orderId']}",
                    "order_id": response["orderId"],
                    "binance_status": response["status"]
                }

                # TP/SL işlemleri
                tp_sl_messages = []

                # Take Profit emirini kontrol et
                if self.order_params.get("enable_take_profit", False) and self.order_params.get("take_profit_price"):
                    try:
                        tp_side = "SELL" if side == "BUY" else "BUY"
                        tp_params = {
                            "symbol": symbol,
                            "side": tp_side,
                            "type": "LIMIT",
                            "quantity": params["quantity"],
                            "price": self.order_params["take_profit_price"],
                            "timeInForce": "GTC"
                        }

                        tp_response = temp_widget.connector.client.create_order(**tp_params)
                        tp_sl_messages.append(f"TP: {tp_response['orderId']}")
                    except Exception as e:
                        tp_sl_messages.append(f"TP Error: {str(e)[:30]}")

                # Stop Loss emirini kontrol et
                if self.order_params.get("enable_stop_loss", False) and self.order_params.get("stop_loss_price"):
                    try:
                        sl_side = "SELL" if side == "BUY" else "BUY"
                        sl_params = {
                            "symbol": symbol,
                            "side": sl_side,
                            "type": "STOP_LOSS_LIMIT",
                            "quantity": params["quantity"],
                            "price": self.order_params["stop_loss_price"],
                            "stopPrice": self.order_params["stop_loss_price"],
                            "timeInForce": "GTC"
                        }

                        sl_response = temp_widget.connector.client.create_order(**sl_params)
                        tp_sl_messages.append(f"SL: {sl_response['orderId']}")
                    except Exception as e:
                        tp_sl_messages.append(f"SL Error: {str(e)[:30]}")

                # Sonuç mesajını güncelle
                if tp_sl_messages:
                    primary_order_result["message"] += f" | {', '.join(tp_sl_messages)}"

                self.results[account_name] = primary_order_result

                if response["status"] == "FILLED":
                    success_count += 1
                    self.progress_update.emit(account_name, "Emir gerçekleşti")
                else:
                    self.progress_update.emit(account_name, "Emir oluşturuldu (bekliyor)")

                temp_widget.deleteLater()

            except BinanceAPIException as e:
                self.results[account_name] = {
                    "status": "Error",
                    "message": f"API Hatası: {e.message}"
                }
                self.progress_update.emit(account_name, f"API Hatası: {e.message}")
                error_count += 1
            except Exception as e:
                self.results[account_name] = {
                    "status": "Error",
                    "message": f"Hata: {str(e)}"
                }
                self.progress_update.emit(account_name, f"Hata: {str(e)}")
                error_count += 1

        # Sonuçları gönder
        summary = {
            "total": total_accounts,
            "success": success_count,
            "error": error_count,
            "results": self.results
        }
        self.finished.emit(summary)

    def round_quantity(self, quantity, symbol):
        """Miktarı sembol için uygun ondalık basamaklara yuvarla"""
        if "BTC" in symbol:
            return round(quantity, 6)
        elif "ETH" in symbol:
            return round(quantity, 5)
        else:
            return round(quantity, 2)


class OrderActionThread(QThread):
    """Emir işlemlerini (iptal/değiştir) arka planda çalıştıran thread"""
    progress_update = pyqtSignal(str, str)  # order_id, message
    finished = pyqtSignal(dict)  # results

    def __init__(self, orders_data, action, modify_params=None, parent=None):
        super().__init__(parent)
        self.orders_data = orders_data  # {order_id: {order_info, account_data}}
        self.action = action  # "cancel" or "modify"
        self.modify_params = modify_params
        self.results = {}

    def run(self):
        """Thread'in ana çalışma metodu"""
        total_orders = len(self.orders_data)
        success_count = 0
        error_count = 0

        for i, (order_id, data) in enumerate(self.orders_data.items()):
            order_info = data["order_info"]
            account_data = data["account_data"]
            account_name = data["account_name"]

            self.progress_update.emit(order_id, f"İşleniyor... ({i + 1}/{total_orders})")

            try:
                # Mevcut AccountWidget'ı kullan
                temp_widget = AccountWidget(account_name, account_data)

                if not temp_widget.connector or not temp_widget.connector.connected:
                    self.results[order_id] = {
                        "status": "Error",
                        "message": "Bağlantı kurulamadı",
                        "account": account_name
                    }
                    error_count += 1
                    continue

                if self.action == "cancel":
                    # AccountWidget'daki cancel_order methodunu kullan
                    if temp_widget.connector.cancel_order(order_info["symbol"], order_info["orderId"]):
                        self.results[order_id] = {
                            "status": "Success",
                            "message": "Emir iptal edildi",
                            "account": account_name
                        }
                        success_count += 1
                        self.progress_update.emit(order_id, "İptal edildi")
                    else:
                        self.results[order_id] = {
                            "status": "Error",
                            "message": "İptal işlemi başarısız",
                            "account": account_name
                        }
                        error_count += 1

                elif self.action == "modify":
                    # Önce eski emri iptal et
                    temp_widget.connector.cancel_order(order_info["symbol"], order_info["orderId"])

                    # Yeni emir oluştur
                    new_params = {
                        "symbol": order_info["symbol"],
                        "side": order_info["side"],
                        "type": order_info["type"],
                        "quantity": float(order_info["origQty"])
                    }

                    # Değişiklik parametrelerini uygula
                    if self.modify_params:
                        if "price" in self.modify_params:
                            new_params["price"] = self.modify_params["price"]
                        if "quantity" in self.modify_params:
                            new_params["quantity"] = self.modify_params["quantity"]
                        if "stop_price" in self.modify_params:
                            new_params["stopPrice"] = self.modify_params["stop_price"]

                    # Emir tipine göre parametreleri ayarla
                    if new_params["type"] in ["LIMIT", "STOP_LOSS_LIMIT"]:
                        if "price" not in new_params:
                            new_params["price"] = float(order_info["price"])
                        new_params["timeInForce"] = "GTC"

                    if "STOP_LOSS" in new_params["type"]:
                        if "stopPrice" not in new_params:
                            new_params["stopPrice"] = float(order_info.get("stopPrice", order_info["price"]))

                    # Yeni emri oluştur
                    response = temp_widget.connector.client.create_order(**new_params)

                    self.results[order_id] = {
                        "status": "Success",
                        "message": f"Emir değiştirildi: {response['orderId']}",
                        "account": account_name,
                        "new_order_id": response["orderId"]
                    }
                    success_count += 1
                    self.progress_update.emit(order_id, "Değiştirildi")

                temp_widget.deleteLater()

            except BinanceAPIException as e:
                if "Unknown order" in str(e):
                    self.results[order_id] = {
                        "status": "Warning",
                        "message": "Emir zaten mevcut değil",
                        "account": account_name
                    }
                    success_count += 1
                else:
                    self.results[order_id] = {
                        "status": "Error",
                        "message": f"API Hatası: {e.message}",
                        "account": account_name
                    }
                    error_count += 1
                self.progress_update.emit(order_id, f"Hata: {str(e)}")
            except Exception as e:
                self.results[order_id] = {
                    "status": "Error",
                    "message": f"Hata: {str(e)}",
                    "account": account_name
                }
                self.progress_update.emit(order_id, f"Hata: {str(e)}")
                error_count += 1

        # Sonuçları gönder
        summary = {
            "total": total_orders,
            "success": success_count,
            "error": error_count,
            "results": self.results
        }
        self.finished.emit(summary)


class AdminPanel(QWidget):
    refresh_accounts_signal = pyqtSignal()

    def __init__(self, account_manager, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        self.current_thread = None
        self.initialization_thread = None
        self.accounts_data = {}

        self.init_ui()
        self.start_initialization()

    def init_ui(self):
        """Initialize UI with loading overlay"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        # Main content widget
        self.main_content = QWidget()
        self.setup_main_content()
        layout.addWidget(self.main_content)

        # Loading overlay
        self.loading_overlay = LoadingOverlay(self)
        layout.addWidget(self.loading_overlay)

        self.setLayout(layout)

        # Hide main content initially
        self.main_content.hide()

    def setup_main_content(self):
        """Setup the main content of admin panel"""
        layout = QVBoxLayout()

        # Tab widget
        self.tabs = QTabWidget()

        # Tab 1: Toplu Emir
        self.bulk_order_tab = QWidget()
        self.setup_bulk_order_tab()

        # Tab 2: Hesap Özeti
        self.summary_tab = QWidget()
        self.setup_summary_tab()

        # Tab 3: Açık Emirler
        self.open_orders_tab = QWidget()
        self.setup_open_orders_tab()

        self.tabs.addTab(self.bulk_order_tab, "Bulk Order")
        self.tabs.addTab(self.summary_tab, "Account Summary")
        self.tabs.addTab(self.open_orders_tab, "Open Orders")

        layout.addWidget(self.tabs)
        self.main_content.setLayout(layout)

    def resizeEvent(self, event):
        """Handle resize events to properly position loading overlay"""
        super().resizeEvent(event)
        if hasattr(self, 'loading_overlay'):
            self.loading_overlay.setGeometry(self.rect())

    def start_initialization(self):
        """Start the initialization process"""
        self.loading_overlay.show_loading("Initializing Admin Panel...")

        # Start initialization thread
        self.initialization_thread = InitializationThread(self.account_manager)
        self.initialization_thread.progress_update.connect(self.on_initialization_progress)
        self.initialization_thread.accounts_loaded.connect(self.on_accounts_loaded)
        self.initialization_thread.summary_loaded.connect(self.on_summary_loaded)
        self.initialization_thread.initialization_complete.connect(self.on_initialization_complete)
        self.initialization_thread.start()

    @pyqtSlot(str)
    def on_initialization_progress(self, message):
        """Update initialization progress"""
        self.loading_overlay.update_message(message)

    @pyqtSlot(dict)
    def on_accounts_loaded(self, accounts_data):
        """Handle accounts loaded"""
        self.accounts_data = accounts_data
        self.populate_accounts_table()

    @pyqtSlot(list)
    def on_summary_loaded(self, summary_data):
        """Handle summary loaded"""
        self.populate_summary_table(summary_data)

    @pyqtSlot()
    def on_initialization_complete(self):
        """Handle initialization completion"""
        self.loading_overlay.hide_loading()
        self.main_content.show()

        # Clean up thread
        if self.initialization_thread:
            self.initialization_thread.deleteLater()
            self.initialization_thread = None

    def populate_accounts_table(self):
        """Populate accounts table with loaded data"""
        self.accounts_table.setRowCount(len(self.accounts_data))

        # Update account filter
        if hasattr(self, 'orders_account_filter'):
            current_selection = self.orders_account_filter.currentText()
            self.orders_account_filter.clear()
            self.orders_account_filter.addItem("ALL")
            self.orders_account_filter.addItems(list(self.accounts_data.keys()))

            # Restore previous selection
            index = self.orders_account_filter.findText(current_selection)
            if index >= 0:
                self.orders_account_filter.setCurrentIndex(index)

        for i, (name, account_info) in enumerate(self.accounts_data.items()):
            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            self.accounts_table.setItem(i, 0, checkbox)

            # Account name
            self.accounts_table.setItem(i, 1, QTableWidgetItem(name))

            # Status
            status_item = QTableWidgetItem(account_info["status"])
            status_item.setForeground(QColor(account_info["color"]))
            self.accounts_table.setItem(i, 2, status_item)

    def populate_summary_table(self, summary_data):
        """Populate summary table with loaded data"""
        self.summary_table.setRowCount(len(summary_data))

        for i, row_data in enumerate(summary_data):
            self.summary_table.setItem(i, 0, QTableWidgetItem(row_data["name"]))

            status_item = QTableWidgetItem(row_data["status"])
            status_item.setForeground(QColor(row_data["status_color"]))
            self.summary_table.setItem(i, 1, status_item)

            self.summary_table.setItem(i, 2, QTableWidgetItem(row_data["total_value"]))
            self.summary_table.setItem(i, 3, QTableWidgetItem(row_data["open_orders"]))

    def setup_bulk_order_tab(self):
        layout = QVBoxLayout()

        # Hesap Seçimi
        accounts_group = QGroupBox("Select Accounts")
        accounts_layout = QVBoxLayout()

        self.accounts_table = QTableWidget()
        self.accounts_table.setColumnCount(3)
        self.accounts_table.setHorizontalHeaderLabels(["Select", "Account", "Status"])
        self.accounts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.accounts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.accounts_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        accounts_layout.addWidget(self.accounts_table)

        # Seçim butonları
        select_layout = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all_accounts)
        select_none_btn = QPushButton("Select None")
        select_none_btn.clicked.connect(self.select_no_accounts)
        refresh_btn = QPushButton("Refresh Accounts")
        refresh_btn.clicked.connect(self.refresh_accounts_data)

        select_layout.addWidget(select_all_btn)
        select_layout.addWidget(select_none_btn)
        select_layout.addWidget(refresh_btn)
        accounts_layout.addLayout(select_layout)

        accounts_group.setLayout(accounts_layout)
        layout.addWidget(accounts_group)

        # Emir Parametreleri
        order_group = QGroupBox("Order Parameters")
        order_layout = QFormLayout()

        # Sembol
        self.symbol_combo = QComboBox()
        self.symbol_combo.setEditable(True)
        self.symbol_combo.addItems(["BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT"])
        order_layout.addRow("Symbol:", self.symbol_combo)

        # İşlem yönü
        self.side_combo = QComboBox()
        self.side_combo.addItems(["BUY", "SELL"])
        order_layout.addRow("Side:", self.side_combo)

        # Emir tipi
        self.order_type_combo = QComboBox()
        self.order_type_combo.addItems(["MARKET", "LIMIT", "STOP_LOSS", "STOP_LOSS_LIMIT"])
        self.order_type_combo.currentTextChanged.connect(self.on_order_type_changed)
        order_layout.addRow("Order Type:", self.order_type_combo)

        # Miktar tipi
        quantity_layout = QHBoxLayout()
        self.quantity_group = QButtonGroup()

        self.fixed_radio = QRadioButton("Fixed Amount")
        self.fixed_radio.setChecked(True)
        self.percentage_radio = QRadioButton("Percentage of Balance")

        self.quantity_group.addButton(self.fixed_radio, 1)
        self.quantity_group.addButton(self.percentage_radio, 2)

        quantity_layout.addWidget(self.fixed_radio)
        quantity_layout.addWidget(self.percentage_radio)
        order_layout.addRow("Quantity Type:", quantity_layout)

        # Miktar
        quantity_input_layout = QHBoxLayout()
        self.quantity_input = QLineEdit()
        self.quantity_input.setPlaceholderText("0.001")
        self.percentage_input = QSpinBox()
        self.percentage_input.setMinimum(1)
        self.percentage_input.setMaximum(100)
        self.percentage_input.setValue(20)
        self.percentage_input.setSuffix("%")
        self.percentage_input.setVisible(False)

        quantity_input_layout.addWidget(self.quantity_input)
        quantity_input_layout.addWidget(self.percentage_input)
        order_layout.addRow("Amount:", quantity_input_layout)

        # Fiyat (LIMIT için)
        self.price_label = QLabel("Price:")
        self.price_input = QLineEdit()
        self.price_input.setPlaceholderText("50000")
        order_layout.addRow(self.price_label, self.price_input)

        # Stop fiyat
        self.stop_price_label = QLabel("Stop Price:")
        self.stop_price_input = QLineEdit()
        self.stop_price_input.setPlaceholderText("49000")
        order_layout.addRow(self.stop_price_label, self.stop_price_input)

        # Take Profit seçeneği
        tp_layout = QHBoxLayout()
        self.take_profit_checkbox = QCheckBox("Enable Take Profit")
        self.take_profit_input = QLineEdit()
        self.take_profit_input.setPlaceholderText("52000")
        self.take_profit_input.setEnabled(False)

        self.take_profit_checkbox.toggled.connect(self.take_profit_input.setEnabled)
        tp_layout.addWidget(self.take_profit_checkbox)
        tp_layout.addWidget(self.take_profit_input)
        order_layout.addRow("Take Profit:", tp_layout)

        # Stop Loss seçeneği
        sl_layout = QHBoxLayout()
        self.stop_loss_checkbox = QCheckBox("Enable Stop Loss")
        self.stop_loss_input = QLineEdit()
        self.stop_loss_input.setPlaceholderText("48000")
        self.stop_loss_input.setEnabled(False)

        self.stop_loss_checkbox.toggled.connect(self.stop_loss_input.setEnabled)
        sl_layout.addWidget(self.stop_loss_checkbox)
        sl_layout.addWidget(self.stop_loss_input)
        order_layout.addRow("Stop Loss:", sl_layout)

        # Başlangıçta görünürlüğü ayarla
        self.on_order_type_changed("MARKET")

        # Miktar tipi değişikliğini dinle
        self.quantity_group.buttonClicked.connect(self.on_quantity_type_changed)

        order_group.setLayout(order_layout)
        layout.addWidget(order_group)

        # İlerleme
        self.progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.progress_text = QTextEdit()
        self.progress_text.setMaximumHeight(100)
        self.progress_text.setVisible(False)
        progress_layout.addWidget(self.progress_text)

        self.progress_group.setLayout(progress_layout)
        layout.addWidget(self.progress_group)

        # Execute butonu
        self.execute_btn = QPushButton("Execute Bulk Order")
        self.execute_btn.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        self.execute_btn.clicked.connect(self.execute_bulk_order)
        layout.addWidget(self.execute_btn)

        self.bulk_order_tab.setLayout(layout)

    def setup_summary_tab(self):
        layout = QVBoxLayout()

        # Özet tablosu
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(4)
        self.summary_table.setHorizontalHeaderLabels(["Account", "Status", "Total Value (USDT)", "Open Orders"])
        self.summary_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.summary_table)

        # Yenileme butonu
        refresh_summary_btn = QPushButton("Refresh Summary")
        refresh_summary_btn.clicked.connect(self.refresh_summary_data)
        layout.addWidget(refresh_summary_btn)

        self.summary_tab.setLayout(layout)

    def setup_open_orders_tab(self):
        layout = QVBoxLayout()

        # Filtre ve kontrol seçenekleri
        filter_group = QGroupBox("Filters and Actions")
        filter_layout = QHBoxLayout()

        # Sembol filtresi
        filter_layout.addWidget(QLabel("Symbol:"))
        self.orders_symbol_filter = QComboBox()
        self.orders_symbol_filter.setEditable(True)
        self.orders_symbol_filter.addItems(["ALL", "BTCUSDT", "ETHUSDT", "BNBUSDT", "ADAUSDT", "DOGEUSDT"])
        filter_layout.addWidget(self.orders_symbol_filter)

        # Hesap filtresi
        filter_layout.addWidget(QLabel("Account:"))
        self.orders_account_filter = QComboBox()
        self.orders_account_filter.addItem("ALL")
        filter_layout.addWidget(self.orders_account_filter)

        # Yenileme butonu
        refresh_orders_btn = QPushButton("Refresh Orders")
        refresh_orders_btn.clicked.connect(self.load_open_orders)
        filter_layout.addWidget(refresh_orders_btn)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Açık emirler tablosu
        self.open_orders_table = QTableWidget()
        self.open_orders_table.setColumnCount(10)
        self.open_orders_table.setHorizontalHeaderLabels([
            "Select", "Account", "Symbol", "Side", "Type", "Quantity",
            "Price", "Stop Price", "Status", "Order ID"
        ])

        # Tablo ayarları
        header = self.open_orders_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Select
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Account
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Symbol
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Side
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Type
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Quantity
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Price
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Stop Price
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(9, QHeaderView.Stretch)  # Order ID

        self.open_orders_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.open_orders_table)

        # Seçim butonları
        selection_layout = QHBoxLayout()

        select_all_orders_btn = QPushButton("Select All")
        select_all_orders_btn.clicked.connect(self.select_all_orders)
        selection_layout.addWidget(select_all_orders_btn)

        select_none_orders_btn = QPushButton("Select None")
        select_none_orders_btn.clicked.connect(self.select_no_orders)
        selection_layout.addWidget(select_none_orders_btn)

        layout.addLayout(selection_layout)

        # Eylem butonları
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout()

        # İptal butonu
        self.cancel_selected_btn = QPushButton("Cancel Selected Orders")
        self.cancel_selected_btn.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 8px; background-color: #ff6b6b; color: white;"
        )
        self.cancel_selected_btn.clicked.connect(self.cancel_selected_orders)
        action_layout.addWidget(self.cancel_selected_btn)

        # Değiştir butonu
        self.modify_selected_btn = QPushButton("Modify Selected Orders")
        self.modify_selected_btn.setStyleSheet(
            "font-size: 12px; font-weight: bold; padding: 8px; background-color: #4ecdc4; color: white;"
        )
        self.modify_selected_btn.clicked.connect(self.modify_selected_orders)
        action_layout.addWidget(self.modify_selected_btn)

        action_group.setLayout(action_layout)
        layout.addWidget(action_group)

        # İlerleme
        self.orders_progress_group = QGroupBox("Progress")
        orders_progress_layout = QVBoxLayout()

        self.orders_progress_bar = QProgressBar()
        self.orders_progress_bar.setVisible(False)
        orders_progress_layout.addWidget(self.orders_progress_bar)

        self.orders_progress_text = QTextEdit()
        self.orders_progress_text.setMaximumHeight(100)
        self.orders_progress_text.setVisible(False)
        orders_progress_layout.addWidget(self.orders_progress_text)

        self.orders_progress_group.setLayout(orders_progress_layout)
        layout.addWidget(self.orders_progress_group)

        self.open_orders_tab.setLayout(layout)

    def refresh_accounts_data(self):
        """Hesap bilgilerini yeniler"""
        self.loading_overlay.show_loading("Refreshing accounts...")

        # Start initialization thread for refresh
        self.initialization_thread = InitializationThread(self.account_manager)
        self.initialization_thread.progress_update.connect(self.on_initialization_progress)
        self.initialization_thread.accounts_loaded.connect(self.on_accounts_loaded)
        self.initialization_thread.initialization_complete.connect(self.loading_overlay.hide_loading)
        self.initialization_thread.start()

    def refresh_summary_data(self):
        """Özet verilerini yeniler"""
        self.loading_overlay.show_loading("Refreshing summary...")

        self.initialization_thread = InitializationThread(self.account_manager)
        self.initialization_thread.progress_update.connect(self.on_initialization_progress)
        self.initialization_thread.summary_loaded.connect(self.on_summary_loaded)
        self.initialization_thread.initialization_complete.connect(self.loading_overlay.hide_loading)
        self.initialization_thread.start()

    def load_open_orders(self):
        """Açık emirlerin yüklenmesi"""
        self.loading_overlay.show_loading("Loading open orders...")

        # Use QTimer to make it async
        QTimer.singleShot(100, self._load_open_orders_async)

    def _load_open_orders_async(self):
        """Emirlerin asenkron yüklenmesi"""
        try:
            accounts = self.account_manager.get_all_accounts()
            all_orders = []

            # Filtreleri al
            symbol_filter = self.orders_symbol_filter.currentText().strip()
            account_filter = self.orders_account_filter.currentText().strip()

            if symbol_filter == "ALL":
                symbol_filter = None
            if account_filter == "ALL":
                account_filter = None

            total_accounts = len(accounts)
            for i, (account_name, account_data) in enumerate(accounts.items()):
                self.loading_overlay.update_message(f"Loading orders {i + 1}/{total_accounts}: {account_name}")

                # Hesap filtresi
                if account_filter and account_name != account_filter:
                    continue

                try:
                    # AccountWidget'ı kullanarak açık emirleri al
                    temp_widget = AccountWidget(account_name, account_data)
                    if temp_widget.connector and temp_widget.connector.connected:
                        # Mevcut get_open_orders methodunu kullan
                        open_orders = temp_widget.connector.get_open_orders()

                        if open_orders:
                            for order in open_orders:
                                # Sembol filtresi
                                if symbol_filter and order["symbol"] != symbol_filter:
                                    continue

                                order["account_name"] = account_name
                                order["account_data"] = account_data
                                all_orders.append(order)

                    temp_widget.deleteLater()
                except Exception as e:
                    continue

            # Tabloyu doldur
            self.open_orders_table.setRowCount(len(all_orders))

            for i, order in enumerate(all_orders):
                # Checkbox
                checkbox = QTableWidgetItem()
                checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                checkbox.setCheckState(Qt.Unchecked)
                self.open_orders_table.setItem(i, 0, checkbox)

                # Hesap adı
                self.open_orders_table.setItem(i, 1, QTableWidgetItem(order["account_name"]))

                # Sembol
                self.open_orders_table.setItem(i, 2, QTableWidgetItem(order["symbol"]))

                # Side
                side_item = QTableWidgetItem(order["side"])
                if order["side"] == "BUY":
                    side_item.setForeground(QColor("green"))
                else:
                    side_item.setForeground(QColor("red"))
                self.open_orders_table.setItem(i, 3, side_item)

                # Type
                self.open_orders_table.setItem(i, 4, QTableWidgetItem(order["type"]))

                # Quantity
                self.open_orders_table.setItem(i, 5, QTableWidgetItem(f"{float(order['origQty']):.8f}"))

                # Price
                price_text = f"{float(order['price']):.8f}" if order.get("price") and float(
                    order["price"]) > 0 else "Market"
                self.open_orders_table.setItem(i, 6, QTableWidgetItem(price_text))

                # Stop Price
                stop_price_text = f"{float(order['stopPrice']):.8f}" if order.get("stopPrice") else "-"
                self.open_orders_table.setItem(i, 7, QTableWidgetItem(stop_price_text))

                # Status
                status_item = QTableWidgetItem(order["status"])
                if order["status"] == "NEW":
                    status_item.setForeground(QColor("blue"))
                elif order["status"] == "PARTIALLY_FILLED":
                    status_item.setForeground(QColor("orange"))
                self.open_orders_table.setItem(i, 8, status_item)

                # Order ID
                self.open_orders_table.setItem(i, 9, QTableWidgetItem(str(order["orderId"])))

            # Bilgi mesajı
            if len(all_orders) == 0:
                QMessageBox.information(self, "Info", "No open orders found.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load orders: {str(e)}")
        finally:
            self.loading_overlay.hide_loading()

    def select_all_accounts(self):
        """Tüm hesapları seç"""
        for i in range(self.accounts_table.rowCount()):
            self.accounts_table.item(i, 0).setCheckState(Qt.Checked)

    def select_no_accounts(self):
        """Tüm hesapların seçimini kaldır"""
        for i in range(self.accounts_table.rowCount()):
            self.accounts_table.item(i, 0).setCheckState(Qt.Unchecked)

    def select_all_orders(self):
        """Tüm emirleri seç"""
        for i in range(self.open_orders_table.rowCount()):
            self.open_orders_table.item(i, 0).setCheckState(Qt.Checked)

    def select_no_orders(self):
        """Tüm emirlerin seçimini kaldır"""
        for i in range(self.open_orders_table.rowCount()):
            self.open_orders_table.item(i, 0).setCheckState(Qt.Unchecked)

    def get_selected_orders(self):
        """Seçilen emirleri döndür"""
        selected_orders = {}

        for i in range(self.open_orders_table.rowCount()):
            if self.open_orders_table.item(i, 0).checkState() == Qt.Checked:
                order_id = self.open_orders_table.item(i, 9).text()
                account_name = self.open_orders_table.item(i, 1).text()

                # Emir bilgilerini topla
                order_info = {
                    "orderId": order_id,
                    "symbol": self.open_orders_table.item(i, 2).text(),
                    "side": self.open_orders_table.item(i, 3).text(),
                    "type": self.open_orders_table.item(i, 4).text(),
                    "origQty": self.open_orders_table.item(i, 5).text(),
                    "price": self.open_orders_table.item(i, 6).text().replace("Market", "0"),
                    "status": self.open_orders_table.item(i, 8).text()
                }

                # Stop price varsa ekle
                stop_price = self.open_orders_table.item(i, 7).text()
                if stop_price != "-":
                    order_info["stopPrice"] = stop_price

                # Hesap verilerini al
                account_data = self.account_manager.get_account(account_name)

                selected_orders[order_id] = {
                    "order_info": order_info,
                    "account_data": account_data,
                    "account_name": account_name
                }

        return selected_orders

    def cancel_selected_orders(self):
        """Seçilen emirleri iptal et"""
        selected_orders = self.get_selected_orders()

        if not selected_orders:
            QMessageBox.warning(self, "Warning", "Please select at least one order!")
            return

        # Onay dialog'u
        reply = QMessageBox.question(
            self,
            "Confirm Cancel Orders",
            f"Are you sure you want to cancel {len(selected_orders)} selected order(s)?\n\n"
            "This action cannot be undone!",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # UI'yi güncelle
        self.cancel_selected_btn.setEnabled(False)
        self.modify_selected_btn.setEnabled(False)
        self.orders_progress_bar.setVisible(True)
        self.orders_progress_text.setVisible(True)
        self.orders_progress_bar.setMaximum(len(selected_orders))
        self.orders_progress_bar.setValue(0)
        self.orders_progress_text.clear()

        # Thread'i başlat
        self.current_thread = OrderActionThread(selected_orders, "cancel")
        self.current_thread.progress_update.connect(self.on_order_progress_update)
        self.current_thread.finished.connect(self.on_order_action_finished)
        self.current_thread.start()

    def modify_selected_orders(self):
        """Seçilen emirleri değiştir"""
        selected_orders = self.get_selected_orders()

        if not selected_orders:
            QMessageBox.warning(self, "Warning", "Please select at least one order!")
            return

        # Değiştirme parametreleri dialog'u
        dialog = ModifyOrderDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            modify_params = dialog.get_parameters()

            if not modify_params:
                QMessageBox.warning(self, "Warning", "No modification parameters provided!")
                return

            # Onay dialog'u
            param_text = ", ".join([f"{k}: {v}" for k, v in modify_params.items()])
            reply = QMessageBox.question(
                self,
                "Confirm Modify Orders",
                f"Are you sure you want to modify {len(selected_orders)} selected order(s) with these parameters?\n\n"
                f"Changes: {param_text}\n\n"
                "This will cancel existing orders and create new ones!",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply != QMessageBox.Yes:
                return

            # UI'yi güncelle
            self.cancel_selected_btn.setEnabled(False)
            self.modify_selected_btn.setEnabled(False)
            self.orders_progress_bar.setVisible(True)
            self.orders_progress_text.setVisible(True)
            self.orders_progress_bar.setMaximum(len(selected_orders))
            self.orders_progress_bar.setValue(0)
            self.orders_progress_text.clear()

            # Thread'i başlat
            self.current_thread = OrderActionThread(selected_orders, "modify", modify_params)
            self.current_thread.progress_update.connect(self.on_order_progress_update)
            self.current_thread.finished.connect(self.on_order_action_finished)
            self.current_thread.start()

    @pyqtSlot(str, str)
    def on_order_progress_update(self, order_id, message):
        """Emir işlemi ilerleme güncellemesi"""
        current_value = self.orders_progress_bar.value()
        self.orders_progress_bar.setValue(current_value + 1)
        self.orders_progress_text.append(f"Order {order_id}: {message}")
        QApplication.processEvents()

    @pyqtSlot(dict)
    def on_order_action_finished(self, results):
        """Emir işlemi tamamlandığında"""
        self.cancel_selected_btn.setEnabled(True)
        self.modify_selected_btn.setEnabled(True)
        self.orders_progress_bar.setVisible(False)

        # Sonuçları göster
        success_count = results["success"]
        error_count = results["error"]
        total = results["total"]

        result_text = f"Order Action Completed!\n\n"
        result_text += f"Total Orders: {total}\n"
        result_text += f"Successful Actions: {success_count}\n"
        result_text += f"Failed Actions: {error_count}\n\n"

        result_text += "Details:\n"
        for order_id, result in results["results"].items():
            result_text += f"Order {order_id} ({result['account']}): {result['status']} - {result['message']}\n"

        # Sonuç dialog'u
        dialog = QDialog(self)
        dialog.setWindowTitle("Order Action Results")
        dialog.setMinimumSize(600, 450)

        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setPlainText(result_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec_()

        # Tabloları yenile
        self.load_open_orders()
        self.refresh_accounts_signal.emit()

        # Thread'i temizle
        self.current_thread = None

    def on_order_type_changed(self, order_type):
        """Emir tipi değiştiğinde UI'yi güncelle"""
        self.price_label.setVisible(order_type != "MARKET")
        self.price_input.setVisible(order_type != "MARKET")

        stop_visible = "STOP_LOSS" in order_type
        self.stop_price_label.setVisible(stop_visible)
        self.stop_price_input.setVisible(stop_visible)

    def on_quantity_type_changed(self, button):
        """Miktar tipi değiştiğinde UI'yi güncelle"""
        if button == self.fixed_radio:
            self.quantity_input.setVisible(True)
            self.percentage_input.setVisible(False)
        else:
            self.quantity_input.setVisible(False)
            self.percentage_input.setVisible(True)

    def get_selected_accounts(self):
        """Seçilen hesapları döndür"""
        selected = {}
        for i in range(self.accounts_table.rowCount()):
            if self.accounts_table.item(i, 0).checkState() == Qt.Checked:
                account_name = self.accounts_table.item(i, 1).text()
                if account_name in self.accounts_data:
                    selected[account_name] = self.accounts_data[account_name]["data"]
        return selected

    def execute_bulk_order(self):
        """Toplu emri çalıştır"""
        # Seçilen hesapları al
        selected_accounts = self.get_selected_accounts()
        if not selected_accounts:
            QMessageBox.warning(self, "Warning", "Please select at least one account!")
            return

        # Parametreleri kontrol et
        symbol = self.symbol_combo.currentText().strip()
        if not symbol:
            QMessageBox.warning(self, "Warning", "Please enter a symbol!")
            return

        # Miktar kontrolü
        quantity_type = "fixed" if self.fixed_radio.isChecked() else "percentage"

        if quantity_type == "fixed":
            try:
                quantity = float(self.quantity_input.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid quantity!")
                return
        else:
            quantity = self.percentage_input.value()

        # Emir parametrelerini hazırla
        order_params = {
            "symbol": symbol,
            "side": self.side_combo.currentText(),
            "type": self.order_type_combo.currentText(),
            "quantity": quantity,
            "quantity_type": quantity_type
        }

        # Fiyat parametreleri
        if self.order_type_combo.currentText() in ["LIMIT", "STOP_LOSS_LIMIT"]:
            try:
                order_params["price"] = float(self.price_input.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid price!")
                return

        if "STOP_LOSS" in self.order_type_combo.currentText():
            try:
                order_params["stop_price"] = float(self.stop_price_input.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid stop price!")
                return

        # Take Profit parametreleri
        if self.take_profit_checkbox.isChecked():
            try:
                order_params["enable_take_profit"] = True
                order_params["take_profit_price"] = float(self.take_profit_input.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid take profit price!")
                return

        # Stop Loss parametreleri
        if self.stop_loss_checkbox.isChecked():
            try:
                order_params["enable_stop_loss"] = True
                order_params["stop_loss_price"] = float(self.stop_loss_input.text())
            except ValueError:
                QMessageBox.warning(self, "Warning", "Please enter a valid stop loss price!")
                return

        # UI'yi güncelle
        self.execute_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_text.setVisible(True)
        self.progress_bar.setMaximum(len(selected_accounts))
        self.progress_bar.setValue(0)
        self.progress_text.clear()

        # Thread'i başlat
        self.current_thread = BulkOrderThread(selected_accounts, order_params)
        self.current_thread.progress_update.connect(self.on_progress_update)
        self.current_thread.finished.connect(self.on_bulk_order_finished)
        self.current_thread.start()

    @pyqtSlot(str, str)
    def on_progress_update(self, account_name, message):
        """İlerleme güncellemesi"""
        current_value = self.progress_bar.value()
        self.progress_bar.setValue(current_value + 1)
        self.progress_text.append(f"{account_name}: {message}")
        QApplication.processEvents()

    @pyqtSlot(dict)
    def on_bulk_order_finished(self, results):
        """Toplu emir tamamlandığında"""
        self.execute_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        # Sonuçları göster
        success_count = results["success"]
        error_count = results["error"]
        total = results["total"]

        result_text = f"Bulk Order Completed!\n\n"
        result_text += f"Total Accounts: {total}\n"
        result_text += f"Successful Orders: {success_count}\n"
        result_text += f"Failed Orders: {error_count}\n\n"

        result_text += "Details:\n"
        for account, result in results["results"].items():
            result_text += f"{account}: {result['status']} - {result['message']}\n"

        # Sonuç dialog'u
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Order Results")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout()
        text_edit = QTextEdit()
        text_edit.setPlainText(result_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec_()

        # Hesap widget'larını yenile
        self.refresh_accounts_signal.emit()

        # Thread'i temizle
        self.current_thread = None


class ModifyOrderDialog(QDialog):
    """Emir değiştirme dialog'u"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Modify Orders")
        self.setMinimumSize(400, 300)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Açıklama
        info_label = QLabel(
            "Enter new values for the parameters you want to change.\nLeave empty to keep current values.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Form
        form_layout = QFormLayout()

        # Yeni fiyat
        self.new_price_input = QLineEdit()
        self.new_price_input.setPlaceholderText("Leave empty to keep current price")
        form_layout.addRow("New Price:", self.new_price_input)

        # Yeni miktar
        self.new_quantity_input = QLineEdit()
        self.new_quantity_input.setPlaceholderText("Leave empty to keep current quantity")
        form_layout.addRow("New Quantity:", self.new_quantity_input)

        # Yeni stop fiyat
        self.new_stop_price_input = QLineEdit()
        self.new_stop_price_input.setPlaceholderText("Leave empty to keep current stop price")
        form_layout.addRow("New Stop Price:", self.new_stop_price_input)

        layout.addLayout(form_layout)

        # Butonlar
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_parameters(self):
        """Değiştirme parametrelerini döndür"""
        params = {}

        if self.new_price_input.text().strip():
            try:
                params["price"] = float(self.new_price_input.text())
            except ValueError:
                pass

        if self.new_quantity_input.text().strip():
            try:
                params["quantity"] = float(self.new_quantity_input.text())
            except ValueError:
                pass

        if self.new_stop_price_input.text().strip():
            try:
                params["stop_price"] = float(self.new_stop_price_input.text())
            except ValueError:
                pass

        return params