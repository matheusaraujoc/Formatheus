# dialog_nova_licenca.py

import sys
import os

# --- Importações Corretas ---
from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QComboBox, QDialogButtonBox, QMessageBox, QLabel)
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import Qt
# --------------------------

# (Presume que você tem o firebase_admin_manager.py na mesma pasta)
# from firebase_admin_manager import FirebaseManager 
# (Não precisamos importar o manager aqui, ele é passado no __init__)

def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando em dev e no PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

class DialogoNovaLicenca(QDialog):
    
    def __init__(self, firebase_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar Nova Licença")
        self.setMinimumWidth(400)
        
        # Armazena a instância do gerenciador para usar suas funções
        self.firebase_manager = firebase_manager
        
        # Define o ícone
        try:
            # (Presume uma pasta 'admin_assets/icons' para os ícones do admin)
            icon_path = resource_path(os.path.join("admin_assets", "icons", "formatheus_admin.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Aviso: Ícone de admin não encontrado: {e}")

        # --- UI ---
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("email@cliente.com")
        
        self.plan_combo = QComboBox()
        
        form_layout.addRow(QLabel("Email do Cliente:"), self.email_input)
        form_layout.addRow(QLabel("Plano:"), self.plan_combo)
        
        # Botões OK e Cancelar
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)

        # Adiciona classes de estilo (se estiver usando qdarktheme)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setProperty("cssClass", "primary")
        
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)
        
        # Carrega os planos do Firestore
        self.carregar_planos()

    def carregar_planos(self):
        """Busca os planos do Firestore e popula o ComboBox."""
        try:
            self.plan_combo.setEnabled(False)
            self.plan_combo.addItem("A carregar planos...")
            
            # Chama a função do nosso gerenciador
            planos = self.firebase_manager.get_all_plans()
            
            self.plan_combo.clear()
            if not planos:
                self.plan_combo.addItem("Erro: Nenhum plano encontrado")
                return
                
            for plano in planos:
                # Mostra "Plano Anual (Limite: 1)"
                texto = f"{plano.get('name', 'Plano Desconhecido')} (Limite: {plano.get('machine_limit', '?')})"
                # Armazena o ID (ex: 'annual') como dado
                self.plan_combo.addItem(texto, userData=plano.get('id'))
                
            self.plan_combo.setEnabled(True)
            
        except Exception as e:
            self.plan_combo.clear()
            self.plan_combo.addItem("Erro ao carregar planos")
            QMessageBox.critical(self, "Erro de Rede", f"Não foi possível buscar os planos: {e}")

    def handle_accept(self):
        """Valida os dados e chama o gerenciador para criar a licença."""
        email = self.email_input.text().strip()
        plan_id_selecionado = self.plan_combo.currentData() # Pega o ID ('annual')
        
        if not email or "@" not in email:
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um e-mail válido.")
            return
            
        if not plan_id_selecionado:
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, selecione um plano válido.")
            return

        # Desativa os botões enquanto processa
        self.button_box.setEnabled(False)
        
        # Chama o gerenciador
        success, result = self.firebase_manager.create_license(email, plan_id_selecionado)
        
        if success:
            license_key = result
            # Mostra a chave gerada para o admin copiar
            QMessageBox.information(self, "Sucesso", 
                                    f"Licença criada com sucesso!\n\nE-mail: {email}\nChave: {license_key}\n\n(Chave copiada para a área de transferência)")
            # Copia para a área de transferência
            QApplication.clipboard().setText(license_key)
            self.accept() # Fecha o diálogo
        else:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar a licença:\n{result}")
            self.button_box.setEnabled(True) # Reativa os botões