# tela_inicial.py
# Descrição: Versão modificada para integração com qdarktheme.
# Remove stylesheet local e adiciona "cssClass" "primary" ao botão novo.

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QVBoxLayout,
                               QHBoxLayout, QListWidget, QListWidgetItem,
                               QFileDialog, QMessageBox, QScrollArea, QSizePolicy)

import gerenciador_config
import gerenciador_recuperacao
from dialogs import DialogoRecuperacao
from modelos_trabalho import get_nomes_modelos

class ProjetoRecenteItem(QWidget):
    """Widget customizado para exibir um item na lista de projetos recentes."""
    def __init__(self, nome, caminho, parent=None):
        super().__init__(parent)
        
        self.setObjectName("ProjetoRecenteItem")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8) # Adiciona um padding interno
        
        nome_label = QLabel(f"<b>{nome}</b>")
        nome_label.setWordWrap(True) # Permite quebra de linha para nomes longos
        
        caminho_label = QLabel(caminho)
        caminho_label.setProperty("cssClass", "caminho_projeto_recente")
        caminho_label.setWordWrap(True)
        
        layout.addWidget(nome_label)
        layout.addWidget(caminho_label)
        self.setLayout(layout)

class TelaInicial(QDialog):
    def __init__(self, is_dark: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bem-vindo ao Formatheus")
        self.setMinimumSize(950, 550)
        
        self.resultado = (None, None) 

        # --- INÍCIO DA ADIÇÃO ---
        # Salva o estado do tema e define o caminho dos ícones
        self.is_dark = is_dark
        self.ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")
        suffix = "-white" if self.is_dark else ""
        # --- FIM DA ADIÇÃO ---

        main_layout = QHBoxLayout(self)

        # --- Painel Esquerdo (Ações) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(250)

        titulo_label = QLabel("Formatheus")
        titulo_label.setFont(QtGui.QFont("Segoe UI", 24, QtGui.QFont.Weight.Bold))
        
        btn_novo = QPushButton("Novo Projeto")
        btn_novo.setProperty("cssClass", "primary")
        # --- MODIFICADO: Usa ícone personalizado 'doc.png' ---
        btn_novo.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"doc{suffix}.png")))
        btn_novo.clicked.connect(self.on_novo_projeto)

        btn_abrir = QPushButton("Abrir Outro...")
        btn_abrir.setObjectName("BtnAbrir") 
        btn_abrir.setProperty("cssClass", "utility")
        # --- MODIFICADO: Usa ícone personalizado 'browser.png' ---
        btn_abrir.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"browser{suffix}.png")))
        btn_abrir.clicked.connect(self.on_abrir_projeto)

        # Botão de Gerenciamento de Recuperação
        btn_recuperacao = QPushButton("Gerenciar Recuperação")
        btn_recuperacao.setObjectName("BtnRecuperar") 
        btn_recuperacao.setProperty("cssClass", "utility")
        # --- MODIFICADO: Usa ícone personalizado 'restore.png' ---
        btn_recuperacao.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"restore{suffix}.png")))
        btn_recuperacao.clicked.connect(self.on_gerenciar_recuperacao)

        left_layout.addWidget(titulo_label)
        left_layout.addSpacing(20)
        left_layout.addWidget(btn_novo)
        left_layout.addWidget(btn_abrir)
        left_layout.addSpacing(20)
        left_layout.addWidget(btn_recuperacao)
        left_layout.addStretch()

        # --- Painel Central (Projetos Recentes) ---
        # (ESTA PARTE ESTAVA FALTANDO)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        
        recentes_label = QLabel("Projetos Recentes")
        recentes_label.setFont(QtGui.QFont("Segoe UI", 16))
        
        self.lista_recentes = QListWidget()
        self.lista_recentes.setObjectName("ListaRecentes") # ID para o QSS
        self.lista_recentes.itemDoubleClicked.connect(self.on_item_recente_clicado)
        self.popular_projetos_recentes()
        
        center_layout.addWidget(recentes_label)
        center_layout.addWidget(self.lista_recentes)

        # --- Painel Direito (Modelos) ---
        # (ESTA PARTE ESTAVA FALTANDO)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_panel.setFixedWidth(300) 
        
        modelos_label = QLabel("Iniciar com um Modelo")
        modelos_label.setFont(QtGui.QFont("Segoe UI", 16))

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.modelos_layout = QVBoxLayout(scroll_content)
        self.modelos_layout.setSpacing(10)
        
        for nome_modelo in get_nomes_modelos():
            btn = QPushButton(nome_modelo)
            btn.setProperty("cssClass", "utility") # Usa o estilo cinza/secundário
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            btn.clicked.connect(lambda checked=False, m=nome_modelo: self.on_novo_com_modelo(m))
            self.modelos_layout.addWidget(btn)
        
        self.modelos_layout.addStretch()
        scroll_area.setWidget(scroll_content)
        
        right_layout.addWidget(modelos_label)
        right_layout.addWidget(scroll_area)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(center_panel, 1)
        main_layout.addWidget(right_panel)
    
    def popular_projetos_recentes(self):
        self.lista_recentes.clear()
        projetos = gerenciador_config.get_projetos_recentes()
        for proj in projetos:
            item = QListWidgetItem(self.lista_recentes)
            item_widget = ProjetoRecenteItem(proj["name"], proj["path"])
            
            # Adiciona uma margem *externa* ao item da lista
            item.setSizeHint(item_widget.sizeHint() + QtCore.QSize(0, 8)) # Adiciona 8px de margem vertical
            
            item.setData(QtCore.Qt.ItemDataRole.UserRole, proj["path"])
            self.lista_recentes.addItem(item)
            self.lista_recentes.setItemWidget(item, item_widget)

    def on_novo_projeto(self):
        modelo_padrao = get_nomes_modelos()[0] if get_nomes_modelos() else "Trabalho Acadêmico"
        self.resultado = ("novo", modelo_padrao)
        self.accept()
        
    def on_novo_com_modelo(self, nome_modelo):
        self.resultado = ("novo", nome_modelo)
        self.accept()

    def on_abrir_projeto(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Carregar Projeto", "", "Arquivo ABNF (*.abnf)")
        if caminho:
            self.resultado = ("abrir", caminho)
            self.accept()

    def on_item_recente_clicado(self, item):
        caminho = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if os.path.exists(caminho):
            self.resultado = ("abrir", caminho)
            self.accept()
        else:
            QMessageBox.warning(self, "Arquivo não encontrado",
                f"O arquivo do projeto não foi encontrado no caminho:\n\n{caminho}\n\nEle pode ter sido movido ou excluído.")
            gerenciador_config.remover_projeto_recente(caminho)
            self.popular_projetos_recentes()

    def on_gerenciar_recuperacao(self):
        arquivos = gerenciador_recuperacao.verificar_arquivos_recuperaveis()
        if not arquivos:
            QMessageBox.information(self, "Gerenciar Recuperação", "Nenhum arquivo de recuperação foi encontrado.")
            return

        dialog = DialogoRecuperacao(arquivos, self)
        if dialog.exec():
            # Se o usuário escolheu recuperar, passa a lista de arquivos para o main_app
            if dialog.arquivos_para_recuperar:
                self.resultado = ("recuperar", dialog.arquivos_para_recuperar)
                # Descarta também os arquivos que o usuário marcou para descarte na mesma ação
                for arq_info in dialog.arquivos_para_descartar:
                    gerenciador_recuperacao.limpar_recuperacao_pelo_caminho_direto(arq_info['recovery_file_path'])
                self.accept()
            # Se ele só escolheu descartar
            elif dialog.arquivos_para_descartar:
                for arq_info in dialog.arquivos_para_descartar:
                    gerenciador_recuperacao.limpar_recuperacao_pelo_caminho_direto(arq_info['recovery_file_path'])
                QMessageBox.information(self, "Limpeza Concluída", "Os arquivos de recuperação selecionados foram descartados.")

    def get_resultado(self):
        return self.resultado