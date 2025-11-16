# main_app.py
# Descrição: Versão completa com integração do qdarktheme
#
# ATUALIZAÇÃO (vX.X):
# 1. Ícones do sistema (fromTheme) agora são recarregados
#    ao trocar o tema, corrigindo ícones pretos em fundos escuros.
# 2. Criado o método _atualizar_icones_do_tema()
# 3. Widgets com ícones convertidos para atributos self.
#
# ATUALIZAÇÃO (vX.X - Preview em Thread):
# 1. Adicionado PreviewWorker e QThread para gerar HTML em segundo plano.
# 2. Implementada lógica de fila (is_preview_worker_busy, pending_preview_update).
# 3. _atualizar_preview agora é um "despachante" que envia dados para a thread.
# 4. _apply_html_to_preview é o novo slot que recebe o HTML da thread.
# 5. Adicionado copy.deepcopy para segurança entre threads.
# 6. Adicionada limpeza da thread no closeEvent.
#

import sys
import os
import re

os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'

import shutil
from datetime import datetime
import copy # <-- NOVO: Para deepcopy (segurança da thread)

from PySide6 import QtWidgets, QtCore, QtGui 
# --- INÍCIO: Novas importações para Threading ---
from PySide6.QtCore import QObject, QThread, Signal, Slot
# --- FIM: Novas importações para Threading ---
from PySide6.QtWidgets import (QApplication, QWidget, QLabel, QLineEdit, QTextEdit,
                             QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                             QMessageBox, QTabWidget, QComboBox,
                             QFormLayout, QMenuBar, QCheckBox, QSplitter, QStyle)
from PySide6.QtGui import QAction, QKeySequence, QActionGroup, QIcon 
from PySide6.QtWebEngineCore import QWebEnginePage
from PySide6.QtWebEngineWidgets import QWebEngineView

# --- Tenta importar o tema ---
try:
    import qdarktheme
    HAS_THEME_LIB = True
except ImportError:
    HAS_THEME_LIB = False
# ------------------------

# --- IMPORTS DE ESTILO ---
import stylesheet 
# ------------------------

# --- Assume que os arquivos abaixo estão na mesma pasta ---
from documento import DocumentoABNT, Autor, Capitulo
from gerador_docx import GeradorDOCX
from referencia import Livro, Artigo, Site
from aba_conteudo import AbaConteudo
from gerador_preview import GeradorHTMLPreview
from gerenciador_projeto import GerenciadorProjetos
from dialogs import ReferenciaDialog
from dialogo_figura import DialogoFigura
from dialogo_brasao import DialogoBrasao
from modelos_trabalho import get_estrutura_por_nome, get_nomes_modelos

# --- Imports para a tela inicial e gerenciamento de configuração/recuperação ---
from tela_inicial import TelaInicial
import gerenciador_config
import gerenciador_recuperacao
from dialogs import DialogoRecuperacao
# -------------------------------------------------------------------------------


# --- INÍCIO: Worker de Preview (Anti-travamento) ---
class PreviewWorker(QObject):
    """Trabalhador para gerar HTML em uma thread separada."""
    finished = Signal(str) # Emite o HTML (str) quando termina

    @Slot(object)
    def run_generation(self, documento_copiado):
        """Executa a tarefa pesada (geração de HTML)."""
        try:
            # 'documento_copiado' é uma deepcopy do self.documento
            gerador = GeradorHTMLPreview(documento_copiado)
            html_content = gerador.gerar_html()
            self.finished.emit(html_content)
        except Exception as e:
            # Emite um sinal de erro
            print(f"Erro na thread do worker de preview: {e}")
            # Emite string vazia para sinalizar o fim
            self.finished.emit("") 

# --- FIM: Worker de Preview ---


