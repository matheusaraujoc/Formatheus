# admin_dashboard.py

import sys
import os
# --- INÍCIO DAS ADIÇÕES ---
from datetime import datetime, timezone 
from PySide6.QtGui import QIcon, QFont, QAction, QColor
# --- FIM DAS ADIÇÕES ---

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                               QPushButton, QTableWidget, QTableWidgetItem, QLineEdit,
                               QMessageBox, QHeaderView, QLabel, QMenu)
from PySide6.QtCore import Qt

from admin_utils import resource_path, save_admin_config
from firebase_admin_manager import FirebaseManager
from dialog_nova_licenca import DialogoNovaLicenca

# --- NOVA CLASSE AUXILIAR PARA ORDENAÇÃO ---
class NumericTableWidgetItem(QTableWidgetItem):
    """Item de tabela customizado para permitir ordenação numérica correta."""
    def __lt__(self, other):
        # Tenta extrair o número do texto (ex: "10 dias" -> 10)
        # Se não conseguir, usa um valor muito alto (para "N/A", "Vitalício")
        try:
            # Pega o dado numérico que salvamos
            self_data = self.data(Qt.ItemDataRole.UserRole)
            other_data = other.data(Qt.ItemDataRole.UserRole)
            
            # Se um dos dados for nulo (não deveria acontecer, mas por segurança)
            if self_data is None: return True
            if other_data is None: return False
                
            return self_data < other_data
        except:
            # Fallback para ordenação de texto se algo der errado
            return super().__lt__(other)

# --- FIM DA CLASSE AUXILIAR ---


