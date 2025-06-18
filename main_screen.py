from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QSplitter,
                             QMessageBox, QGridLayout, QPushButton,
                             QStackedWidget, QToolBar, QAction, QMenuBar, QMenu)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from account_manager import AccountManager
from transaction import AccountWidget
from admin_panel import AdminPanel


class MainWindow(QMainWindow):
    """Binance çoklu hesap yönetimi ana penceresi"""
    def __init__(self):
        super().__init__()
        self.account_manager = AccountManager()
        self.account_widgets = {}  # Açık hesap widget'ları
        self.current_view = "accounts"  # Başlangıç görünümü: "accounts" veya "admin"
        self.init_ui()

    def init_ui(self):
        """Kullanıcı arayüzünü başlat"""
        self.setWindowTitle("Binance Multi-Account Management")
        self.setGeometry(100, 100, 1200, 800)

        # Menü çubuğu
        self.create_menu_bar()

        # Araç çubuğu oluşturma
        self.create_toolbar()

        # Ana widget
        central_widget = QWidget()
        main_layout = QHBoxLayout()

        # Sol menü
        from left_menu import SideMenuWidget
        self.side_menu = SideMenuWidget(self.account_manager, self)
        main_layout.addWidget(self.side_menu)

        # Ana içerik alanı
        self.stacked_widget = QStackedWidget()

        # 1. Hesaplar Görünümü
        self.accounts_view = QWidget()
        accounts_layout = QVBoxLayout()

        # Boş ekran mesajı
        self.empty_label = QLabel("No accounts to display. Add accounts from the side menu.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("font-size: 16px; color: gray;")

        # Hesapların gösterileceği grid widget
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_widget.setLayout(self.grid_layout)

        # Başlangıçta boş ekran mesajı
        accounts_layout.addWidget(self.empty_label)
        self.accounts_view.setLayout(accounts_layout)

        # 2. Admin Paneli Görünümü (başlatma lazy loading ile yapılacak)
        self.admin_panel = None

        # Görünümleri StackedWidget'a ekle
        self.stacked_widget.addWidget(self.accounts_view)

        # Başlangıçta hesaplar görünümünü göster
        self.stacked_widget.setCurrentIndex(0)

        main_layout.addWidget(self.stacked_widget)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def create_menu_bar(self):
        """Güvenlik menüsünü oluştur"""
        menubar = self.menuBar()

        security_menu = menubar.addMenu('Security')

        # Şifre değiştirme menüsü
        change_password_action = QAction('Change Password', self)
        change_password_action.setStatusTip('Change your master password')
        change_password_action.triggered.connect(self.show_change_password_dialog)
        security_menu.addAction(change_password_action)

        # Uygulama kitleme butonu
        lock_action = QAction('Lock Application', self)
        lock_action.setStatusTip('Lock the application and require password')
        lock_action.triggered.connect(self.lock_application)
        security_menu.addAction(lock_action)

    def create_toolbar(self):
        """Araç çubuğunu oluştur"""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Hesaplar görünümü butonu
        self.accounts_action = QAction("Accounts View", self)
        self.accounts_action.setCheckable(True)
        self.accounts_action.setChecked(True)  # Başlangıçta seçili
        self.accounts_action.triggered.connect(lambda: self.switch_view("accounts"))
        self.toolbar.addAction(self.accounts_action)

        # Admin Paneli butonu
        self.admin_action = QAction("Admin Panel", self)
        self.admin_action.setCheckable(True)
        self.admin_action.triggered.connect(lambda: self.switch_view("admin"))
        self.toolbar.addAction(self.admin_action)

        # Araç çubuğuna stil ekle
        self.toolbar.setStyleSheet("""
            QToolBar {
                spacing: 10px;
                padding: 5px;
                background-color: #f0f0f0;
            }
            QToolButton {
                padding: 5px 10px;
                border-radius: 3px;
            }
            QToolButton:checked {
                background-color: #c0d6e4;
                font-weight: bold;
            }
        """)

    def show_change_password_dialog(self):
        """Şifre değiştirme diyaloğunu göster"""
        from password_dialog import PasswordManager
        success = PasswordManager.show_change_password_dialog(self.account_manager, self)

        if success:
            QMessageBox.information(
                self,
                "Password Changed",
                "Your password has been changed successfully!\n\n"
                "Please remember your new password as it will be required\n"
                "the next time you start the application."
            )

    def lock_application(self):
        """Uygulamayı kilitle ve şifre iste"""
        reply = QMessageBox.question(
            self,
            "Lock Application",
            "Are you sure you want to lock the application?\n\n"
            "You will need to enter your password to unlock it.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.hide()  # Ana pencereyi gizle

            # Şifre diyaloğunu göster
            from password_dialog import PasswordManager
            password = PasswordManager.get_password(is_new_setup=False, parent=None)

            if password:
                # Şifreyi şifre çözme deneyerek doğrula
                try:
                    temp_manager = AccountManager(password)
                    self.show()  # Ana pencereyi tekrar göster
                    QMessageBox.information(self, "Unlocked", "Application unlocked successfully!")
                except:
                    QMessageBox.critical(self, "Invalid Password", "Invalid password. Application will exit.")
                    self.close()
            else:
                # Kullanıcı şifre diyaloğunu iptal etti
                self.close()

    def create_admin_panel(self):
        """Admin panelini lazy loading ile oluştur"""
        if self.admin_panel is None:
            self.admin_panel = AdminPanel(self.account_manager)
            self.admin_panel.refresh_accounts_signal.connect(self.load_account_widgets)
            self.stacked_widget.addWidget(self.admin_panel)

    def switch_view(self, view_name):
        """Görünümler arasında geçiş yap"""
        if view_name == "accounts":
            self.stacked_widget.setCurrentIndex(0)
            self.current_view = "accounts"

            # Butonları güncelle
            self.accounts_action.setChecked(True)
            self.admin_action.setChecked(False)

            # Hesap görünümünde grid'i yeniden düzenle
            if len(self.account_widgets) > 0:
                # Hesaplar görünümünün layout'undan boş etiketi kaldır
                layout = self.accounts_view.layout()
                if layout.itemAt(0).widget() == self.empty_label:
                    layout.takeAt(0)
                    self.empty_label.setParent(None)

                # Grid widget'ı ekle
                if not layout.count():
                    layout.addWidget(self.grid_widget)

                self.update_grid_layout()
            else:
                # Hesap yok, boş ekranı göster
                layout = self.accounts_view.layout()
                if layout.count() == 0 or layout.itemAt(0).widget() != self.empty_label:
                    # Önceki widget'ı kaldır (eğer varsa)
                    while layout.count():
                        item = layout.takeAt(0)
                        if item.widget():
                            item.widget().setParent(None)

                    # Boş ekran mesajını ekle
                    layout.addWidget(self.empty_label)

        elif view_name == "admin":
            # Admin panelini lazy loading ile oluştur
            self.create_admin_panel()

            # Admin panel index'ini al (dinamik olarak eklendi)
            admin_index = self.stacked_widget.indexOf(self.admin_panel)
            self.stacked_widget.setCurrentIndex(admin_index)
            self.current_view = "admin"

            # Butonları güncelle
            self.accounts_action.setChecked(False)
            self.admin_action.setChecked(True)

            # Admin paneli başlatması otomatik olarak başlayacak
            # Eğer daha önceden yüklenmişse ve kullanıcı tekrar geçiş yapıyorsa,
            # veri tazeleme isteğe bağlı yapılabilir
            self.refresh_admin_panel_if_needed()

    def refresh_admin_panel_if_needed(self):
        """Admin panelinin verilerini gerekirse tazele"""
        if self.admin_panel is not None:
            # Eğer admin panel zaten yüklü ve kullanıcı tekrar geçiş yapıyorsa
            # sadece mevcut sekmede verileri tazele
            current_tab = self.admin_panel.tabs.currentIndex()

            if current_tab == 0:  # Toplu Emir sekmesi
                # Hesaplar tablosunu güncelle
                if hasattr(self.admin_panel, 'accounts_data') and self.admin_panel.accounts_data:
                    self.admin_panel.populate_accounts_table()
            elif current_tab == 1:  # Özet sekmesi
                # Özet verilerini yenile
                self.admin_panel.refresh_summary_data()
            elif current_tab == 2:  # Açık Emirler sekmesi
                # Açık emirleri yenile
                self.admin_panel.load_open_orders()

    def add_account_to_view(self, account_name):
        """Seçili hesabı görüntüleme ekranına ekle"""
        # Maksimum 4 hesap kontrolü
        if len(self.account_widgets) >= 4:
            QMessageBox.warning(self, "Warning", "Maximum of 4 accounts can be displayed at once. "
                                                 "Remove an account before adding a new one.")
            return

        # Hesap zaten ekranda mı?
        if account_name in self.account_widgets:
            QMessageBox.information(self, "Info", f"Account '{account_name}' is already displayed.")
            return

        # Hesap bilgilerini al
        account_data = self.account_manager.get_account(account_name)
        if not account_data:
            QMessageBox.warning(self, "Error", f"Account '{account_name}' not found.")
            return

        # Yeni hesap widget'ı oluştur
        account_widget = AccountWidget(account_name, account_data)

        # Widget'ı kaydet
        self.account_widgets[account_name] = account_widget

        # Eğer hesaplar görünümündeysek, görünümü güncelle
        if self.current_view == "accounts":
            # Boş ekran mesajını kaldır
            if len(self.account_widgets) == 1:
                layout = self.accounts_view.layout()
                if layout.itemAt(0).widget() == self.empty_label:
                    layout.takeAt(0)
                    self.empty_label.setParent(None)

                # Grid widget'ı ekle
                layout.addWidget(self.grid_widget)

            # Grid'e ekle
            count = len(self.account_widgets)
            row, col = divmod(count - 1, 2)  # 2x2 grid için satır ve sütun hesaplama
            self.grid_layout.addWidget(account_widget, row, col)

            # Grid düzenini güncelle
            self.update_grid_layout()

        # Otomatik olarak hesaplar görünümüne geç
        self.switch_view("accounts")

    def remove_account_from_view(self, account_name):
        """Hesabı görüntüleme ekranından kaldır"""
        if account_name not in self.account_widgets:
            return

        # Widget'ı grid'den kaldır (eğer şu an gösteriliyorsa)
        if self.current_view == "accounts":
            widget = self.account_widgets[account_name]
            self.grid_layout.removeWidget(widget)
            widget.setParent(None)

        # Widget'ı listeden çıkar ve belleği temizle
        self.account_widgets[account_name].deleteLater()
        del self.account_widgets[account_name]

        # Eğer tüm hesaplar kaldırıldıysa, boş ekran mesajını göster
        if len(self.account_widgets) == 0:
            if self.current_view == "accounts":
                layout = self.accounts_view.layout()
                # Grid widget'ı kaldır
                if layout.count() > 0 and layout.itemAt(0).widget() == self.grid_widget:
                    layout.takeAt(0)
                    self.grid_widget.setParent(None)

                # Boş ekran mesajını ekle
                layout.addWidget(self.empty_label)
        else:
            # Mevcut hesaplar varsa grid düzenini güncelle
            if self.current_view == "accounts":
                self.update_grid_layout()

    def update_grid_layout(self):
        """Grid layout'u yeniden düzenle"""
        # Önce tüm widget'ları grid'den kaldır
        for i in reversed(range(self.grid_layout.count())):
            item = self.grid_layout.itemAt(i)
            if item.widget():
                self.grid_layout.removeItem(item)
                item.widget().setParent(None)

        # Şimdi yeniden düzenle
        accounts = list(self.account_widgets.items())

        if len(accounts) == 1:
            # Tek hesap varsa, tam ekran göster
            self.grid_layout.addWidget(accounts[0][1], 0, 0)
        elif len(accounts) == 2:
            # İki hesap varsa, yan yana göster
            self.grid_layout.addWidget(accounts[0][1], 0, 0)
            self.grid_layout.addWidget(accounts[1][1], 0, 1)
        elif len(accounts) == 3:
            # Üç hesap varsa, üstte 2, altta 1 şeklinde göster
            self.grid_layout.addWidget(accounts[0][1], 0, 0)
            self.grid_layout.addWidget(accounts[1][1], 0, 1)
            self.grid_layout.addWidget(accounts[2][1], 1, 0, 1, 2)  # Son widget iki sütunu da kaplasın
        elif len(accounts) == 4:
            # Dört hesap varsa, 2x2 grid şeklinde göster
            self.grid_layout.addWidget(accounts[0][1], 0, 0)
            self.grid_layout.addWidget(accounts[1][1], 0, 1)
            self.grid_layout.addWidget(accounts[2][1], 1, 0)
            self.grid_layout.addWidget(accounts[3][1], 1, 1)

    def load_account_widgets(self):
        """Hesap widget'larını yenile"""
        # Mevcut hesap widget'larını güncelle
        for account_name, widget in self.account_widgets.items():
            # Hesabın bağlantısını ve verilerini yenile
            widget.refresh_data()