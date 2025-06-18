import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class AccountManager:
    def __init__(self, password=None):
        self.accounts = {}
        self.config_file = "accounts.encrypted"
        self.key_file = ".encryption_key"
        self.salt_file = ".salt"
        self._load_or_create_key(password)
        self.load_accounts()

    def _load_or_create_key(self, password=None):
        """Şifrelemene Anahtarı kontrolü ve oluşturulması"""
        # Salt yaratılması veya yüklenmesi
        if os.path.exists(self.salt_file):
            with open(self.salt_file, 'rb') as f:
                salt = f.read()
        else:
            # Rasgele salt oluşturulur
            import os as opsys
            salt = opsys.urandom(16)
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            os.chmod(self.salt_file, 0o600)

        if os.path.exists(self.key_file):
            # Eğer şifre yoksa GUI'den şifre al
            if password is None:
                # Import here to avoid circular import
                from password_dialog import PasswordManager
                password = PasswordManager.get_password(is_new_setup=False)
                if password is None:
                    raise ValueError("Password is required to unlock accounts")

            # Şifre üzerinden anahtar yaratılır
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key_encryption_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

            # Şifreleme anahtarı okunur
            with open(self.key_file, 'rb') as f:
                encrypted_key = f.read()

            try:
                # Anahtar şifresi çözülür
                fernet = Fernet(key_encryption_key)
                self.key = fernet.decrypt(encrypted_key)
            except Exception as e:
                raise ValueError("Invalid password or corrupted key file")
        else:
            # Yeni anahtar yaratılır
            self.key = Fernet.generate_key()

            # Anahtarın korunması için şifre oluşturulur
            if password is None:
                # Import here to avoid circular import
                from password_dialog import PasswordManager
                password = PasswordManager.get_password(is_new_setup=True)
                if password is None:
                    raise ValueError("Password is required to secure accounts")

            # Şifre üzerinden anahtar şifrelemesi yapılır
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key_encryption_key = base64.urlsafe_b64encode(kdf.derive(password.encode()))

            # Anahtarı Şifreler
            fernet = Fernet(key_encryption_key)
            encrypted_key = fernet.encrypt(self.key)

            # Şifrelenmiş Anahtarın saklanması
            with open(self.key_file, 'wb') as f:
                f.write(encrypted_key)
            os.chmod(self.key_file, 0o600)

    def load_accounts(self):
        """Şifrelenmiş hesap bilgilerini okur ve saklar."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'rb') as f:
                    encrypted_data = f.read()

                if encrypted_data:
                    fernet = Fernet(self.key)
                    decrypted_data = fernet.decrypt(encrypted_data)
                    self.accounts = json.loads(decrypted_data.decode())
            except Exception as e:
                print(f"Error while reading account info: {e}")
                self.accounts = {}
        else:
            self.accounts = {}

    def save_accounts(self):
        """Şifrelenmiş dosyaya hesap bilgilerini kaydeder"""
        try:
            fernet = Fernet(self.key)
            encrypted_data = fernet.encrypt(json.dumps(self.accounts).encode())

            with open(self.config_file, 'wb') as f:
                f.write(encrypted_data)

            # Şifrelenmiş dosyaya erişim yetkileri atanır
            os.chmod(self.config_file, 0o600)
        except Exception as e:
            print(f"Hesaplar kaydedilirken hata: {e}")

    def add_account(self, name, api_key, api_secret, testnet=True):
        """Yeni hesap ekler"""
        self.accounts[name] = {
            "api_key": api_key,
            "api_secret": api_secret,
            "testnet": testnet
        }
        self.save_accounts()

    def remove_account(self, name):
        """Hesap siler"""
        if name in self.accounts:
            del self.accounts[name]
            self.save_accounts()
            return True
        return False

    def get_account(self, name):
        """İsme göre hesap bilgilerini getirir"""
        return self.accounts.get(name)

    def get_all_accounts(self):
        """Tüm hesapları döndürür"""
        return self.accounts

    def change_password(self, old_password, new_password):
        """Şifre değiştirilmesi"""
        # Eski şifrenin kontrolü
        self._load_or_create_key(old_password)

        # Salt okunur
        with open(self.salt_file, 'rb') as f:
            salt = f.read()

        # Yeni şifreyle şifrelenecek bir anahtar oluşturulur
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key_encryption_key = base64.urlsafe_b64encode(kdf.derive(new_password.encode()))

        # Yeni şifreyle anahtar şifrelenir
        fernet = Fernet(key_encryption_key)
        encrypted_key = fernet.encrypt(self.key)

        # Şifreli anahtar kaydedilir
        with open(self.key_file, 'wb') as f:
            f.write(encrypted_key)

        return True