class AdminDashboardWindow(QMainWindow):
    
    def __init__(self, firebase_manager: FirebaseManager):
        super().__init__()
        self.setWindowTitle("Formatheus - Painel Administrativo")
        self.setMinimumSize(1100, 600) # Aumentei o tamanho para as novas colunas
        
        self.firebase_manager = firebase_manager
        
        try:
            icon_path = resource_path(os.path.join("admin_assets", "icons", "formatheus_admin.ico"))
            self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Aviso: Ícone de admin não encontrado: {e}")
            
        self.create_menu_bar()

        # --- UI Principal ---
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        main_layout = QVBoxLayout(self.main_widget)
        
        # --- Barra de Ferramentas (Toolbar) ---
        toolbar_layout = QHBoxLayout()
        
        self.btn_nova_licenca = QPushButton("Criar Nova Licença")
        self.btn_nova_licenca.setProperty("cssClass", "primary")
        self.btn_nova_licenca.clicked.connect(self.abrir_dialogo_nova_licenca)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por e-mail ou chave...")
        self.search_input.textChanged.connect(self.filtrar_tabela)

        self.btn_recarregar = QPushButton("Recarregar Lista")
        self.btn_recarregar.clicked.connect(self.carregar_licencas)
        
        toolbar_layout.addWidget(self.btn_nova_licenca)
        toolbar_layout.addWidget(self.btn_recarregar)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(QLabel("Filtrar:"))
        toolbar_layout.addWidget(self.search_input)
        
        # --- Tabela de Licenças ---
        self.table_widget = QTableWidget()
        
        # --- INÍCIO DA MUDANÇA (Novas Colunas) ---
        self.table_widget.setColumnCount(8) # Mudou de 6 para 8
        self.table_widget.setHorizontalHeaderLabels([
            "Chave (ID)", "E-mail", "Plano", "Status", "Dispositivos", 
            "Data Expiração", "Dias Restantes", "Ações"
        ])
        
        # Ajusta o tamanho das colunas
        self.table_widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive) # Chave
        self.table_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive) # Email
        self.table_widget.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Status
        self.table_widget.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Dispositivos
        self.table_widget.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # Data Exp.
        self.table_widget.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Interactive) # Dias Rest.
        self.table_widget.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents) # Ações
        # --- FIM DA MUDANÇA ---
        
        self.table_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table_widget.setSortingEnabled(True)
        
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.customContextMenuRequested.connect(self.show_table_context_menu)
        
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table_widget)
        
        self.carregar_licencas()

    def create_menu_bar(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Arquivo")
        
        logout_action = QAction("Sair (Logout)", self)
        logout_action.triggered.connect(self.handle_logout)
        file_menu.addAction(logout_action)
        
        exit_action = QAction("Fechar Programa", self)
        exit_action.triggered.connect(self.close) 
        file_menu.addAction(exit_action)

    def handle_logout(self):
        save_admin_config(None, False)
        QApplication.instance().exit(99) 

    def show_table_context_menu(self, pos):
        row = self.table_widget.rowAt(pos.y()) 
        if row < 0: return 

        key_item = self.table_widget.item(row, 0)   
        email_item = self.table_widget.item(row, 1) 

        menu = QMenu()
        
        if key_item and key_item.text(): 
            copy_key_action = menu.addAction(f"Copiar Chave: {key_item.text()[:15]}...")
            copy_key_action.triggered.connect(lambda: QApplication.clipboard().setText(key_item.text()))
            
        if email_item and email_item.text(): 
            copy_email_action = menu.addAction(f"Copiar E-mail: {email_item.text()}")
            copy_email_action.triggered.connect(lambda: QApplication.clipboard().setText(email_item.text()))
        
        if not menu.isEmpty():
            menu.exec(self.table_widget.viewport().mapToGlobal(pos))

    # --- INÍCIO DA MUDANÇA (Lógica de Carregamento) ---
    def carregar_licencas(self):
        """Busca licenças do Firestore e preenche a tabela."""
        self.table_widget.setSortingEnabled(False)
        self.table_widget.setRowCount(0) 
        
        licencas = self.firebase_manager.get_all_licenses()
        
        # Pega a data atual (com fuso horário UTC)
        # Usamos UTC pois é o padrão que o Firestore salva
        hoje = datetime.now(timezone.utc)
        
        for row, lic_data in enumerate(licencas):
            self.table_widget.insertRow(row)
            
            key = lic_data.get('key', 'N/A')
            email = lic_data.get('email', 'N/A')
            plan_id = lic_data.get('plan_id', 'N/A')
            status = lic_data.get('status', 'N/A')
            devices = lic_data.get('active_devices', {})
            device_count = len(devices)

            # Colunas Padrão
            self.table_widget.setItem(row, 0, QTableWidgetItem(key))
            self.table_widget.setItem(row, 1, QTableWidgetItem(email))
            self.table_widget.setItem(row, 2, QTableWidgetItem(plan_id))
            
            status_item = QTableWidgetItem(status.title())
            if status == "active":
                status_item.setForeground(QColor("darkGreen")) # Verde
            else:
                status_item.setForeground(QColor("red")) # Vermelho
            self.table_widget.setItem(row, 3, status_item)
            
            self.table_widget.setItem(row, 4, QTableWidgetItem(str(device_count)))
            
            # --- Novas Colunas (Data e Dias) ---
            
            # Pega a data de expiração (pode não existir)
            expires_at = lic_data.get('expires_at') 
            
            # Cria os itens da tabela (usando nossa classe customizada)
            item_expiracao = NumericTableWidgetItem()
            item_dias = NumericTableWidgetItem()

            if expires_at:
                # Converte o timestamp do Firestore (que já é UTC)
                # (Se o SDK não converter, use expires_at.to_datetime())
                
                # 1. Coluna "Data Expiração"
                data_str = expires_at.strftime("%d/%m/%Y")
                item_expiracao.setText(data_str)
                # Salva o timestamp para ordenação numérica
                item_expiracao.setData(Qt.ItemDataRole.UserRole, expires_at.timestamp())

                # 2. Coluna "Dias Restantes"
                delta = expires_at - hoje
                dias_restantes = delta.days # Pega apenas a parte inteira (dias)

                # Salva o número de dias para ordenação
                item_dias.setData(Qt.ItemDataRole.UserRole, dias_restantes)
                
                if dias_restantes < 0:
                    item_dias.setText(f"Expirado ({abs(dias_restantes)} dias)")
                    item_dias.setForeground(QColor("red")) # Vermelho
                elif dias_restantes <= 30:
                    item_dias.setText(f"{dias_restantes} dias")
                    item_dias.setForeground(QColor("orange")) # Laranja
                else:
                    item_dias.setText(f"{dias_restantes} dias")
                    item_dias.setForeground(QColor("darkGreen")) # Verde

            else:
                # Se 'expires_at' não existe, é Vitalício
                item_expiracao.setText("Vitalício")
                item_dias.setText("N/A")
                
                # Define um número muito alto para ordenação (para Vitalício ficar por último)
                item_expiracao.setData(Qt.ItemDataRole.UserRole, 9999999999)
                item_dias.setData(Qt.ItemDataRole.UserRole, 9999999999)

            self.table_widget.setItem(row, 5, item_expiracao)
            self.table_widget.setItem(row, 6, item_dias)
            
            # --- Fim das Novas Colunas ---

            # Coluna de Ações (agora é a coluna 7)
            btn_text = "Desativar" if status == "active" else "Reativar"
            btn_toggle = QPushButton(btn_text)
            if status == "active":
                btn_toggle.setProperty("cssClass", "destructive") 
            
            btn_toggle.clicked.connect(
                lambda checked=False, k=key, s=status: self.toggle_status(k, s)
            )
            
            self.table_widget.setCellWidget(row, 7, btn_toggle) # <-- MUDOU PARA 7

        self.table_widget.setSortingEnabled(True) 
    # --- FIM DA MUDANÇA ---

    def filtrar_tabela(self, texto_filtro):
        """Filtra a tabela por e-mail ou chave."""
        texto_filtro = texto_filtro.lower()
        for row in range(self.table_widget.rowCount()):
            key_item = self.table_widget.item(row, 0)
            email_item = self.table_widget.item(row, 1)
            
            key_match = texto_filtro in key_item.text().lower()
            email_match = email_item and (texto_filtro in email_item.text().lower())
            
            visivel = key_match or email_match
                       
            self.table_widget.setRowHidden(row, not visivel)

    def abrir_dialogo_nova_licenca(self):
        """Abre o diálogo de criação e atualiza a tabela se for bem-sucedido."""
        dialog = DialogoNovaLicenca(self.firebase_manager, self)
        
        if dialog.exec():
            self.carregar_licencas() 

    def toggle_status(self, license_key, current_status):
        """Chamado pelo botão 'Desativar/Reativar'."""
        novo_status_texto = "DESATIVAR" if current_status == "active" else "REATIVAR"
        
        resposta = QMessageBox.question(self, "Confirmar Ação",
            f"Tem certeza que deseja {novo_status_texto} a licença:\n{license_key}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
        if resposta == QMessageBox.StandardButton.Yes:
            success, message = self.firebase_manager.toggle_license_status(license_key, current_status)
            if success:
                QMessageBox.information(self, "Sucesso", message)
                self.carregar_licencas() 
            else:
                QMessageBox.critical(self, "Erro", message)