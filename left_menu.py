from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QLineEdit,
                             QFormLayout, QMessageBox, QGroupBox, QComboBox,
                             QCheckBox)
from PyQt5.QtCore import Qt
from binance_api import BinanceConnector


class SideMenuWidget(QWidget):
    def __init__(self, account_manager, main_window):
        super().__init__()
        self.account_manager = account_manager
        self.main_window = main_window
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Başlık
        title = QLabel("Account Management")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Hesap ekleme formu
        add_group = QGroupBox("Add Account")
        form_layout = QFormLayout()

        self.name_input = QLineEdit()
        self.api_key_input = QLineEdit()
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setEchoMode(QLineEdit.Password)

        self.testnet_checkbox = QCheckBox("Test Account")
        self.testnet_checkbox.setChecked(True)  # Varsayılan olarak seçili

        form_layout.addRow("Account Name:", self.name_input)
        form_layout.addRow("API Key:", self.api_key_input)
        form_layout.addRow("API Secret:", self.api_secret_input)
        form_layout.addRow("", self.testnet_checkbox)

        add_button = QPushButton("Add Account")
        add_button.clicked.connect(self.add_account)
        form_layout.addRow(add_button)

        add_group.setLayout(form_layout)
        layout.addWidget(add_group)

        # Hesap listesi
        list_group = QGroupBox("Account List")
        list_layout = QVBoxLayout()

        self.accounts_combo = QComboBox()
        self.update_accounts_list()
        list_layout.addWidget(self.accounts_combo)

        # Hesap silme butonu
        remove_button = QPushButton("Delete Account")
        remove_button.clicked.connect(self.remove_account)
        list_layout.addWidget(remove_button)

        # Görünüme ekleme butonu
        add_to_view_button = QPushButton("Add to View")
        add_to_view_button.clicked.connect(self.add_account_to_view)
        list_layout.addWidget(add_to_view_button)

        list_group.setLayout(list_layout)
        layout.addWidget(list_group)

        # Görünümden kaldırma butonu
        remove_from_view_button = QPushButton("Remove from View")
        remove_from_view_button.clicked.connect(self.remove_account_from_view)
        list_layout.addWidget(remove_from_view_button)

        # Altta esnek boşluk
        layout.addStretch(1)

        self.setLayout(layout)
        self.setFixedWidth(250)  # Yan menü genişliği

    def update_accounts_list(self):
        """Hesap listesini güncelle"""
        self.accounts_combo.clear()
        accounts = self.account_manager.get_all_accounts()
        for name in accounts.keys():
            self.accounts_combo.addItem(name)

    def add_account(self):
        """Yeni hesap ekle"""
        name = self.name_input.text().strip()
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        testnet = self.testnet_checkbox.isChecked()

        if not name or not api_key or not api_secret:
            QMessageBox.warning(self, "Warning", "Please fill in all fields!")
            return

        if name in self.account_manager.get_all_accounts():
            QMessageBox.warning(self, "Warning", f"Account '{name}' already exists!")
            return

        # API bağlantısını test et
        connector = BinanceConnector(api_key, api_secret, testnet=testnet)
        if not connector.connect():
            QMessageBox.critical(self, "Error", "Could not connect to Binance API. Please check your credentials.")
            return

        # Hesap ekle
        self.account_manager.add_account(name, api_key, api_secret, testnet=testnet)
        self.update_accounts_list()

        # Formu temizle
        self.name_input.clear()
        self.api_key_input.clear()
        self.api_secret_input.clear()

        QMessageBox.information(self, "Success", f"Account '{name}' added successfully.")

    def remove_account(self):
        """Seçilen hesabı sil"""
        current_account = self.accounts_combo.currentText()
        if not current_account:
            return

        reply = QMessageBox.question(self, "Remove Account",
                                     f"Are you sure you want to remove account '{current_account}'?",
                                     QMessageBox.Yes | QMessageBox.No)

        if reply == QMessageBox.Yes:
            # Görünümden hesabı kaldır
            self.main_window.remove_account_from_view(current_account)

            # Hesabı sil
            if self.account_manager.remove_account(current_account):
                self.update_accounts_list()
                QMessageBox.information(self, "Success", f"Account '{current_account}' removed.")

    def add_account_to_view(self):
        """Seçilen hesabı ana görünüme ekle"""
        current_account = self.accounts_combo.currentText()
        if not current_account:
            return

        # Ana görünüme ekle
        self.main_window.add_account_to_view(current_account)

    def remove_account_from_view(self):
        """Seçilen hesabı ana görünümden kaldır"""
        current_account = self.accounts_combo.currentText()
        if not current_account:
            return

        # Ana görünümden kaldır
        self.main_window.remove_account_from_view(current_account)