class ABNTHelperApp(QWidget):
    
    # --- INÍCIO: Adicionar Signal para a thread ---
    # Signal para enviar o objeto 'documento' (copiado) para o worker
    request_preview_update = Signal(object) 
    # --- FIM: Adicionar Signal ---
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Formatheus')
        self.setGeometry(100, 100, 1400, 800)

        self.ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")

        self.config = gerenciador_config.carregar_config()
        self.documento = DocumentoABNT()
        self.gerenciador_projeto = GerenciadorProjetos()
        self.caminho_projeto_atual = None
        self.modificado = False
        self._populando_ui = False
        
        self.wants_to_restart = False
        
        saved_theme = self.config['ui_settings']['theme']
        self.is_dark_theme = (saved_theme == "dark")
        
        self.is_search_bar_visible = self.config['ui_settings']['search_bar_visible']

        self.BASE_ZOOM_FACTOR = 0.75
        initial_editor_width = 800
        initial_preview_width = 600
        total_initial_width = initial_editor_width + initial_preview_width
        self.NEUTRAL_PREVIEW_RATIO = initial_preview_width / total_initial_width

        self.modo_preview = "lado_a_lado"
        self.preview_update_timer = QtCore.QTimer(self)
        self.preview_update_timer.setSingleShot(True)
        self.preview_update_timer.setInterval(750)
        self.preview_update_timer.timeout.connect(self._atualizar_preview)
        
        # --- INÍCIO: Flags e setup da Thread de Preview ---
        self.is_preview_worker_busy = False
        self.pending_preview_update = False
        
        self.preview_thread = QThread()
        self.preview_worker = PreviewWorker()
        self.preview_worker.moveToThread(self.preview_thread)
        
        # Conexões da Thread
        # Conecta o sinal que pede o trabalho ao slot do worker que o executa
        self.request_preview_update.connect(self.preview_worker.run_generation) 
        # Conecta o sinal de 'finalizado' do worker ao slot que aplica o HTML na UI
        self.preview_worker.finished.connect(self._apply_html_to_preview) 
        
        self.preview_thread.start()
        # --- FIM: Flags e setup da Thread de Preview ---
        
        self.autosave_timer = QtCore.QTimer(self)
        intervalo_ms = self.config['recovery']['autosave_periodic_interval_min'] * 60 * 1000
        self.autosave_timer.setInterval(intervalo_ms)
        self.autosave_timer.timeout.connect(self._auto_salvar_recuperacao)
        
        self.scroll_posicao = 0
        self.main_layout = QVBoxLayout(self)
        
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        self.main_content_widget = None
                                
        self._build_ui()
        self._conectar_sinais_modificacao()
        gerenciador_recuperacao.setup_diretorios()
        
        # Atualiza os ícones com base no tema salvo
        self._atualizar_icones_do_tema(self.is_dark_theme)

    @QtCore.Slot()
    def toggle_theme(self):
        """Alterna o tema da aplicação inteira."""
        if not HAS_THEME_LIB: return
        
        self.is_dark_theme = not self.is_dark_theme
        theme = "dark" if self.is_dark_theme else "light"
        
        # --- MUDANÇA: Atualiza ícones ANTES de aplicar o tema ---
        self._atualizar_icones_do_tema(self.is_dark_theme)
        # --- FIM DA MUDANÇA ---
        
        qss = qdarktheme.load_stylesheet(theme)
        qss += stylesheet.get_style_sheet() 
        
        QApplication.instance().setStyleSheet(qss)
        
        self.config['ui_settings']['theme'] = theme
        gerenciador_config.salvar_config(self.config)

    def _atualizar_icones_do_tema(self, is_dark):
        """
        Recarrega todos os ícones baseados no tema, carregando
        os arquivos manuais da pasta assets/icons.
        """
        suffix = "-white" if is_dark else ""
        
        # Mapeamento de 'fromTheme' para os nomes de arquivo da sua biblioteca
        
        # 1. Ícones do Menu
        # (Estou mapeando os nomes 'fromTheme' para os nomes da sua imagem)
        self.acao_novo.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"file{suffix}.png")))
        self.acao_carregar.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"folder{suffix}.png")))
        self.acao_salvar.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"save{suffix}.png")))
        self.acao_salvar_como.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"save{suffix}.png"))) # Reutilizando 'save'
        self.acao_voltar.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"previous{suffix}.png")))
        self.acao_sair.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"x{suffix}.png")))
        self.acao_localizar.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"search{suffix}.png")))
        
        # 2. Botão Gerar Docx
        self.generate_btn.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"doc{suffix}.png")))
        
        # 3. Aba Geral
        self.btn_procurar_esquerdo.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"browser{suffix}.png")))
        self.btn_procurar_direito.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"browser{suffix}.png")))
        
        # 4. Aba Referências
        # (Sua imagem não tem 'list-add' ou 'document-edit', estou usando substitutos)
        self.btn_add_ref.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"doc{suffix}.png"))) # Usando 'doc' como substituto
        self.btn_edit_ref.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"doc{suffix}.png"))) # Usando 'doc' como substituto
        self.btn_del_ref.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"trash{suffix}.png")))
        
        # 5. Painel de Preview (Busca)
        self.btn_buscar_anterior.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"previous{suffix}.png")))
        self.btn_buscar_proximo.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"next{suffix}.png")))
        self.btn_fechar_busca.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"x{suffix}.png")))
        self.btn_atualizar_preview.setIcon(QtGui.QIcon(os.path.join(self.ICON_PATH, f"restore{suffix}.png")))
        
        # 6. Ícones Personalizados (assets) - Esta parte já funciona!
        if hasattr(self, 'aba_conteudo'):
            self.aba_conteudo.update_theme_icons(is_dark)

    def _build_ui(self):
        menu_bar = QMenuBar(self)
        self.main_layout.setMenuBar(menu_bar)

        menu_arquivo = menu_bar.addMenu("&Arquivo")
        
        # Convertido para self.
        self.acao_novo = QAction("&Novo Projeto", self)
        self.acao_novo.triggered.connect(self._novo_projeto)
        menu_arquivo.addAction(self.acao_novo)
        
        self.acao_carregar = QAction("&Carregar Projeto...", self)
        self.acao_carregar.triggered.connect(self._carregar_projeto)
        menu_arquivo.addAction(self.acao_carregar)
        menu_arquivo.addSeparator()

        self.acao_salvar = QAction("&Salvar", self)
        self.acao_salvar.setShortcut("Ctrl+S")
        self.acao_salvar.triggered.connect(self._salvar_projeto)
        menu_arquivo.addAction(self.acao_salvar)
        
        self.acao_salvar_como = QAction("Salvar &Como...", self)
        self.acao_salvar_como.triggered.connect(self._salvar_projeto_como)
        menu_arquivo.addAction(self.acao_salvar_como)
        menu_arquivo.addSeparator()

        self.acao_voltar = QAction("Voltar à Tela Inicial", self)
        self.acao_voltar.triggered.connect(self._voltar_tela_inicial)
        menu_arquivo.addAction(self.acao_voltar)
        menu_arquivo.addSeparator()

        self.acao_sair = QAction("Sai&r", self)
        self.acao_sair.triggered.connect(self.close)
        menu_arquivo.addAction(self.acao_sair)
        
        menu_editar = menu_bar.addMenu("&Editar")
        
        self.acao_localizar = QAction("&Localizar...", self)
        self.acao_localizar.setShortcut(QKeySequence.StandardKey.Find)
        self.acao_localizar.triggered.connect(self._alternar_barra_busca)
        menu_editar.addAction(self.acao_localizar)

        menu_visualizacao = menu_bar.addMenu("&Visualização")
        grupo_modos = QActionGroup(self)
        grupo_modos.setExclusive(True)
        
        self.acao_modo_lado_a_lado = QAction("Pré-visualização Lado a Lado", self, checkable=True)
        self.acao_modo_lado_a_lado.setChecked(True)
        self.acao_modo_lado_a_lado.triggered.connect(lambda: self._alternar_modo_preview("lado_a_lado"))
        menu_visualizacao.addAction(self.acao_modo_lado_a_lado)
        grupo_modos.addAction(self.acao_modo_lado_a_lado)
        
        self.acao_modo_aba = QAction("Pré-visualização como Aba", self, checkable=True)
        self.acao_modo_aba.triggered.connect(lambda: self._alternar_modo_preview("aba"))
        menu_visualizacao.addAction(self.acao_modo_aba)
        grupo_modos.addAction(self.acao_modo_aba)

        menu_visualizacao.addSeparator()
        self.acao_alternar_tema = QAction("Alternar Tema (Claro/Escuro) 🌗", self)
        self.acao_alternar_tema.triggered.connect(self.toggle_theme)
        menu_visualizacao.addAction(self.acao_alternar_tema)
        self.acao_alternar_tema.setEnabled(HAS_THEME_LIB)

        self.tabs = QTabWidget()
        self.aba_conteudo = AbaConteudo(self.documento)
        
        self.aba_conteudo.topicoSelecionadoParaNavegacao.connect(self._navegar_preview_para_ancora)
        
        self.tabs.addTab(self._criar_aba_geral(), "Geral e Pré-Textual")
        self.tabs.addTab(self.aba_conteudo, "Conteúdo Textual (Estrutura)")
        self.tabs.addTab(self._criar_aba_referencias(), "Referências")
        
        self.preview_container = self._criar_painel_preview() 

        self.generate_btn = QPushButton("Gerar .docx")
        self.generate_btn.setToolTip("Gerar o documento .docx final")
        self.generate_btn.setProperty("cssClass", "primary")
        self.generate_btn.clicked.connect(self._gerar_documento_final)
        self.tabs.setCornerWidget(self.generate_btn, QtCore.Qt.Corner.TopRightCorner)

        self._reconfigurar_layout() 

    def _criar_aba_geral(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label_config = QLabel("Configurações do Documento")
        label_config.setProperty("cssClass", "titulo")
        layout.addWidget(label_config)
        
        form_layout1 = QFormLayout()
        self.cfg_tipo = QComboBox()
        self.cfg_tipo.addItems(get_nomes_modelos())
        self.cfg_instituicao = QLineEdit()

        form_layout1.addRow("Tipo de Trabalho:", self.cfg_tipo)
        form_layout1.addRow("Instituição:", self.cfg_instituicao)

        self.cfg_posicao_brasao = QComboBox()
        self.cfg_posicao_brasao.addItems(["Nenhum", "Acima do Nome", "Lados (Esquerdo e Direito)", "Apenas Esquerdo", "Apenas Direito"])
        form_layout1.addRow("Posição do Brasão:", self.cfg_posicao_brasao)

        self.brasao_esquerdo_widget = QWidget()
        brasao_esquerdo_layout = QHBoxLayout(self.brasao_esquerdo_widget)
        brasao_esquerdo_layout.setContentsMargins(0,0,0,0)
        self.cfg_brasao_esquerdo_path = QLineEdit()
        self.cfg_brasao_esquerdo_path.setReadOnly(True)
        # Convertido para self.
        self.btn_procurar_esquerdo = QPushButton("Procurar...")
        self.btn_procurar_esquerdo.setProperty("cssClass", "outline-button") 
        brasao_esquerdo_layout.addWidget(self.cfg_brasao_esquerdo_path)
        brasao_esquerdo_layout.addWidget(self.btn_procurar_esquerdo)
        self.label_brasao_esquerdo = QLabel("Brasão Esquerdo/Único:")
        form_layout1.addRow(self.label_brasao_esquerdo, self.brasao_esquerdo_widget)

        self.brasao_direito_widget = QWidget()
        brasao_direito_layout = QHBoxLayout(self.brasao_direito_widget)
        brasao_direito_layout.setContentsMargins(0,0,0,0)
        self.cfg_brasao_direito_path = QLineEdit()
        self.cfg_brasao_direito_path.setReadOnly(True)
        # Convertido para self.
        self.btn_procurar_direito = QPushButton("Procurar...")
        self.btn_procurar_direito.setProperty("cssClass", "outline-button")
        brasao_direito_layout.addWidget(self.cfg_brasao_direito_path)
        brasao_direito_layout.addWidget(self.btn_procurar_direito)
        self.label_brasao_direito = QLabel("Brasão Direito:")
        form_layout1.addRow(self.label_brasao_direito, self.brasao_direito_widget)

        self.btn_procurar_esquerdo.clicked.connect(lambda: self._procurar_brasao('esquerdo'))
        self.btn_procurar_direito.clicked.connect(lambda: self._procurar_brasao('direito'))
        self.cfg_posicao_brasao.currentTextChanged.connect(self._atualizar_visibilidade_brasao)
        
        self.cfg_curso = QLineEdit()
        self.cfg_modalidade_curso = QLineEdit()
        self.cfg_titulo_pretendido = QLineEdit()
        self.cfg_cidade = QLineEdit()
        self.cfg_ano = QLineEdit()
        form_layout1.addRow("Nome do Curso (Ex: Ciência da Computação):", self.cfg_curso)
        form_layout1.addRow("Modalidade do Curso (Ex: Bacharelado):", self.cfg_modalidade_curso)
        form_layout1.addRow("Título Pretendido (Ex: Bacharel):", self.cfg_titulo_pretendido)
        form_layout1.addRow("Cidade:", self.cfg_cidade)
        form_layout1.addRow("Ano:", self.cfg_ano)
        layout.addLayout(form_layout1)
        
        label_pretextual = QLabel("Informações Pré-Textuais")
        label_pretextual.setProperty("cssClass", "titulo")
        layout.addWidget(label_pretextual)
        
        form_layout2 = QFormLayout()
        self.titulo_input = QLineEdit()
        self.autores_input = QTextEdit()
        self.orientador_input = QLineEdit()
        self.resumo_input = QTextEdit()
        self.keywords_input = QLineEdit()
        form_layout2.addRow("Título do Trabalho:", self.titulo_input)
        form_layout2.addRow("Autores (um por linha):", self.autores_input)
        form_layout2.addRow("Orientador(a):", self.orientador_input)
        form_layout2.addRow("Resumo:", self.resumo_input)
        form_layout2.addRow("Palavras-chave (separadas por ;):", self.keywords_input)
        layout.addLayout(form_layout2)
        
        self._atualizar_visibilidade_brasao(self.cfg_posicao_brasao.currentText())
        return widget

    @QtCore.Slot(str)
    def _procurar_brasao(self, lado: str):
        cfg = self.documento.configuracoes
        if lado == 'esquerdo':
            caminho_atual = cfg.caminho_brasao_esquerdo_original
            tamanho_atual = cfg.tamanho_brasao_esquerdo_cm
        else:
            caminho_atual = cfg.caminho_brasao_direito_original
            tamanho_atual = cfg.tamanho_brasao_direito_cm

        dialog = DialogoBrasao(caminho_original=caminho_atual, tamanho_cm=tamanho_atual, parent=self)
        if dialog.exec():
            dados = dialog.get_dados_brasao()
            if dados:
                if lado == 'esquerdo':
                    cfg.caminho_brasao_esquerdo_original = dados['original']
                    cfg.caminho_brasao_esquerdo_processado = dados['processado']
                    cfg.tamanho_brasao_esquerdo_cm = dados['tamanho_cm']
                    self.cfg_brasao_esquerdo_path.setText(dados['original'])
                else:
                    cfg.caminho_brasao_direito_original = dados['original']
                    cfg.caminho_brasao_direito_processado = dados['processado']
                    cfg.tamanho_brasao_direito_cm = dados['tamanho_cm']
                    self.cfg_brasao_direito_path.setText(dados['original'])
                self._marcar_modificado()

    @QtCore.Slot(str)
    def _atualizar_visibilidade_brasao(self, texto_selecionado):
        if texto_selecionado == "Nenhum":
            self.label_brasao_esquerdo.setVisible(False)
            self.brasao_esquerdo_widget.setVisible(False)
            self.label_brasao_direito.setVisible(False)
            self.brasao_direito_widget.setVisible(False)
        elif texto_selecionado == "Acima do Nome":
            self.label_brasao_esquerdo.setText("Brasão (centralizado):")
            self.label_brasao_esquerdo.setVisible(True)
            self.brasao_esquerdo_widget.setVisible(True)
            self.label_brasao_direito.setVisible(False)
            self.brasao_direito_widget.setVisible(False)
        elif texto_selecionado == "Lados (Esquerdo e Direito)":
            self.label_brasao_esquerdo.setText("Brasão Esquerdo:")
            self.label_brasao_esquerdo.setVisible(True)
            self.brasao_esquerdo_widget.setVisible(True)
            self.label_brasao_direito.setVisible(True)
            self.brasao_direito_widget.setVisible(True)
        elif texto_selecionado == "Apenas Esquerdo":
            self.label_brasao_esquerdo.setText("Brasão Esquerdo:")
            self.label_brasao_esquerdo.setVisible(True)
            self.brasao_esquerdo_widget.setVisible(True)
            self.label_brasao_direito.setVisible(False)
            self.brasao_direito_widget.setVisible(False)
        elif texto_selecionado == "Apenas Direito":
            self.label_brasao_esquerdo.setVisible(False)
            self.brasao_esquerdo_widget.setVisible(False)
            self.label_brasao_direito.setText("Brasão Direito:")
            self.label_brasao_direito.setVisible(True)
            self.brasao_direito_widget.setVisible(True)

    @QtCore.Slot()
    def _voltar_tela_inicial(self):
        if self._verificar_alteracoes_nao_salvas():
            self.wants_to_restart = True
            self.close()

    @QtCore.Slot(str)
    def _alternar_modo_preview(self, novo_modo):
        if self.modo_preview != novo_modo:
            self.modo_preview = novo_modo
            self._reconfigurar_layout()

    def _reconfigurar_layout(self):
        if self.main_content_widget is not None:
            self.main_content_widget.setParent(None)
            if isinstance(self.main_content_widget, QSplitter):
                self.main_content_widget.deleteLater()
        self.main_content_widget = None
        
        if self.modo_preview == "lado_a_lado":
            index_preview = self.tabs.indexOf(self.preview_container)
            if index_preview != -1:
                self.tabs.removeTab(index_preview)
            self.btn_atualizar_preview.setVisible(False)
            splitter = QSplitter(QtCore.Qt.Orientation.Horizontal, self)
            splitter.addWidget(self.tabs)
            splitter.addWidget(self.preview_container)
            
            # Define sua proporção personalizada
            splitter.setSizes([1000, 400]) 
            
            splitter.splitterMoved.connect(self._on_splitter_moved)
            
            # --- INÍCIO DA CORREÇÃO (Zoom Inicial) ---
            # Copia a lógica de zoom aqui para ser executada UMA VEZ no início.
            sizes = splitter.sizes()
            if len(sizes) == 2 and sum(sizes) > 0 and self.NEUTRAL_PREVIEW_RATIO > 0:
                total_width = sum(sizes)
                current_preview_width = sizes[1]
                
                if current_preview_width > 0:
                    current_ratio = current_preview_width / total_width
                    ratio_change = current_ratio / self.NEUTRAL_PREVIEW_RATIO
                    new_zoom = self.BASE_ZOOM_FACTOR * ratio_change
                    new_zoom = max(0.2, min(new_zoom, 3.0)) 
                    self.preview_display.setZoomFactor(new_zoom)
            # --- FIM DA CORREÇÃO (Zoom Inicial) ---
            
            self.main_content_widget = splitter
            self.preview_container.show()
        else:
            index_preview = self.tabs.indexOf(self.preview_container)
            if index_preview == -1:
                self.tabs.addTab(self.preview_container, "Pré-Visualização")
            self.btn_atualizar_preview.setVisible(True)
            self.main_content_widget = self.tabs
        
        self.main_layout.insertWidget(0, self.main_content_widget, 1)

    def _criar_aba_referencias(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        label_refs = QLabel("Gerenciador de Referências")
        label_refs.setProperty("cssClass", "titulo")
        layout.addWidget(label_refs)
        
        self.lista_referencias = QtWidgets.QListWidget()
        self.lista_referencias.itemDoubleClicked.connect(self._editar_referencia)
        layout.addWidget(self.lista_referencias)
        
        btn_layout = QHBoxLayout()
        
        # Convertido para self.
        self.btn_add_ref = QPushButton("Adicionar")
        self.btn_edit_ref = QPushButton("Editar Selecionada")
        self.btn_del_ref = QPushButton("Remover Selecionada")

        self.btn_add_ref.setProperty("cssClass", "primary")
        self.btn_edit_ref.setProperty("cssClass", "utility")
        self.btn_del_ref.setProperty("cssClass", "destructive")

        btn_layout.addWidget(self.btn_add_ref)
        btn_layout.addWidget(self.btn_edit_ref)
        btn_layout.addWidget(self.btn_del_ref)
        self.btn_add_ref.clicked.connect(self._adicionar_referencia)
        self.btn_edit_ref.clicked.connect(self._editar_referencia)
        self.btn_del_ref.clicked.connect(self._remover_referencia)
        layout.addLayout(btn_layout)
        
        return widget

    def _criar_painel_preview(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0,0,0,0)
        
        self.busca_toolbar = QWidget()
        busca_layout = QHBoxLayout(self.busca_toolbar)
        busca_layout.setContentsMargins(2, 5, 2, 5)
        self.busca_input = QLineEdit()
        self.busca_input.setPlaceholderText("Buscar na pré-visualização...")
        # Convertido para self.
        self.btn_buscar_anterior = QPushButton("Anterior")
        self.btn_buscar_proximo = QPushButton("Próximo")
        self.busca_case_sensitive = QCheckBox("Diferenciar M/m")
        self.btn_fechar_busca = QPushButton("Fechar")

        self.btn_buscar_anterior.setProperty("cssClass", "outline-button")
        self.btn_buscar_proximo.setProperty("cssClass", "outline-button")
        self.btn_fechar_busca.setProperty("cssClass", "outline-button") 

        busca_layout.addWidget(QLabel("Localizar:"))
        busca_layout.addWidget(self.busca_input)
        busca_layout.addWidget(self.btn_buscar_anterior)
        busca_layout.addWidget(self.btn_buscar_proximo)
        busca_layout.addWidget(self.busca_case_sensitive)
        busca_layout.addStretch()
        busca_layout.addWidget(self.btn_fechar_busca)
        layout.addWidget(self.busca_toolbar)
        
        self.busca_toolbar.setVisible(self.is_search_bar_visible)
        
        self.preview_display = QWebEngineView()
        self.preview_display.setHtml("<html><body><h1>Pré-Visualização</h1><p>A pré-visualização será atualizada aqui.</p></body></html>")
        
        self.preview_display.setZoomFactor(self.BASE_ZOOM_FACTOR)
        
        self.preview_display.loadFinished.connect(self._restaurar_scroll_preview)
        layout.addWidget(self.preview_display, 1)
        
        self.btn_atualizar_preview = QPushButton("Atualizar Pré-Visualização")
        self.btn_atualizar_preview.clicked.connect(self._atualizar_preview)
        self.btn_atualizar_preview.setVisible(False)
        layout.addWidget(self.btn_atualizar_preview)
        
        self.btn_buscar_proximo.clicked.connect(self._buscar_proximo_preview)
        self.btn_buscar_anterior.clicked.connect(self._buscar_anterior_preview)
        self.busca_input.returnPressed.connect(self._buscar_proximo_preview)
        self.btn_fechar_busca.clicked.connect(self._alternar_barra_busca)
        
        return widget

    @QtCore.Slot(int, int)
    def _on_splitter_moved(self, pos, index):
        """Ajusta o zoom da preview quando o splitter é movido."""
        if self.modo_preview != "lado_a_lado" or not isinstance(self.main_content_widget, QSplitter):
            return
        
        splitter = self.main_content_widget
        sizes = splitter.sizes()
        
        if len(sizes) != 2:
            return
            
        total_width = sum(sizes)
        if total_width == 0:
            return
            
        current_preview_width = sizes[1]
        
        if current_preview_width <= 0:
            return
            
        current_ratio = current_preview_width / total_width
        
        if self.NEUTRAL_PREVIEW_RATIO == 0:
            return
            
        ratio_change = current_ratio / self.NEUTRAL_PREVIEW_RATIO
        
        new_zoom = self.BASE_ZOOM_FACTOR * ratio_change
        
        new_zoom = max(0.2, min(new_zoom, 3.0)) 
        
        self.preview_display.setZoomFactor(new_zoom)

    @QtCore.Slot()
    def _alternar_barra_busca(self):
        is_visible = self.busca_toolbar.isVisible()
        new_visibility = not is_visible 
        
        self.busca_toolbar.setVisible(new_visibility)
        if new_visibility:
            self.busca_input.setFocus()
        
        self.is_search_bar_visible = new_visibility
        self.config['ui_settings']['search_bar_visible'] = self.is_search_bar_visible
        gerenciador_config.salvar_config(self.config)

    def _buscar_preview(self, direcao_reversa=False):
        texto_busca = self.busca_input.text()
        if not texto_busca: return
        flags = QWebEnginePage.FindFlag(0)
        if direcao_reversa:
            flags |= QWebEnginePage.FindFlag.FindBackward
        if self.busca_case_sensitive.isChecked():
            flags |= QWebEnginePage.FindFlag.FindCaseSensitively
        self.preview_display.findText(texto_busca, flags)

    @QtCore.Slot()
    def _buscar_proximo_preview(self):
        self._buscar_preview(direcao_reversa=False)
        
    @QtCore.Slot()
    def _buscar_anterior_preview(self):
        self._buscar_preview(direcao_reversa=True)
        
    @QtCore.Slot()
    def _disparar_atualizacao_automatica(self):
        if self.modo_preview == "lado_a_lado":
            self.preview_update_timer.start()
            
    def _salvar_scroll_preview(self):
        self.preview_display.page().runJavaScript("window.scrollY;", self._on_scroll_posicao_recebida)
        
    @QtCore.Slot(object)
    def _on_scroll_posicao_recebida(self, result):
        if isinstance(result, (int, float)):
            self.scroll_posicao = result
            
    @QtCore.Slot()
    def _restaurar_scroll_preview(self):
        # --- INÍCIO DA CORREÇÃO (Re-aplicar Zoom após carregar HTML) ---
        # Garante que o zoom correto seja aplicado toda vez que o HTML é recarregado.
        
        # Apenas executa a lógica de zoom se estivermos no modo lado-a-lado
        if self.modo_preview == "lado_a_lado" and isinstance(self.main_content_widget, QSplitter):
            splitter = self.main_content_widget
            sizes = splitter.sizes()
            
            if len(sizes) == 2 and sum(sizes) > 0 and self.NEUTRAL_PREVIEW_RATIO > 0:
                total_width = sum(sizes)
                current_preview_width = sizes[1]
                
                if current_preview_width > 0:
                    current_ratio = current_preview_width / total_width
                    ratio_change = current_ratio / self.NEUTRAL_PREVIEW_RATIO
                    new_zoom = self.BASE_ZOOM_FACTOR * ratio_change
                    new_zoom = max(0.2, min(new_zoom, 3.0)) 
                    self.preview_display.setZoomFactor(new_zoom)
        # --- FIM DA CORREÇÃO ---
        
        # Restaura a posição do scroll (como antes)
        self.preview_display.page().runJavaScript(f"window.scrollTo(0, {self.scroll_posicao});")
    
    @QtCore.Slot(str)
    def _navegar_preview_para_ancora(self, id_ancora: str):
        if not id_ancora:
            return
            
        if self.modo_preview == "aba":
            index_preview = self.tabs.indexOf(self.preview_container)
            if index_preview != -1:
                self.tabs.setCurrentIndex(index_preview)
        
        js_code = f"""
        var element = document.getElementById('{id_ancora}');
        if (element) {{
            element.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
        }}
        """
        self.preview_display.page().runJavaScript(js_code)

    # --- INÍCIO: Método _atualizar_preview (Refatorado para Thread) ---
    @QtCore.Slot()
    def _atualizar_preview(self):
        """
        Verifica a fila e despacha a geração da preview para uma thread
        separada, evitando travamento da UI.
        """
        # Se o worker estiver ocupado, apenas marque que queremos uma atualização
        # e saia. O worker chamará esta função quando terminar.
        if self.is_preview_worker_busy:
            self.pending_preview_update = True
            print("Preview worker ocupado. Adicionando à fila.")
            return

        # Se o worker estiver livre, inicie o trabalho.
        print("Iniciando atualização da preview em segundo plano...")
        self.is_preview_worker_busy = True
        self.pending_preview_update = False

        # 1. Salva o scroll (na thread principal)
        if self.modo_preview == "lado_a_lado":
            self._salvar_scroll_preview()
        
        # 2. Sincroniza os dados (na thread principal)
        # Garante que o documento tenha os dados mais recentes do editor e da UI
        self.aba_conteudo.sincronizar_conteudo_pendente()
        self._sincronizar_modelo_com_ui()
        
        # 3. Cria uma cópia segura dos dados para a thread
        try:
            # Deepcopy é essencial para evitar que a thread acesse
            # o mesmo objeto que a UI está modificando.
            documento_copia = copy.deepcopy(self.documento)
        except Exception as e:
            print(f"Erro ao copiar documento para a thread: {e}")
            self.is_preview_worker_busy = False # Libera a trava se a cópia falhar
            return

        # 4. Envia a cópia para a thread de trabalho emitindo o sinal
        self.request_preview_update.emit(documento_copia)
    # --- FIM: Método _atualizar_preview ---


    # --- INÍCIO: Novo Slot para receber o resultado da Thread ---
    @QtCore.Slot(str)
    def _apply_html_to_preview(self, html_content):
        """
        Chamado pela thread do worker quando o HTML está pronto.
        Este método roda na thread principal e atualiza a UI.
        """
        print("Preview HTML recebido da thread. Atualizando UI.")
        
        # Se o conteúdo for vazio, o worker provavelmente falhou
        if not html_content:
            print("Worker retornou HTML vazio (provável erro na geração).")
            # Libera a trava, mas não verifica se há atualização pendente
            # para evitar um loop de falhas.
            self.is_preview_worker_busy = False
            return

        # 1. Limpa a busca e define o HTML
        self.preview_display.findText("")
        base_url = QtCore.QUrl.fromLocalFile(os.path.abspath(os.path.dirname(__file__)))
        self.preview_display.setHtml(html_content, baseUrl=base_url)
        
        # self._restaurar_scroll_preview() já é chamado automaticamente 
        # pelo sinal 'loadFinished' do QWebEngineView.

        # 2. Mostra a mensagem (se estiver no modo aba)
        if self.modo_preview == "aba":
            QMessageBox.information(self, "Atualizado", "A pré-visualização foi atualizada com sucesso.")
        
        # 3. Lógica da Fila: Verifica se uma nova atualização foi solicitada
        #    enquanto esta estava sendo gerada.
        if self.pending_preview_update:
            print("Atualização pendente detectada. Reiniciando o worker...")
            # Limpa as flags e chama _atualizar_preview imediatamente
            # para processar a versão mais recente dos dados.
            self.pending_preview_update = False
            self.is_preview_worker_busy = False
            self._atualizar_preview() # Dispara a atualização pendente
        else:
            # Se não houver nada pendente, o worker está livre.
            self.is_preview_worker_busy = False
            print("Worker da preview está ocioso.")
    # --- FIM: Novo Slot ---


    def _marcar_modificado(self):
        if self._populando_ui:
            return
        if not self.modificado:
            self.modificado = True
            self.setWindowTitle(self.windowTitle() + '*')
        if self.config['recovery']['autosave_enabled']:
            if not self.autosave_timer.isActive():
                intervalo_min = self.config['recovery']['autosave_periodic_interval_min']
                print(f"Primeira modificação detectada. Iniciando auto-save periódico a cada {intervalo_min} minutos.")
                self.autosave_timer.start()
        self._disparar_atualizacao_automatica()

    def closeEvent(self, event):
        if self._verificar_alteracoes_nao_salvas():
            if self.caminho_projeto_atual or self.modificado:
                 gerenciador_recuperacao.limpar_recuperacao(self.caminho_projeto_atual)
            self.gerenciador_projeto.fechar_projeto()
            
            # --- INÍCIO: Limpeza da Thread de Preview ---
            print("Encerrando thread da preview...")
            self.preview_thread.quit()
            # Espera até 3 segundos pela thread encerrar
            if not self.preview_thread.wait(3000): 
                print("Thread da preview não encerrou, forçando término.")
                self.preview_thread.terminate()
            # --- FIM: Limpeza da Thread de Preview ---
            
            event.accept()
        else:
            event.ignore()

    @QtCore.Slot(bool)
    def _novo_projeto(self, primeira_execucao=False):
        if not primeira_execucao and not self._verificar_alteracoes_nao_salvas():
            return
        modelo_padrao = get_nomes_modelos()[0]
        self.iniciar_novo_projeto_com_modelo(modelo_padrao)

    @QtCore.Slot(str)
    def _on_template_selecionado(self, nome_modelo):
        if self._populando_ui or not nome_modelo or nome_modelo == self.documento.configuracoes.tipo_trabalho:
            return
        resposta = QMessageBox.question(self, "Mudar Modelo de Trabalho",
                                        f"Mudar o modelo para '{nome_modelo}' irá reorganizar sua estrutura de capítulos.\n"
                                        "Capítulos existentes serão preservados...\nDeseja continuar?",
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resposta == QMessageBox.StandardButton.No:
            self._populando_ui = True
            self.cfg_tipo.setCurrentText(self.documento.configuracoes.tipo_trabalho)
            self._populando_ui = False
            return
        mapa_capitulos_atuais = {c.titulo.upper().strip(): c for c in self.documento.estrutura_textual.filhos}
        titulos_novos = get_estrutura_por_nome(nome_modelo)
        nova_lista_de_capitulos = [mapa_capitulos_atuais.pop(t.upper().strip(), Capitulo(titulo=t, is_template_item=True)) for t in titulos_novos]
        capitulos_orfaos = [c for c in mapa_capitulos_atuais.values() if c.conteudo.strip() or c.filhos]
        if capitulos_orfaos:
            for c in capitulos_orfaos:
                c.is_template_item = False
            nova_lista_de_capitulos.extend(capitulos_orfaos)
            QMessageBox.information(self, "Capítulos Preservados", "Capítulos com conteúdo que não pertencem ao novo modelo foram movidos para o final.")
        self.documento.estrutura_textual.filhos = nova_lista_de_capitulos
        for filho in self.documento.estrutura_textual.filhos:
            filho.pai = self.documento.estrutura_textual
        self.aba_conteudo._popular_arvore()
        self.documento.configuracoes.tipo_trabalho = nome_modelo
        self._marcar_modificado()

    def _salvar_projeto(self):
        if not self.caminho_projeto_atual:
            self._salvar_projeto_como()
            return
        if self.config['backup']['backup_on_save_enabled']:
            gerenciador_recuperacao.criar_backup(self.caminho_projeto_atual, self.config['backup']['max_backups_per_project'])
        self.aba_conteudo.sincronizar_conteudo_pendente()
        self._sincronizar_modelo_com_ui()
        try:
            self.gerenciador_projeto.salvar_projeto(self.documento, self.caminho_projeto_atual)
            self.modificado = False
            self.setWindowTitle(f'Formatheus - {os.path.basename(self.caminho_projeto_atual)}')
            QMessageBox.information(self, "Sucesso", "Projeto salvo com sucesso!")
            print("Trabalho salvo manualmente. Timer de recuperação pausado.")
            self.autosave_timer.stop()
            gerenciador_recuperacao.limpar_recuperacao(self.caminho_projeto_atual)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar", f"Não foi possível salvar o projeto:\n{e}")

    def _salvar_projeto_como(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Salvar Projeto Como...", "", "Arquivo ABNF (*.abnf)")
        if caminho:
            self.caminho_projeto_atual = caminho
            self._salvar_projeto()

    def _carregar_projeto(self):
        if self._verificar_alteracoes_nao_salvas():
            caminho, _ = QFileDialog.getOpenFileName(self, "Carregar Projeto", "", "Arquivo ABNF (*.abnf)")
            if caminho:
                self.carregar_projeto_pelo_caminho(caminho)

    def _popular_ui_com_documento(self):
        self._populando_ui = True
        cfg = self.documento.configuracoes
        
        self.cfg_tipo.setCurrentText(cfg.tipo_trabalho)
        self.cfg_instituicao.setText(cfg.instituicao)
        self.cfg_curso.setText(cfg.curso)
        self.cfg_modalidade_curso.setText(cfg.modalidade_curso)
        self.cfg_titulo_pretendido.setText(cfg.titulo_pretendido)
        self.cfg_cidade.setText(cfg.cidade)
        self.cfg_ano.setText(str(cfg.ano))

        self.cfg_posicao_brasao.setCurrentText(cfg.posicao_brasao)
        self.cfg_brasao_esquerdo_path.setText(cfg.caminho_brasao_esquerdo_original)
        self.cfg_brasao_direito_path.setText(cfg.caminho_brasao_direito_original)
        self._atualizar_visibilidade_brasao(cfg.posicao_brasao)

        self.titulo_input.setText(self.documento.titulo)
        self.autores_input.setPlainText('\n'.join([a.nome_completo for a in self.documento.autores]))
        self.orientador_input.setText(self.documento.orientador)
        self.resumo_input.setPlainText(self.documento.resumo)
        self.keywords_input.setText(self.documento.palavras_chave)
        
        self.aba_conteudo.documento = self.documento
        self.aba_conteudo._popular_arvore()
        self.aba_conteudo.atualizar_bancos_visuais()
        if self.aba_conteudo.arvore_capitulos.topLevelItemCount() > 0:
            self.aba_conteudo.arvore_capitulos.setCurrentItem(self.aba_conteudo.arvore_capitulos.topLevelItem(0))
        
        self.lista_referencias.clear()
        for ref in self.documento.referencias:
            self.lista_referencias.addItem(ref.formatar().replace('**', ''))
            
        self._populando_ui = False
        self._disparar_atualizacao_automatica()

    def _verificar_alteracoes_nao_salvas(self) -> bool:
        if not self.modificado:
            return True
        resposta = QMessageBox.question(self, "Salvar Alterações?",
                                        "Você tem alterações não salvas. Deseja salvá-las?",
                                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if resposta == QMessageBox.StandardButton.Cancel:
            return False
        if resposta == QMessageBox.StandardButton.Save:
            self._salvar_projeto()
        return True

    @QtCore.Slot()
    def _on_editor_modificado(self):
        if not self.aba_conteudo._carregando_capitulo:
            self._marcar_modificado()

    def _conectar_sinais_modificacao(self):
        self.cfg_tipo.currentTextChanged.connect(self._marcar_modificado)
        self.cfg_instituicao.textChanged.connect(self._marcar_modificado)
        self.cfg_curso.textChanged.connect(self._marcar_modificado)
        self.cfg_modalidade_curso.textChanged.connect(self._marcar_modificado)
        self.cfg_titulo_pretendido.textChanged.connect(self._marcar_modificado)
        self.cfg_cidade.textChanged.connect(self._marcar_modificado)
        self.cfg_ano.textChanged.connect(self._marcar_modificado)
        
        self.cfg_posicao_brasao.currentTextChanged.connect(self._marcar_modificado)

        self.titulo_input.textChanged.connect(self._marcar_modificado)
        self.autores_input.textChanged.connect(self._marcar_modificado)
        self.orientador_input.textChanged.connect(self._marcar_modificado)
        self.resumo_input.textChanged.connect(self._marcar_modificado)
        self.keywords_input.textChanged.connect(self._marcar_modificado)

        self.aba_conteudo.editor_capitulo.textChanged.connect(self._on_editor_modificado)
        
        self.aba_conteudo.arvore_capitulos.estruturaAlterada.connect(self._marcar_modificado)
        self.aba_conteudo.arvore_capitulos.itemChanged.connect(self._marcar_modificado)

    @QtCore.Slot()
    def _adicionar_referencia(self):
        dialog = ReferenciaDialog(parent=self)
        if dialog.exec():
            nova_ref = dialog.get_data()
            if nova_ref:
                self.documento.referencias.append(nova_ref)
                self.lista_referencias.addItem(nova_ref.formatar().replace('**', ''))
                self._marcar_modificado()

    @QtCore.Slot()
    def _editar_referencia(self):
        linha = self.lista_referencias.currentRow()
        if linha == -1:
            QMessageBox.warning(self, "Atenção", "Nenhuma referência selecionada para editar.")
            return
        ref_para_editar = self.documento.referencias[linha]
        dialog = ReferenciaDialog(ref=ref_para_editar, parent=self)
        if dialog.exec():
            ref_atualizada = dialog.get_data()
            if ref_atualizada:
                self.documento.referencias[linha] = ref_atualizada
                self.lista_referencias.item(linha).setText(ref_atualizada.formatar().replace('**', ''))
                self._marcar_modificado()

    @QtCore.Slot()
    def _remover_referencia(self):
        linha = self.lista_referencias.currentRow()
        if linha == -1: return
        if QMessageBox.question(self, "Confirmar", "Remover esta referência?") == QMessageBox.StandardButton.Yes:
            self.lista_referencias.takeItem(linha)
            del self.documento.referencias[linha]
            self._marcar_modificado()

    def _sincronizar_modelo_com_ui(self):
        cfg = self.documento.configuracoes
        cfg.tipo_trabalho = self.cfg_tipo.currentText()
        cfg.instituicao = self.cfg_instituicao.text()
        cfg.curso = self.cfg_curso.text()
        cfg.modalidade_curso = self.cfg_modalidade_curso.text()
        cfg.titulo_pretendido = self.cfg_titulo_pretendido.text()
        cfg.cidade = self.cfg_cidade.text()
        cfg.ano = int(self.cfg_ano.text() or datetime.now().year)
        cfg.posicao_brasao = self.cfg_posicao_brasao.currentText()
        self.documento.titulo = self.titulo_input.text()
        self.documento.autores = [Autor(n.strip()) for n in self.autores_input.toPlainText().splitlines() if n.strip()]
        self.documento.orientador = self.orientador_input.text()
        self.documento.resumo = self.resumo_input.toPlainText()
        self.documento.palavras_chave = self.keywords_input.text()

    def _gerar_documento_final(self):
        self.aba_conteudo.sincronizar_conteudo_pendente()
        self._sincronizar_modelo_com_ui()
        if not self.documento.titulo or not self.documento.autores:
            QMessageBox.warning(self, "Erro", "Título e Autores são campos obrigatórios.")
            return
        
        titulo_projeto = self.documento.titulo
        if titulo_projeto:
            nome_sanitizado = re.sub(r'[<>:"/\\|?*]', '', titulo_projeto)
            nome_sanitizado = nome_sanitizado[:60].strip()
        else:
            nome_sanitizado = ""

        if not nome_sanitizado:
            nome_sanitizado = "trabalho_abnt"
            
        nome_arquivo_sugerido = f"{nome_sanitizado}.docx"
        
        diretorio_sugerido = "" 
        
        if self.caminho_projeto_atual:
            diretorio_sugerido = os.path.dirname(self.caminho_projeto_atual)
            
        caminho_sugerido_completo = os.path.join(diretorio_sugerido, nome_arquivo_sugerido)
        
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar Documento", 
                                                 caminho_sugerido_completo, 
                                                 "Word Documents (*.docx)")
        
        if not filename: return
        try:
            gerador = GeradorDOCX(self.documento)
            gerador.gerar_documento(filename)
            QMessageBox.information(self, "Sucesso", f"Documento .docx gerado com sucesso em:\n{filename}")
        except Exception as e:
            QMessageBox.critical(self, "Erro na Geração", f"Ocorreu um erro: {e}")

    @QtCore.Slot()
    def _auto_salvar_recuperacao(self):
        if not self.modificado: return
        print(f"[{datetime.now():%H:%M:%S}] TIMER PERIÓDICO DISPARADO! Executando auto-save...")
        self.aba_conteudo.sincronizar_conteudo_pendente()
        self._sincronizar_modelo_com_ui()
        gerenciador_recuperacao.salvar_recuperacao(self.gerenciador_projeto, self.documento, self.caminho_projeto_atual)

    def carregar_projeto_pelo_caminho(self, caminho, is_recovery=False):
        if not is_recovery and not self._verificar_alteracoes_nao_salvas():
            self.close()
            return
        try:
            self.documento = self.gerenciador_projeto.carregar_projeto(caminho)
            self._popular_ui_com_documento()
            if is_recovery:
                self.caminho_projeto_atual = None
                self.modificado = True
                self.setWindowTitle(f'Formatheus - ARQUIVO RECUPERADO*')
                QMessageBox.information(self, "Arquivo Recuperado", "O arquivo foi recuperado com sucesso.\nUse 'Salvar Como...' para salvá-lo em um local permanente.")
                gerenciador_recuperacao.limpar_recuperacao_pelo_caminho_direto(caminho)
                self._marcar_modificado()
            else:
                self.caminho_projeto_atual = caminho
                self.modificado = False
                self.setWindowTitle(f'Formatheus - {os.path.basename(caminho)}')
                gerenciador_config.add_projeto_recente(caminho)
                gerenciador_recuperacao.limpar_recuperacao(caminho)
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Carregar", f"Não foi possível carregar o projeto:\n{e}")
            self.gerenciador_projeto.fechar_projeto()

    def iniciar_novo_projeto_com_modelo(self, nome_modelo):
        if not self._verificar_alteracoes_nao_salvas(): return
        
        gerenciador_recuperacao.limpar_recuperacao(self.caminho_projeto_atual)
        if self.autosave_timer.isActive(): self.autosave_timer.stop()
        
        self.documento = DocumentoABNT()
        
        estrutura_data_list = get_estrutura_por_nome(nome_modelo)
        
        for capitulo_data in estrutura_data_list:
            novo_capitulo = Capitulo.from_dict(capitulo_data) 
            self.documento.estrutura_textual.adicionar_filho(novo_capitulo)

        self.caminho_projeto_atual = None
        self.gerenciador_projeto.fechar_projeto()
        
        if hasattr(self, 'cfg_tipo'):
            self._popular_ui_com_documento()
            self._populando_ui = True
            self.cfg_tipo.setCurrentText(nome_modelo)
            self.documento.configuracoes.tipo_trabalho = nome_modelo
            self._populando_ui = False
            
        self.modificado = False
        self.setWindowTitle(f'Formatheus - Novo Projeto ({nome_modelo})')
        self._disparar_atualizacao_automatica()


if __name__ == '__main__':
    try:
        from PySide6.QtWebEngineWidgets import QWebEngineView
    except ImportError:
        print("ERRO: A dependência 'PySide6-WebEngineWidgets' não está instalada.")
        print("Por favor, execute: pip install PySide6-WebEngineWidgets")
        sys.exit(1)

    app = QApplication(sys.argv)
    
    config = gerenciador_config.carregar_config()
    initial_theme = config.get('ui_settings', {}).get('theme', 'light') # Padrão 'light'
    
    if HAS_THEME_LIB:
        app_style = qdarktheme.load_stylesheet(initial_theme) # Usa o tema salvo
        app_style += stylesheet.get_style_sheet()
        app.setStyleSheet(app_style)
    else:
        app.setStyleSheet(stylesheet.get_style_sheet())
    
    while True:
        gerenciador_recuperacao.setup_diretorios()
        
        acao_inicial = None
        dados_iniciais = None

        arquivos_recuperaveis = gerenciador_recuperacao.verificar_arquivos_recuperaveis()
        if arquivos_recuperaveis:
            dialog = DialogoRecuperacao(arquivos_recuperaveis)
            if dialog.exec():
                if dialog.arquivos_para_recuperar:
                    acao_inicial = 'recuperar'
                    dados_iniciais = dialog.arquivos_para_recuperar
                
                for arq_info in dialog.arquivos_para_descartar:
                    gerenciador_recuperacao.limpar_recuperacao_pelo_caminho_direto(arq_info['recovery_file_path'])

        if not acao_inicial:
            # --- INÍCIO DA MODIFICAÇÃO ---
            # Verifica qual é o tema inicial carregado
            is_dark_inicial = (initial_theme == "dark")
            # Passa a informação do tema para a TelaInicial
            tela_inicial = TelaInicial(is_dark=is_dark_inicial)
            # --- FIM DA MODIFICAÇÃO ---
            
            if tela_inicial.exec():
                # --- CORREÇÃO: Esta linha estava faltando ---
                acao_inicial, dados_iniciais = tela_inicial.get_resultado()

        if not acao_inicial:
            break

        if acao_inicial == 'recuperar':
            arquivos_para_recuperar = dados_iniciais
            primeiro_para_abrir = arquivos_para_recuperar.pop(0)
            caminho_primeiro = primeiro_para_abrir['recovery_file_path']
            
            outros_recuperados = []
            if arquivos_para_recuperar:
                desktop = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
                for arq_info in arquivos_para_recuperar:
                    nome_original = arq_info.get('original_name', 'arquivo_recuperado').replace('.abnf', '')
                    caminho_seguro = os.path.join(desktop, f"[RECUPERADO] {nome_original}.abnf")
                    contador = 1
                    while os.path.exists(caminho_seguro):
                        caminho_seguro = os.path.join(desktop, f"[RECUPERADO] {nome_original}_{contador}.abnf")
                        contador += 1
                    try:
                        shutil.copy2(arq_info['recovery_file_path'], caminho_seguro)
                        outros_recuperados.append(os.path.basename(caminho_seguro))
                    except Exception as e:
                        print(f"Erro ao salvar arquivo recuperado na área de trabalho: {e}")
                    gerenciador_recuperacao.limpar_recuperacao_pelo_caminho_direto(arq_info['recovery_file_path'])
            
            acao_inicial = 'abrir_recuperado'
            dados_iniciais = caminho_primeiro
            
            if outros_recuperados:
                msg = (f"O projeto '{primeiro_para_abrir.get('original_name')}' foi aberto para edição.\n\n"
                       "Os seguintes projetos recuperados foram salvos na sua Área de Trabalho:\n- " +
                       "\n- ".join(outros_recuperados))
                QMessageBox.information(None, "Projetos Recuperados", msg)

        win = ABNTHelperApp()

        if acao_inicial == 'novo':
            win.iniciar_novo_projeto_com_modelo(dados_iniciais)
        elif acao_inicial == 'abrir':
            win.carregar_projeto_pelo_caminho(dados_iniciais)
        elif acao_inicial == 'abrir_recuperado':
            win.carregar_projeto_pelo_caminho(dados_iniciais, is_recovery=True)

        win.showMaximized()
        app.exec()

        if not win.wants_to_restart:
            break
            
    sys.exit(0)