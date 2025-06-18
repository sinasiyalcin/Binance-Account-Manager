from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QMessageBox, QFrame,
                             QApplication, QProgressBar, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, QSize
from PyQt5.QtGui import QFont, QIcon, QPalette
import sys


class PasswordValidationThread(QThread):
    """Şifre doğrulaması yapan thread"""
    validation_complete = pyqtSignal(bool, str)  # başarı, hata_mesajı

    def __init__(self, account_manager, password, is_new_password=False, confirm_password=None):
        super().__init__()
        self.account_manager = account_manager
        self.password = password
        self.is_new_password = is_new_password
        self.confirm_password = confirm_password

    def run(self):
        try:
            if self.is_new_password:
                # Yeni şifre oluşturma için
                if self.password != self.confirm_password:
                    self.validation_complete.emit(False, "Passwords don't match")
                    return

                if len(self.password) < 6:
                    self.validation_complete.emit(False, "Password must be at least 6 characters long")
                    return

                # Bu şifre ile yeni anahtar oluşturmayı dene
                self.account_manager._load_or_create_key(self.password)
                self.validation_complete.emit(True, "")
            else:
                # Mevcut şifre doğrulaması için
                self.account_manager._load_or_create_key(self.password)
                self.validation_complete.emit(True, "")

        except Exception as e:
            if "Invalid password" in str(e) or "incorrect" in str(e).lower():
                self.validation_complete.emit(False, "Invalid password")
            else:
                self.validation_complete.emit(False, f"Error: {str(e)}")


