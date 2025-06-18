import sys
import json
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                            QHBoxLayout, QPushButton, QLabel, QLineEdit,
                            QTableWidget, QTableWidgetItem, QTabWidget,
                            QFormLayout, QMessageBox, QGroupBox, QSplitter,
                            QComboBox, QGridLayout, QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
from binance.client import Client
from binance.exceptions import BinanceAPIException

from account_manager import AccountManager
from binance_api import BinanceConnector
from transaction import AccountWidget
from left_menu import SideMenuWidget
from main_screen import MainWindow

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()