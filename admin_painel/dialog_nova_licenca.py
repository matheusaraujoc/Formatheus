# dialog_nova_licenca.py

import sys
import os
from datetime import date 

from PySide6.QtWidgets import (QApplication, QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
                               QComboBox, QDialogButtonBox, QMessageBox, QLabel,
                               QDateEdit) 
from PySide6.QtGui import QIcon, QFont
# --- INÍCIO DA CORREÇÃO ---
from PySide6.QtCore import Qt, QDate, Slot # <--- Slot foi adicionado aqui
# --- FIM DA CORREÇÃO ---

from admin_utils import resource_path

class DialogoNovaLicenca(QDialog):
    
    def __init__(self, firebase_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Criar Nova Licença")
        self.setMinimumWidth(400)
        
        self.firebase_manager = firebase_manager
        
        try:
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
        
        self.date_expire_input = QDateEdit()
        self.date_expire_input.setCalendarPopup(True)
        self.date_expire_input.setDate(QDate.currentDate())
        
        form_layout.addRow(QLabel("Email do Cliente:"), self.email_input)
        form_layout.addRow(QLabel("Plano:"), self.plan_combo)
        form_layout.addRow(QLabel("Data de Expiração:"), self.date_expire_input) 
        
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.handle_accept)
        self.button_box.rejected.connect(self.reject)

        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button:
            ok_button.setProperty("cssClass", "primary")
        
        layout.addLayout(form_layout)
        layout.addWidget(self.button_box)
        
        self.plan_combo.currentIndexChanged.connect(self.on_plan_changed)
        
        self.carregar_planos()

    def carregar_planos(self):
        """Busca os planos do Firestore e popula o ComboBox."""
        try:
            self.plan_combo.setEnabled(False)
            self.plan_combo.addItem("A carregar planos...")
            
            planos = self.firebase_manager.get_all_plans()
            
            self.plan_combo.clear()
            if not planos:
                self.plan_combo.addItem("Erro: Nenhum plano encontrado")
                return
                
            for plano in planos:
                nome = plano.get('name', 'Plano Desconhecido')
                limite = plano.get('machine_limit', '?')
                texto = f"{nome} (Limite: {limite})"
                
                self.plan_combo.addItem(texto, userData=plano)
                
            self.plan_combo.setEnabled(True)
            self.on_plan_changed(0) # Força a atualização da data para o primeiro item
            
        except Exception as e:
            self.plan_combo.clear()
            self.plan_combo.addItem("Erro ao carregar planos")
            QMessageBox.critical(self, "Erro de Rede", f"Não foi possível buscar os planos: {e}")

    @Slot(int) # <--- Esta linha agora funciona
    def on_plan_changed(self, index):
        """Chamado quando o usuário troca o plano no ComboBox."""
        plano_data = self.plan_combo.itemData(index) 
        
        if not plano_data:
            return

        if "duration_days" in plano_data:
            dias = int(plano_data["duration_days"])
            
            data_expiracao = QDate.currentDate().addDays(dias)
            
            self.date_expire_input.setDate(data_expiracao)
            self.date_expire_input.setEnabled(True) 
        else:
            self.date_expire_input.setEnabled(False) 
            self.date_expire_input.setDate(QDate(2099, 12, 31))

    def handle_accept(self):
        """Valida os dados e chama o gerenciador para criar a licença."""
        email = self.email_input.text().strip()
        
        plano_selecionado = self.plan_combo.currentData() 
        
        if not email or "@" not in email:
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, insira um e-mail válido.")
            return
            
        if not plano_selecionado:
            QMessageBox.warning(self, "Dados Inválidos", "Por favor, selecione um plano válido.")
            return

        plan_id = plano_selecionado.get('id')
        
        expiration_date = None 
        
        if "duration_days" in plano_selecionado:
            q_date = self.date_expire_input.date()
            expiration_date = date(q_date.year(), q_date.month(), q_date.day())

        self.button_box.setEnabled(False)
        
        success, result = self.firebase_manager.create_license(
            email, 
            plan_id, 
            expiration_date 
        )
        
        if success:
            license_key = result
            QMessageBox.information(self, "Sucesso", 
                                    f"Licença criada com sucesso!\n\nE-mail: {email}\nChave: {license_key}\n\n(Chave copiada para a área de transferência)")
            QApplication.clipboard().setText(license_key)
            self.accept()
        else:
            QMessageBox.critical(self, "Erro", f"Não foi possível criar a licença:\n{result}")
            self.button_box.setEnabled(True)