class PasswordDialog(QDialog):
    """Modern şifre giriş diyaloğu"""

    def __init__(self, is_new_setup=False, parent=None):
        super().__init__(parent)
        self.is_new_setup = is_new_setup
        self.password = None
        self.validation_thread = None
        self.init_ui()

    def init_ui(self):
        """Kullanıcı arayüzünü başlat"""
        self.setWindowTitle("Account Security")
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint)

        # Minimum boyut ayarla ama gerektiğinde genişleyebilsin
        self.setMinimumSize(450, 350 if not self.is_new_setup else 450)
        self.resize(450, 350 if not self.is_new_setup else 450)

        # Koyu tema ve uygun boyutlandırma ayarları
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
                padding: 2px;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                height: 35px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: bold;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #555555;
                color: #999999;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 4px;
                background-color: #3c3c3c;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
        """)

        # Ana layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Başlık
        title = QLabel("🔒 Binance Account Security")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)
        layout.addWidget(title)

        # Açıklama
        if self.is_new_setup:
            desc_text = "Create a secure password to protect your Binance API credentials.\nThis password will be required each time you start the application."
        else:
            desc_text = "Enter your password to unlock your encrypted Binance accounts."

        description = QLabel(desc_text)
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)
        description.setStyleSheet("color: #cccccc; font-size: 12px; padding: 10px;")
        layout.addWidget(description)

        # Ayırıcı çizgi
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #555555;")
        separator.setMaximumHeight(2)
        layout.addWidget(separator)

        # Şifre bölümü
        password_container = QVBoxLayout()
        password_container.setSpacing(8)

        password_label = QLabel("Password:" if not self.is_new_setup else "Create Password:")
        password_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        password_container.addWidget(password_label)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Enter your password...")
        self.password_input.returnPressed.connect(self.handle_password_input)
        password_container.addWidget(self.password_input)

        layout.addLayout(password_container)

        # Şifre onaylama (sadece yeni kurulum için)
        if self.is_new_setup:
            confirm_container = QVBoxLayout()
            confirm_container.setSpacing(8)

            confirm_label = QLabel("Confirm Password:")
            confirm_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            confirm_container.addWidget(confirm_label)

            self.confirm_input = QLineEdit()
            self.confirm_input.setEchoMode(QLineEdit.Password)
            self.confirm_input.setPlaceholderText("Confirm your password...")
            self.confirm_input.returnPressed.connect(self.handle_password_input)
            confirm_container.addWidget(self.confirm_input)

            layout.addLayout(confirm_container)

        # İlerleme çubuğu (başlangıçta gizli)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Butonlar
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        if not self.is_new_setup:
            self.cancel_btn = QPushButton("Exit Application")
            self.cancel_btn.clicked.connect(self.reject_and_exit)
            self.cancel_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d13438;
                    height: 40px;
                    min-width: 120px;
                }
                QPushButton:hover {
                    background-color: #b52d32;
                }
            """)
            button_layout.addWidget(self.cancel_btn)

        self.ok_btn = QPushButton("Unlock Accounts" if not self.is_new_setup else "Create & Secure")
        self.ok_btn.clicked.connect(self.handle_password_input)
        self.ok_btn.setDefault(True)
        self.ok_btn.setStyleSheet("min-width: 140px; height: 40px;")
        button_layout.addWidget(self.ok_btn)

        layout.addLayout(button_layout)

        # Durum etiketi
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px; padding: 5px;")
        self.status_label.setMinimumHeight(30)
        layout.addWidget(self.status_label)

        # Şifre girişine odaklan
        self.password_input.setFocus()

        # Boyutu içeriğe göre ayarla
        self.adjustSize()

    def handle_password_input(self):
        """Şifre girişini doğrulama ile işle"""
        password = self.password_input.text().strip()

        if not password:
            self.show_error("Please enter a password")
            return

        if self.is_new_setup:
            confirm_password = self.confirm_input.text().strip()
            if not confirm_password:
                self.show_error("Please confirm your password")
                return
        else:
            confirm_password = None

        # Doğrulama sırasında UI'yı devre dışı bırak
        self.set_ui_enabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Belirsiz ilerleme
        self.status_label.setText("Validating password...")
        self.status_label.setStyleSheet("color: #ffaa00; font-size: 11px; padding: 5px;")

        # Doğrulamayı ayrı thread'de başlat
        from account_manager import AccountManager
        temp_manager = AccountManager.__new__(AccountManager)  # __init__ çağrılmadan oluştur
        temp_manager.config_file = "accounts.encrypted"
        temp_manager.key_file = ".encryption_key"
        temp_manager.salt_file = ".salt"

        self.validation_thread = PasswordValidationThread(
            temp_manager, password, self.is_new_setup, confirm_password
        )
        self.validation_thread.validation_complete.connect(self.on_validation_complete)
        self.validation_thread.start()

    def on_validation_complete(self, success, error_message):
        """Doğrulama tamamlanma işlemini gerçekleştir"""
        self.progress_bar.setVisible(False)
        self.set_ui_enabled(True)

        if success:
            self.password = self.password_input.text().strip()
            self.status_label.setText("✓ Password validated successfully!")
            self.status_label.setStyleSheet("color: #4ecdc4; font-size: 11px; padding: 5px;")

            # Kabul etmeden önce kısa bekleme
            QTimer.singleShot(500, self.accept)
        else:
            self.show_error(error_message)
            self.password_input.selectAll()
            self.password_input.setFocus()

        # Thread'i temizle
        self.validation_thread.deleteLater()
        self.validation_thread = None

    def show_error(self, message):
        """Hata mesajını göster"""
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px; padding: 5px;")

    def set_ui_enabled(self, enabled):
        """UI öğelerini etkinleştir/devre dışı bırak"""
        self.password_input.setEnabled(enabled)
        if hasattr(self, 'confirm_input'):
            self.confirm_input.setEnabled(enabled)
        self.ok_btn.setEnabled(enabled)
        if hasattr(self, 'cancel_btn'):
            self.cancel_btn.setEnabled(enabled)

    def reject_and_exit(self):
        """Tüm uygulamadan çık"""
        reply = QMessageBox.question(
            self,
            "Exit Application",
            "Are you sure you want to exit?\nThe application cannot run without password authentication.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            QApplication.quit()
            sys.exit(0)

    def get_password(self):
        """Doğrulanmış şifreyi al"""
        return self.password


class PasswordManager:
    """Şifre diyaloglarını ve doğrulama işlemlerini yönetir"""

    @staticmethod
    def get_password(is_new_setup=False, parent=None):
        """Şifre diyaloğunu göster ve doğrulanmış şifreyi döndür"""
        dialog = PasswordDialog(is_new_setup, parent)

        if dialog.exec_() == QDialog.Accepted:
            return dialog.get_password()
        else:
            if not is_new_setup:
                # Kullanıcı mevcut şifreyi iptal etti - uygulamadan çık
                QApplication.quit()
                sys.exit(0)
            return None

    @staticmethod
    def show_change_password_dialog(account_manager, parent=None):
        """Şifre değiştirme diyaloğunu göster"""
        dialog = ChangePasswordDialog(account_manager, parent)
        return dialog.exec_() == QDialog.Accepted


class ChangePasswordDialog(QDialog):
    """Mevcut şifreyi değiştirme diyaloğu"""

    def __init__(self, account_manager, parent=None):
        super().__init__(parent)
        self.account_manager = account_manager
        self.init_ui()

    def init_ui(self):
        """Kullanıcı arayüzünü başlat"""
        self.setWindowTitle("Change Password")
        self.setMinimumSize(400, 450)
        self.resize(400, 450)

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
                padding: 2px;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 2px solid #555555;
                border-radius: 8px;
                padding: 12px;
                font-size: 13px;
                height: 35px;
            }
            QLineEdit:focus {
                border-color: #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: bold;
                height: 40px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)

        # Ana layout
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Başlık
        title = QLabel("🔐 Change Password")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Mevcut şifre
        current_container = QVBoxLayout()
        current_container.setSpacing(8)

        current_label = QLabel("Current Password:")
        current_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        current_container.addWidget(current_label)

        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.Password)
        self.current_password.setPlaceholderText("Enter your current password...")
        current_container.addWidget(self.current_password)

        layout.addLayout(current_container)

        # Yeni şifre
        new_container = QVBoxLayout()
        new_container.setSpacing(8)

        new_label = QLabel("New Password:")
        new_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        new_container.addWidget(new_label)

        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.new_password.setPlaceholderText("Enter your new password...")
        new_container.addWidget(self.new_password)

        layout.addLayout(new_container)

        # Yeni şifreyi onayla
        confirm_container = QVBoxLayout()
        confirm_container.setSpacing(8)

        confirm_label = QLabel("Confirm New Password:")
        confirm_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        confirm_container.addWidget(confirm_label)

        self.confirm_password = QLineEdit()
        self.confirm_password.setEchoMode(QLineEdit.Password)
        self.confirm_password.setPlaceholderText("Confirm your new password...")
        confirm_container.addWidget(self.confirm_password)

        layout.addLayout(confirm_container)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                height: 40px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(cancel_btn)

        change_btn = QPushButton("Change Password")
        change_btn.clicked.connect(self.change_password)
        change_btn.setDefault(True)
        change_btn.setStyleSheet("min-width: 140px; height: 40px;")
        button_layout.addWidget(change_btn)

        layout.addLayout(button_layout)

        # Durum etiketi
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px; padding: 5px;")
        self.status_label.setMinimumHeight(30)
        layout.addWidget(self.status_label)

        # Mevcut şifre girişine odaklan
        self.current_password.setFocus()

        # Boyutu içeriğe göre ayarla
        self.adjustSize()

    def change_password(self):
        """Şifre değiştirme işlemini gerçekleştir"""
        current = self.current_password.text().strip()
        new = self.new_password.text().strip()
        confirm = self.confirm_password.text().strip()

        if not current:
            self.show_error("Please enter your current password")
            return

        if not new:
            self.show_error("Please enter a new password")
            return

        if len(new) < 6:
            self.show_error("New password must be at least 6 characters long")
            return

        if new != confirm:
            self.show_error("New passwords don't match")
            return

        try:
            self.account_manager.change_password(current, new)
            self.show_success("Password changed successfully!")
            QTimer.singleShot(1000, self.accept)
        except Exception as e:
            if "Invalid password" in str(e):
                self.show_error("Current password is incorrect")
            else:
                self.show_error(f"Error: {str(e)}")

    def show_error(self, message):
        """Hata mesajını göster"""
        self.status_label.setText(f"❌ {message}")
        self.status_label.setStyleSheet("color: #ff6b6b; font-size: 11px; padding: 5px;")

    def show_success(self, message):
        """Başarı mesajını göster"""
        self.status_label.setText(f"✓ {message}")
        self.status_label.setStyleSheet("color: #4ecdc4; font-size: 11px; padding: 5px;")