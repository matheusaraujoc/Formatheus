import sys
import os
import json 

# --- Importações Corretas da PySide6 ---
from PySide6.QtWidgets import (QApplication, QDialog, QWidget, QVBoxLayout, 
                               QLineEdit, QPushButton, QLabel, QMessageBox,
                               QCheckBox) 
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt, QSize 
# ------------------------------------

# Tenta importar o tema
try:
    import qdarktheme
    HAS_THEME_LIB = True
except ImportError:
    HAS_THEME_LIB = False

# --- INÍCIO DA CORREÇÃO ---
# Importa os módulos do app admin
from firebase_admin_manager import FirebaseManager
from admin_dashboard import AdminDashboardWindow # Importa o dashboard principal

# Importa as funções do novo arquivo de utils
from admin_utils import resource_path, load_admin_config, save_admin_config
# --- FIM DA CORREÇÃO ---


class AdminLoginWindow(QDialog):
    
    def __init__(self, firebase_manager=None):
        super().__init__()
        self.setWindowTitle("Formatheus - Login Admin")
        
        try:
            icon_path = resource_path(os.path.join("admin_assets", "icons", "formatheus_admin.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Aviso: Ícone de admin não encontrado: {e}")

        self.setMinimumWidth(350)
        self.setModal(True) 

        if firebase_manager:
            self.firebase_manager = firebase_manager
        else:
            self.firebase_manager = FirebaseManager()

        # --- UI ---
        layout = QVBoxLayout(self)
        
        title = QLabel("Login do Administrador")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("E-mail do admin")
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Senha")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.remember_me_check = QCheckBox("Lembrar e-mail")
        
        self.login_button = QPushButton("Entrar")
        self.login_button.setProperty("cssClass", "primary")
        self.login_button.setMinimumHeight(40)
        
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #d13438;")
        
        layout.addWidget(title)
        layout.addSpacing(20)
        layout.addWidget(QLabel("E-mail:"))
        layout.addWidget(self.email_input)
        layout.addWidget(QLabel("Senha:"))
        layout.addWidget(self.password_input)
        layout.addSpacing(10)
        layout.addWidget(self.remember_me_check) 
        layout.addSpacing(10)
        layout.addWidget(self.login_button)
        layout.addWidget(self.status_label)

        # --- Sinais ---
        self.login_button.clicked.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)

        self.load_saved_email()

    def load_saved_email(self):
        email, remember = load_admin_config()
        self.email_input.setText(email)
        self.remember_me_check.setChecked(remember)

    def handle_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or not password:
            self.status_label.setText("Preencha todos os campos.")
            return

        self.login_button.setEnabled(False)
        self.status_label.setText("Autenticando...")
        
        success, message = self.firebase_manager.admin_login(email, password)
        
        if success:
            save_admin_config(email, self.remember_me_check.isChecked())
            self.status_label.setText(message)
            self.accept()
        else:
            self.status_label.setText(message)
            self.login_button.setEnabled(True)

# --- Ponto de Entrada Principal ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    if HAS_THEME_LIB:
        app.setStyleSheet(qdarktheme.load_stylesheet('dark'))
    
    firebase_manager_instance = FirebaseManager()
    
    while True:
        login_dialog = AdminLoginWindow(firebase_manager_instance)
        
        if login_dialog.exec():
            print("Login OK! Abrindo o Dashboard...")
            main_dashboard = AdminDashboardWindow(login_dialog.firebase_manager)
            main_dashboard.show()
            
            exit_code = app.exec() 
            
            if exit_code == 99: 
                print("Fazendo logout, voltando para a tela de login...")
                continue 
            else:
                print("Dashboard fechado, encerrando.")
                break 
        else:
            print("Login cancelado.")
            break

    sys.exit(0)