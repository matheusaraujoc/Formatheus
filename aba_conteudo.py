# aba_conteudo.py
# Descrição: Versão com layout de 3 painéis (Árvore | Editor | Bancos)
#
# ATUALIZAÇÃO (v53 - Correção de Typo):
# 1. Corrigido typo de 'QAbstractaItemView' para
#    'QAbstractItemView' na classe ArvoreConteudo.
# 2. Mantém a lógica de validação de bins (v52) e
#    numeração (v51).
#

import re
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QWidget, QLabel, QTextEdit, QPushButton, QListWidget, QCheckBox,
                               QVBoxLayout, QHBoxLayout, QMessageBox, QTreeWidget,
                               QTreeWidgetItem, QInputDialog, QAbstractItemView, QLineEdit, QTabWidget,
                               QSplitter, QToolButton, QMenu, QStyle,
                               QGridLayout)
from PySide6.QtGui import (QSyntaxHighlighter, QTextCharFormat, QColor, 
                           QFont)
from PySide6.QtCore import Qt

from documento import (Capitulo, Tabela, Figura, Formula, ListaABNT, 
                       Grafico)
from dialogo_tabela import TabelaDialog
from dialogo_figura import DialogoFigura
from dialogo_formula import DialogoFormula
from dialogo_lista import ListaDialog
from dialogo_chart import ChartDialog
import os

# --- CLASSE SYNTAX HIGHLIGHTER PARA MARCADORES ---

class MarcadorHighlighter(QSyntaxHighlighter):
    """
    Realça a sintaxe dos marcadores {{...}} dentro do QTextEdit.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlight_rules = []
        
        self.marker_regex = re.compile(
            r"(\{\{(Tabela|Figura|Grafico|Formula|Lista):([^}]+)\}\})|"
            r"(\{\{(QUEBRA_PAGINA|PAGINA_EM_BRANCO)\}\})"
        )

        self.formats = {}
        base_colors = {
            "Tabela": "#0078d4", "Figura": "#008a00", "Grafico": "#8a008a",
            "Formula": "#d13438", "Lista": "#b45f06", "QUEBRA_PAGINA": "#a0a0a0",
            "PAGINA_EM_BRANCO": "#a0a0a0",
        }

        for tipo, cor_hex in base_colors.items():
            format = QTextCharFormat()
            format.setForeground(QColor(cor_hex))
            format.setFontWeight(QFont.Weight.Bold)
            
            # A linha abaixo foi comentada para remover o fundo cinza
            # format.setBackground(QColor("#f0f0f0")) 
            
            self.formats[tipo] = format

    def highlightBlock(self, text):
        """Aplica a formatação ao bloco de texto atual."""
        for match in self.marker_regex.finditer(text):
            if match.group(1): # É um marcador de ativo (ex: {{Figura:Nome}})
                tipo = match.group(2) # O tipo (Figura)
                if tipo in self.formats:
                    self.setFormat(match.start(1), match.end(1) - match.start(1), self.formats[tipo])
            
            elif match.group(4): # É um marcador de comando (ex: {{QUEBRA_PAGINA}})
                tipo = match.group(5) # O tipo (QUEBRA_PAGINA)
                if tipo in self.formats:
                    self.setFormat(match.start(4), match.end(4) - match.start(4), self.formats[tipo])
                    
# --- CLASSE EDITOR DE CONTEÚDO ---
class EditorConteudo(QTextEdit):
    """
    QTextEdit modificado para criar o menu de contexto padrão,
    adicionar as ações customizadas de inserção e exibi-lo.
    """
    def __init__(self, aba_conteudo_parent, parent=None):
        super().__init__(parent)
        self.aba_conteudo_parent = aba_conteudo_parent # Referência ao AbaConteudo
    
    def contextMenuEvent(self, event: QtGui.QContextMenuEvent) -> None:
        menu = self.createStandardContextMenu()
        self.aba_conteudo_parent._adicionar_acoes_menu_contexto(menu)
        menu.exec(event.globalPos())

# --- CLASSE ARVORE CONTEUDO (Capítulos) ---
class ArvoreConteudo(QTreeWidget):
    estruturaAlterada = QtCore.Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        # --- CORREÇÃO (v53) ---
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        # --- FIM DA CORREÇÃO ---
        self.setDropIndicatorShown(True)
        
    def dropEvent(self, event: QtGui.QDropEvent):
        if self.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove:
            super().dropEvent(event)
            self.estruturaAlterada.emit()
        else:
            event.ignore()

# --- CLASSE BinTreeWidget (Bancos de Ativos) ---
class BinTreeWidget(QTreeWidget):
    """
    Subclasse de QTreeWidget que gerencia o drag-and-drop de
    ativos (filhos) para dentro de "bins" (pastas/pais).
    """
    assetBinChanged = QtCore.Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True) # Bins não precisam de cabeçalho
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDropIndicatorShown(True)
        self.setAcceptDrops(True)

    def dropEvent(self, event: QtGui.QDropEvent):
        """
        Sobrescreve o dropEvent para atualizar o 'bin_name' do ativo.
        """
        item_arrastado = self.currentItem()
        if not item_arrastado or not item_arrastado.parent():
            event.ignore()
            return

        asset = item_arrastado.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not asset:
            event.ignore()
            return

        item_alvo = self.itemAt(event.position().toPoint())
        
        novo_bin_name = None
        item_bin_alvo = None

        if item_alvo is None:
            # Soltou em espaço vazio, move para o bin "(Padrão)"
            item_bin_alvo = self.findItems("(Padrão)", Qt.MatchFlag.MatchExactly)[0]
        elif item_alvo.parent() is None:
            # Soltou em um bin (item top-level)
            item_bin_alvo = item_alvo
        else:
            # Soltou em outro ativo (item filho)
            item_bin_alvo = item_alvo.parent()

        if not item_bin_alvo:
            event.ignore()
            return
            
        nome_bin_alvo = item_bin_alvo.text(0)

        # Atualiza o modelo de dados
        if nome_bin_alvo == "(Padrão)":
            asset.bin_name = None
        else:
            asset.bin_name = nome_bin_alvo

        self.assetBinChanged.emit()
        event.accept()

# --- CLASSE ABA CONTEUDO ---
class AbaConteudo(QWidget):
    topicoSelecionadoParaNavegacao = QtCore.Signal(str)

    def __init__(self, documento, parent=None):
        super().__init__(parent)
        self.documento = documento
        self._carregando_capitulo = False
        
        # --- INÍCIO DA MODIFICAÇÃO (Inline Bin-Editing) ---
        # Roles customizadas para rastrear a edição de bins
        # UserRole + 10: Flag para marcar se um bin é recém-criado
        self.IS_NEW_BIN_ROLE = QtCore.Qt.ItemDataRole.UserRole + 10 
        # UserRole + 11: Armazena o nome "antigo" antes da edição começar
        self.OLD_NAME_ROLE = QtCore.Qt.ItemDataRole.UserRole + 11
        
        # Mapa para ligar as árvores de bin aos seus modelos de dados
        self.bin_tree_map = {}
        # (Este mapa será populado em _build_ui após as árvores serem criadas)
        # --- FIM DA MODIFICAÇÃO ---
        
        # Fontes especiais para bins
        self.bin_font = QFont()
        self.bin_font.setBold(True)
        self.default_bin_font = QFont()
        self.default_bin_font.setItalic(True)
        self.default_bin_brush = QColor("gray")

        self._build_ui()
        self._apply_styles()

    def _apply_styles(self):
        """Aplica estilos CSS para os QToolButton da barra de formatação."""
        style = """
        QToolButton {
            border: 1px solid transparent; 
            padding: 5px;
            background-color: transparent;
            min-width: 32px; 
            min-height: 32px; 
            border-radius: 4px; 
        }
        QToolButton:hover {
            background-color: #e0e0e0; 
            border: 1px solid #c0c0c0; 
        }
        QToolButton:pressed {
            background-color: #d0d0d0; 
            border: 1px solid #a0a0a0;
        }
        QToolButton:disabled {
            opacity: 0.6; 
        }
        """
        self.setStyleSheet(style)

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10) 
        
        # --- PAINEL ESQUERDO (Splitter Vertical) ---
        
        left_splitter = QSplitter(QtCore.Qt.Orientation.Vertical)
        left_splitter.setMaximumWidth(350)

        # --- INÍCIO DA MODIFICAÇÃO (v48) ---
        # Adiciona estilo para a alça (handle) do splitter
        left_splitter.setStyleSheet("""
            QSplitter::handle:vertical {
                background-color: #dcdcdc; /* Cor da borda */
                height: 1px; /* Altura da barra */
                border-top: 1px solid #c0c0c0;
                border-bottom: 1px solid #c0c0c0;
            }
            QSplitter::handle:vertical:hover {
                background-color: #0078d4; /* Cor primária */
            }
        """)
        # --- FIM DA MODIFICAÇÃO (v48) ---


        # --- 1. PAINEL DO TOPO-ESQUERDO (Árvore de Capítulos) ---
        top_left_widget = QWidget()
        left_layout = QVBoxLayout(top_left_widget)
        
        label_estrutura = QLabel("Estrutura do Documento")
        label_estrutura.setProperty("cssClass", "titulo")
        left_layout.addWidget(label_estrutura)
        
        self.busca_arvore_input = QLineEdit()
        self.busca_arvore_input.setPlaceholderText("Filtrar tópicos e conteúdos...")
        self.busca_arvore_input.textChanged.connect(self._filtrar_arvore)
        left_layout.addWidget(self.busca_arvore_input)
        
        self.chk_reorganizar = QCheckBox("Habilitar Reorganização (Arrastar e Soltar)")
        self.chk_reorganizar.stateChanged.connect(self._alternar_modo_arrastar)
        left_layout.addWidget(self.chk_reorganizar)

        self.arvore_capitulos = ArvoreConteudo()
        self.arvore_capitulos.setHeaderLabel("Tópicos")
        self.arvore_capitulos.estruturaAlterada.connect(self._sincronizar_modelo_com_arvore)
        self.arvore_capitulos.currentItemChanged.connect(self._on_capitulo_selecionado_changed)
        self.arvore_capitulos.itemChanged.connect(self._renomear_capitulo)
        
        left_layout.addWidget(self.arvore_capitulos)

        btn_layout = QHBoxLayout()
        btn_add_topico = QPushButton("Novo Tópico")
        btn_add_sub = QPushButton("Novo Subtópico")
        btn_del = QPushButton("Remover")
        
        btn_del.setProperty("cssClass", "destructive")
        
        btn_layout.addWidget(btn_add_topico)
        btn_layout.addWidget(btn_add_sub)
        btn_layout.addWidget(btn_del)
        btn_add_topico.clicked.connect(self._adicionar_topico_principal)
        btn_add_sub.clicked.connect(self._adicionar_subtopico)
        btn_del.clicked.connect(self._remover_topico)
        left_layout.addLayout(btn_layout)
        
        left_splitter.addWidget(top_left_widget) 
        
        # --- 2. PAINEL DA BASE-ESQUERDA (Bancos de Ativos) ---
        
        self.arvore_tabelas = BinTreeWidget()
        self.arvore_figuras = BinTreeWidget()
        self.arvore_graficos = BinTreeWidget()
        self.arvore_formulas = BinTreeWidget()
        self.arvore_listas = BinTreeWidget()
        
        self.arvore_tabelas.assetBinChanged.connect(self.atualizar_bancos_visuais)
        self.arvore_figuras.assetBinChanged.connect(self.atualizar_bancos_visuais)
        self.arvore_graficos.assetBinChanged.connect(self.atualizar_bancos_visuais)
        self.arvore_formulas.assetBinChanged.connect(self.atualizar_bancos_visuais)
        self.arvore_listas.assetBinChanged.connect(self.atualizar_bancos_visuais)

        self.bancos_tabs = QTabWidget()
        
        self.bancos_tabs.setObjectName("BancosAbas")
        self.bancos_tabs.setStyleSheet("""
            QTabWidget#BancosAbas QTabBar::tab {
                font-size: 12px;
                padding: 6px 8px;
            }
        """)

        # --- INÍCIO DA MODIFICAÇÃO (v47) ---
        # Função auxiliar local para criar o layout do título do bin
        def _criar_layout_titulo_bin(titulo: str, add_slot, del_slot) -> QHBoxLayout:
            titulo_layout = QHBoxLayout()
            titulo_layout.addWidget(QLabel(titulo))
            titulo_layout.addStretch()
            
            btn_add_bin = QToolButton()
            btn_add_bin.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
            btn_add_bin.setToolTip("Criar novo bin (pasta)")
            btn_add_bin.clicked.connect(add_slot)
            titulo_layout.addWidget(btn_add_bin)
            
            btn_del_bin = QToolButton()
            btn_del_bin.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
            btn_del_bin.setToolTip("Remover bin selecionado")
            btn_del_bin.setProperty("cssClass", "destructive") # Para estilo
            btn_del_bin.clicked.connect(del_slot)
            titulo_layout.addWidget(btn_del_bin)
            return titulo_layout
        # --- FIM DA MODIFICAÇÃO (v47) ---


        # --- Aba Tabelas ---
        tabelas_widget = QWidget()
        tabelas_v_layout = QVBoxLayout(tabelas_widget)
        tabelas_titulo_layout = _criar_layout_titulo_bin(
            "Banco de Tabelas:",
            lambda: self._adicionar_bin(self.arvore_tabelas, "tabelas"),
            lambda: self._remover_bin(self.arvore_tabelas, "tabelas", self.documento.banco_tabelas)
        )
        tabelas_v_layout.addLayout(tabelas_titulo_layout)
        self.filtro_tabelas_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_tabelas_check.stateChanged.connect(self.atualizar_bancos_visuais)
        tabelas_v_layout.addWidget(self.filtro_tabelas_check)
        tabelas_v_layout.addWidget(self.arvore_tabelas) 
        
        tabelas_btn_layout = QHBoxLayout()
        btn_add_tabela = QPushButton("Criar")
        btn_edit_tabela = QPushButton("Editar")
        btn_del_tabela = QPushButton("Remover")
        btn_edit_tabela.setProperty("cssClass", "utility")
        btn_del_tabela.setProperty("cssClass", "destructive")
        tabelas_btn_layout.addWidget(btn_add_tabela)
        tabelas_btn_layout.addWidget(btn_edit_tabela)
        tabelas_btn_layout.addWidget(btn_del_tabela)
        tabelas_v_layout.addLayout(tabelas_btn_layout)
        
        btn_ins_tabela = QPushButton("Inserir no Texto")
        tabelas_v_layout.addWidget(btn_ins_tabela)
        
        btn_add_tabela.clicked.connect(self._adicionar_tabela)
        btn_edit_tabela.clicked.connect(self._editar_tabela)
        btn_del_tabela.clicked.connect(self._remover_tabela)
        btn_ins_tabela.clicked.connect(lambda: self._inserir_marcador_selecionado(self.arvore_tabelas, "Tabela"))
        
        # --- Aba Figuras ---
        figuras_widget = QWidget()
        figuras_v_layout = QVBoxLayout(figuras_widget)
        figuras_titulo_layout = _criar_layout_titulo_bin(
            "Banco de Figuras:",
            lambda: self._adicionar_bin(self.arvore_figuras, "figuras"),
            lambda: self._remover_bin(self.arvore_figuras, "figuras", self.documento.banco_figuras)
        )
        figuras_v_layout.addLayout(figuras_titulo_layout)
        self.filtro_figuras_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_figuras_check.stateChanged.connect(self.atualizar_bancos_visuais)
        figuras_v_layout.addWidget(self.filtro_figuras_check)
        figuras_v_layout.addWidget(self.arvore_figuras)
        
        figuras_btn_layout = QHBoxLayout()
        btn_add_figura = QPushButton("Criar")
        btn_edit_figura = QPushButton("Editar")
        btn_del_figura = QPushButton("Remover")
        btn_edit_figura.setProperty("cssClass", "utility")
        btn_del_figura.setProperty("cssClass", "destructive")
        figuras_btn_layout.addWidget(btn_add_figura)
        figuras_btn_layout.addWidget(btn_edit_figura)
        figuras_btn_layout.addWidget(btn_del_figura)
        figuras_v_layout.addLayout(figuras_btn_layout)
        
        btn_ins_figura = QPushButton("Inserir no Texto")
        figuras_v_layout.addWidget(btn_ins_figura)
        
        btn_add_figura.clicked.connect(self._adicionar_figura)
        btn_edit_figura.clicked.connect(self._editar_figura)
        btn_del_figura.clicked.connect(self._remover_figura)
        btn_ins_figura.clicked.connect(lambda: self._inserir_marcador_selecionado(self.arvore_figuras, "Figura"))

        # --- Aba Gráficos ---
        graficos_widget = QWidget()
        graficos_v_layout = QVBoxLayout(graficos_widget)
        graficos_titulo_layout = _criar_layout_titulo_bin(
            "Banco de Gráficos:",
            lambda: self._adicionar_bin(self.arvore_graficos, "graficos"),
            lambda: self._remover_bin(self.arvore_graficos, "graficos", self.documento.banco_graficos)
        )
        graficos_v_layout.addLayout(graficos_titulo_layout)
        self.filtro_graficos_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_graficos_check.stateChanged.connect(self.atualizar_bancos_visuais)
        graficos_v_layout.addWidget(self.filtro_graficos_check)
        graficos_v_layout.addWidget(self.arvore_graficos)
        
        graficos_btn_layout = QHBoxLayout()
        btn_add_grafico = QPushButton("Criar")
        btn_edit_grafico = QPushButton("Editar")
        btn_del_grafico = QPushButton("Remover")
        btn_edit_grafico.setProperty("cssClass", "utility")
        btn_del_grafico.setProperty("cssClass", "destructive")
        graficos_btn_layout.addWidget(btn_add_grafico)
        graficos_btn_layout.addWidget(btn_edit_grafico)
        graficos_btn_layout.addWidget(btn_del_grafico)
        graficos_v_layout.addLayout(graficos_btn_layout)
        
        btn_ins_grafico = QPushButton("Inserir no Texto")
        graficos_v_layout.addWidget(btn_ins_grafico)
        
        btn_add_grafico.clicked.connect(self._adicionar_grafico)
        btn_edit_grafico.clicked.connect(self._editar_grafico)
        btn_del_grafico.clicked.connect(self._remover_grafico)
        btn_ins_grafico.clicked.connect(lambda: self._inserir_marcador_selecionado(self.arvore_graficos, "Grafico"))

        # --- Aba Fórmulas ---
        formulas_widget = QWidget()
        formulas_v_layout = QVBoxLayout(formulas_widget)
        formulas_titulo_layout = _criar_layout_titulo_bin(
            "Banco de Fórmulas:",
            lambda: self._adicionar_bin(self.arvore_formulas, "formulas"),
            lambda: self._remover_bin(self.arvore_formulas, "formulas", self.documento.banco_formulas)
        )
        formulas_v_layout.addLayout(formulas_titulo_layout)
        self.filtro_formulas_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_formulas_check.stateChanged.connect(self.atualizar_bancos_visuais)
        formulas_v_layout.addWidget(self.filtro_formulas_check)
        formulas_v_layout.addWidget(self.arvore_formulas)
        
        formulas_btn_layout = QHBoxLayout()
        btn_add_formula = QPushButton("Criar")
        btn_edit_formula = QPushButton("Editar")
        btn_del_formula = QPushButton("Remover")
        btn_edit_formula.setProperty("cssClass", "utility")
        btn_del_formula.setProperty("cssClass", "destructive")
        formulas_btn_layout.addWidget(btn_add_formula)
        formulas_btn_layout.addWidget(btn_edit_formula)
        formulas_btn_layout.addWidget(btn_del_formula)
        formulas_v_layout.addLayout(formulas_btn_layout)
        
        btn_ins_formula = QPushButton("Inserir no Texto")
        formulas_v_layout.addWidget(btn_ins_formula)
        
        btn_add_formula.clicked.connect(self._adicionar_formula)
        btn_edit_formula.clicked.connect(self._editar_formula)
        btn_del_formula.clicked.connect(self._remover_formula)
        btn_ins_formula.clicked.connect(lambda: self._inserir_marcador_selecionado(self.arvore_formulas, "Formula"))
        
        # --- Aba Listas ---
        listas_widget = QWidget()
        listas_v_layout = QVBoxLayout(listas_widget)
        listas_titulo_layout = _criar_layout_titulo_bin(
            "Banco de Listas:",
            lambda: self._adicionar_bin(self.arvore_listas, "listas"),
            lambda: self._remover_bin(self.arvore_listas, "listas", self.documento.banco_listas)
        )
        listas_v_layout.addLayout(listas_titulo_layout)
        self.filtro_listas_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_listas_check.stateChanged.connect(self.atualizar_bancos_visuais)
        listas_v_layout.addWidget(self.filtro_listas_check)
        listas_v_layout.addWidget(self.arvore_listas)
        
        listas_btn_layout = QHBoxLayout()
        btn_add_lista = QPushButton("Criar")
        btn_edit_lista = QPushButton("Editar")
        btn_del_lista = QPushButton("Remover")
        btn_edit_lista.setProperty("cssClass", "utility")
        btn_del_lista.setProperty("cssClass", "destructive")
        listas_btn_layout.addWidget(btn_add_lista)
        listas_btn_layout.addWidget(btn_edit_lista)
        listas_btn_layout.addWidget(btn_del_lista)
        listas_v_layout.addLayout(listas_btn_layout)
        
        btn_ins_lista = QPushButton("Inserir no Texto")
        listas_v_layout.addWidget(btn_ins_lista)
        
        btn_add_lista.clicked.connect(self._adicionar_lista)
        btn_edit_lista.clicked.connect(self._editar_lista)
        btn_del_lista.clicked.connect(self._remover_lista)
        btn_ins_lista.clicked.connect(lambda: self._inserir_marcador_selecionado(self.arvore_listas, "Lista"))
        
        # Adiciona os widgets criados como abas no QTabWidget
        self.bancos_tabs.addTab(tabelas_widget, "Tabelas")
        self.bancos_tabs.addTab(figuras_widget, "Figuras")
        self.bancos_tabs.addTab(graficos_widget, "Gráficos") 
        self.bancos_tabs.addTab(formulas_widget, "Fórmulas")
        self.bancos_tabs.addTab(listas_widget, "Listas") 

        left_splitter.addWidget(self.bancos_tabs)
        
        layout.addWidget(left_splitter)

        # --- 3. PAINEL DIREITO (Editor de Texto) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.label_capitulo_atual = QLabel("Selecione um tópico para editar")
        self.label_capitulo_atual.setProperty("cssClass", "titulo")
        
        format_toolbar = QHBoxLayout()
        format_toolbar.addWidget(QLabel("Formatação:"))
        
        self.btn_desfazer = QToolButton()
        self.btn_desfazer.setIcon(QtGui.QIcon("assets/icons/undo.png"))
        self.btn_desfazer.setToolTip("Desfazer (Ctrl+Z)")
        self.btn_desfazer.setEnabled(False)
        format_toolbar.addWidget(self.btn_desfazer)

        self.btn_refazer = QToolButton()
        self.btn_refazer.setIcon(QtGui.QIcon("assets/icons/redo.png"))
        self.btn_refazer.setToolTip("Refazer (Ctrl+Y)")
        self.btn_refazer.setEnabled(False)
        format_toolbar.addWidget(self.btn_refazer)
        
        self.btn_quebra_pagina = QToolButton()
        self.btn_quebra_pagina.setIcon(QtGui.QIcon("assets/icons/page_break.png")) 
        self.btn_quebra_pagina.setToolTip("Inserir Quebra de Página (Ctrl+Enter)")
        self.btn_quebra_pagina.clicked.connect(self._inserir_quebra_pagina)
        format_toolbar.addWidget(self.btn_quebra_pagina)
        
        self.btn_pagina_em_branco = QToolButton()
        self.btn_pagina_em_branco.setIcon(QtGui.QIcon("assets/icons/blank_page.png"))
        self.btn_pagina_em_branco.setToolTip("Inserir Página em Branco")
        self.btn_pagina_em_branco.clicked.connect(self._inserir_pagina_em_branco)
        format_toolbar.addWidget(self.btn_pagina_em_branco)
        
        format_toolbar.addStretch()
        
        self.editor_capitulo = EditorConteudo(aba_conteudo_parent=self) 
        self.editor_capitulo.textChanged.connect(self._on_editor_text_changed)

        self.highlighter = MarcadorHighlighter(self.editor_capitulo.document())

        self.btn_desfazer.clicked.connect(self.editor_capitulo.undo)
        self.btn_refazer.clicked.connect(self.editor_capitulo.redo)
        
        self.editor_capitulo.undoAvailable.connect(self.btn_desfazer.setEnabled)
        self.editor_capitulo.redoAvailable.connect(self.btn_refazer.setEnabled)
        
        right_layout.addWidget(self.label_capitulo_atual)
        right_layout.addLayout(format_toolbar)
        right_layout.addWidget(self.editor_capitulo, 1) 
        
        layout.addWidget(right_panel, 1) 
        
        # --- INÍCIO DA MODIFICAÇÃO (Inline Bin-Editing) ---
        # Popula o mapa de árvores e conecta os sinais de edição
        self.bin_tree_map = {
            self.arvore_tabelas: ("tabelas", self.documento.banco_tabelas),
            self.arvore_figuras: ("figuras", self.documento.banco_figuras),
            self.arvore_graficos: ("graficos", self.documento.banco_graficos),
            self.arvore_formulas: ("formulas", self.documento.banco_formulas),
            self.arvore_listas: ("listas", self.documento.banco_listas),
        }
        
        for tree in self.bin_tree_map.keys():
            # Conecta o handler que processa a mudança de nome
            tree.itemChanged.connect(self._on_bin_item_changed)
        # --- FIM DA MODIFICAÇÃO ---
        
        self._popular_arvore()
        if self.arvore_capitulos.topLevelItemCount() > 0:
            self.arvore_capitulos.setCurrentItem(self.arvore_capitulos.topLevelItem(0))

    # --- MÉTODOS DE MENU DE CONTEXTO (MODIFICADOS) ---

    @QtCore.Slot(QMenu)
    def _adicionar_acoes_menu_contexto(self, menu: QMenu): # Aceita o menu nativo
        menu.addSeparator() 

        menu_tabelas = menu.addMenu("Inserir Tabela")
        self._adicionar_submenus_banco(
            menu=menu_tabelas, 
            banco=self.documento.banco_tabelas, 
            tipo="Tabela",
            inserir_slot=self._inserir_marcador_generico,
            criar_slot=self._adicionar_tabela
        )

        menu_figuras = menu.addMenu("Inserir Figura")
        self._adicionar_submenus_banco(
            menu=menu_figuras, 
            banco=self.documento.banco_figuras, 
            tipo="Figura",
            inserir_slot=self._inserir_marcador_generico,
            criar_slot=self._adicionar_figura
        )

        menu_graficos = menu.addMenu("Inserir Gráfico")
        self._adicionar_submenus_banco(
            menu=menu_graficos, 
            banco=self.documento.banco_graficos,
            tipo="Grafico",
            inserir_slot=self._inserir_marcador_generico,
            criar_slot=self._adicionar_grafico
        )

        menu_formulas = menu.addMenu("Inserir Fórmula")
        self._adicionar_submenus_banco(
            menu=menu_formulas, 
            banco=self.documento.banco_formulas, 
            tipo="Formula",
            inserir_slot=self._inserir_marcador_generico,
            criar_slot=self._adicionar_formula
        )
        
        menu_listas = menu.addMenu("Inserir Lista")
        self._adicionar_submenus_banco(
            menu=menu_listas, 
            banco=self.documento.banco_listas, 
            tipo="Lista",
            inserir_slot=self._inserir_marcador_generico,
            criar_slot=self._adicionar_lista
        )


    def _adicionar_submenus_banco(self, menu: QMenu, banco: list, tipo: str, inserir_slot, criar_slot):
        acao_novo = menu.addAction(f"Criar Nova {tipo}...")
        acao_novo.triggered.connect(criar_slot)
        
        if banco:
            menu.addSeparator()
            for item in banco:
                nome = getattr(item, 'titulo', None) or getattr(item, 'legenda', None)
                
                if nome:
                    acao_inserir = menu.addAction(f"Inserir: {nome}")
                    acao_inserir.triggered.connect(lambda checked, n=nome, t=tipo: inserir_slot(t, n))
    
    @QtCore.Slot(str, str)
    def _inserir_marcador_generico(self, tipo: str, nome: str):
        self.editor_capitulo.insertPlainText(f"\n{{{{{tipo}:{nome}}}}}\n")

    # --- FIM DOS MÉTODOS DE MENU DE CONTEXTO ---

    # --- INÍCIO DA MODIFICAÇÃO (v46) ---
    # Método genérico para popular uma BinTreeWidget
    def _popular_arvore_bin(self, tree_widget: BinTreeWidget, lista_ativos: list, filtro_check: QCheckBox, conteudo_capitulo: str, tipo_marcador: str, bin_key: str):
        """
        Popula uma BinTreeWidget, organizando os ativos em bins.
        Aplica o filtro de "tópico atual" se estiver ativo.
        """
        tree_widget.blockSignals(True)
        tree_widget.clear()

        # 1. Obter o conjunto de ativos usados neste tópico, se o filtro estiver ativo
        titulos_usados = set()
        filtrar_topico = filtro_check.isChecked() and conteudo_capitulo
        if filtrar_topico:
            titulos_usados = set(re.findall(r"\{\{" + tipo_marcador + r":([^}]+)\}\}", conteudo_capitulo))

        # 2. Criar os Bins
        bins_existentes = {} # Mapeia nome do bin -> QTreeWidgetItem
        
        # Bin Padrão (sempre existe)
        bin_padrao = QTreeWidgetItem(tree_widget, ["(Padrão)"])
        bin_padrao.setFont(0, self.default_bin_font)
        bin_padrao.setForeground(0, self.default_bin_brush)
        bin_padrao.setToolTip(0, "Itens que não estão em um bin")
        bin_padrao.setFlags(bin_padrao.flags() & ~Qt.ItemFlag.ItemIsEditable & ~Qt.ItemFlag.ItemIsDropEnabled & ~Qt.ItemFlag.ItemIsDragEnabled) # Não pode ser editado, alvo ou arrastado
        bins_existentes["(Padrão)"] = bin_padrao
        
        # Bins do Usuário
        for nome_bin in sorted(self.documento.banco_bins.get(bin_key, [])):
            item_bin = QTreeWidgetItem(tree_widget, [nome_bin])
            item_bin.setFont(0, self.bin_font)
            item_bin.setFlags(item_bin.flags() & ~Qt.ItemFlag.ItemIsDragEnabled) # Bins não podem ser arrastados
            
            # --- INÍCIO DA MODIFICAÇÃO (Inline Bin-Editing) ---
            # Permite que bins existentes sejam renomeados
            item_bin.setFlags(item_bin.flags() | Qt.ItemFlag.ItemIsEditable) 
            # Armazena o nome atual para lógica de renomeação
            item_bin.setData(0, self.OLD_NAME_ROLE, nome_bin) 
            # --- FIM DA MODIFICAÇÃO ---
            
            item_bin.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
            bins_existentes[nome_bin] = item_bin
            
        # 3. Adicionar Ativos aos Bins
        for ativo in lista_ativos:
            nome_ativo = getattr(ativo, 'titulo', None) or getattr(ativo, 'legenda', None)
            if not nome_ativo:
                continue

            # Aplica filtro de tópico
            if filtrar_topico and nome_ativo not in titulos_usados:
                continue

            # Encontra o bin pai
            nome_bin = ativo.bin_name
            if nome_bin and nome_bin in bins_existentes:
                item_bin_pai = bins_existentes[nome_bin]
            else:
                item_bin_pai = bin_padrao # Padrão

            # Cria o item do ativo
            item_ativo = QTreeWidgetItem(item_bin_pai, [nome_ativo])
            item_ativo.setData(0, QtCore.Qt.ItemDataRole.UserRole, ativo) # Armazena o objeto
            item_ativo.setFlags(item_ativo.flags() & ~Qt.ItemFlag.ItemIsEditable | Qt.ItemFlag.ItemIsDragEnabled) # Ativos podem ser arrastados
            
        tree_widget.expandAll()
        tree_widget.blockSignals(False)
    
    @QtCore.Slot()
    def atualizar_bancos_visuais(self):
        """
        Atualiza TODOS os bancos de ativos (árvores),
        respeitando os filtros de tópico e os bins.
        """
        capitulo_selecionado = self._get_capitulo_selecionado()
        conteudo_capitulo = capitulo_selecionado.conteudo if capitulo_selecionado else ""

        # Popula Tabelas
        self._popular_arvore_bin(self.arvore_tabelas, self.documento.banco_tabelas, 
                                 self.filtro_tabelas_check, conteudo_capitulo, 
                                 "Tabela", "tabelas")
        
        # Popula Figuras
        self._popular_arvore_bin(self.arvore_figuras, self.documento.banco_figuras, 
                                 self.filtro_figuras_check, conteudo_capitulo, 
                                 "Figura", "figuras")
                                 
        # Popula Gráficos
        self._popular_arvore_bin(self.arvore_graficos, self.documento.banco_graficos, 
                                 self.filtro_graficos_check, conteudo_capitulo, 
                                 "Grafico", "graficos")
        
        # Popula Fórmulas
        self._popular_arvore_bin(self.arvore_formulas, self.documento.banco_formulas, 
                                 self.filtro_formulas_check, conteudo_capitulo, 
                                 "Formula", "formulas")

        # Popula Listas
        self._popular_arvore_bin(self.arvore_listas, self.documento.banco_listas, 
                                 self.filtro_listas_check, conteudo_capitulo, 
                                 "Lista", "listas")
    
    # --- FIM DA MODIFICAÇÃO (v46) ---


    @QtCore.Slot()
    def _inserir_quebra_pagina(self):
        self.editor_capitulo.insertPlainText("\n{{QUEBRA_PAGINA}}\n")

    @QtCore.Slot()
    def _inserir_pagina_em_branco(self):
        self.editor_capitulo.insertPlainText("\n{{PAGINA_EM_BRANCO}}\n")
    
    @QtCore.Slot()
    def _on_editor_text_changed(self):
        self._salvar_conteudo_capitulo()
        # Atualiza os filtros caso um novo marcador tenha sido digitado
        self.atualizar_bancos_visuais()

    def _get_item_numero_completo(self, item: QTreeWidgetItem) -> str:
        path_parts = []
        current = item
        
        while current and current is not self.arvore_capitulos.invisibleRootItem():
            parent = current.parent()
            index = -1
            
            if parent:
                index = parent.indexOfChild(current)
            else:
                index = self.arvore_capitulos.indexOfTopLevelItem(current)
                
            if index != -1:
                path_parts.append(str(index + 1))
            else:
                break 
            
            current = parent
            
        return ".".join(reversed(path_parts))

    @QtCore.Slot(QTreeWidgetItem, QTreeWidgetItem)
    def _on_capitulo_selecionado_changed(self, item_atual, item_anterior):
        self._carregar_capitulo_no_editor(item_atual, item_anterior)
        self.atualizar_bancos_visuais() # Atualiza os filtros para o novo capítulo

        if item_atual:
            try:
                numero_completo = self._get_item_numero_completo(item_atual)
                if numero_completo:
                    id_ancora = f"secao-{numero_completo.replace('.', '-')}"
                    self.topicoSelecionadoParaNavegacao.emit(id_ancora)
            except Exception as e:
                print(f"Erro ao gerar âncora para navegação: {e}")

    @QtCore.Slot(str)
    def _filtrar_arvore(self, texto_busca):
        texto_busca = texto_busca.lower()
        def visitar_item(item):
            capitulo_modelo = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
            titulo_corresponde = texto_busca in item.text(0).lower()
            conteudo_corresponde = False
            if capitulo_modelo and capitulo_modelo.conteudo:
                conteudo_corresponde = texto_busca in capitulo_modelo.conteudo.lower()
            item_corresponde = titulo_corresponde or conteudo_corresponde
            algum_filho_corresponde = False
            for i in range(item.childCount()):
                if visitar_item(item.child(i)):
                    algum_filho_corresponde = True
            deve_ficar_visivel = item_corresponde or algum_filho_corresponde
            item.setHidden(not deve_ficar_visivel)
            if algum_filho_corresponde:
                item.setExpanded(True)
            return deve_ficar_visivel
        root = self.arvore_capitulos.invisibleRootItem()
        for i in range(root.childCount()):
            visitar_item(root.child(i))

    @QtCore.Slot(int)
    def _alternar_modo_arrastar(self, state):
        if state == QtCore.Qt.CheckState.Checked.value:
            self.arvore_capitulos.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.arvore_capitulos.setHeaderLabel("Tópicos (Modo Reorganizar)")
        else:
            self.arvore_capitulos.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
            self.arvore_capitulos.setHeaderLabel("Tópicos")
            
    @QtCore.Slot(QTreeWidgetItem, QTreeWidgetItem)
    def _carregar_capitulo_no_editor(self, item_atual, item_anterior):
        capitulo = self._get_capitulo_selecionado()
        elementos_habilitados = True if capitulo else False
        self.bancos_tabs.setEnabled(elementos_habilitados)
        self.btn_quebra_pagina.setEnabled(elementos_habilitados)
        self.btn_pagina_em_branco.setEnabled(elementos_habilitados)
        
        if hasattr(self, 'btn_desfazer'):
            self.btn_desfazer.setEnabled(elementos_habilitados and self.editor_capitulo.document().isUndoAvailable())
        if hasattr(self, 'btn_refazer'):
            self.btn_refazer.setEnabled(elementos_habilitados and self.editor_capitulo.document().isRedoAvailable())
        
        if not capitulo:
            self.editor_capitulo.clear()
            self.editor_capitulo.setEnabled(False)
            self.label_capitulo_atual.setText("Selecione um tópico")
            return
        
        self._carregando_capitulo = True
        self.label_capitulo_atual.setText(f"Editando: {capitulo.titulo}")
        self.editor_capitulo.setPlainText(capitulo.conteudo)
        self.editor_capitulo.setEnabled(True)
        self._carregando_capitulo = False

    # --- INÍCIO DA MODIFICAÇÃO (v52) ---
    # Métodos genéricos para gerenciamento de Bins
    
    def _adicionar_bin(self, tree_widget: QTreeWidget, bin_key: str):
        """
        Adiciona um novo item de bin na árvore e o coloca
        imediatamente em modo de edição (estilo Windows).
        """
        # --- Lógica de numeração (v51) ---
        base_name = "Novo Bin"
        temp_name = base_name
        
        # 1. Verifica se "Novo Bin" (sem número) existe
        if tree_widget.findItems(temp_name, Qt.MatchFlag.MatchExactly):
            # Se existe, começa a procurar por "Novo Bin 2"
            i = 2
            while True:
                temp_name = f"{base_name} {i}"
                if not tree_widget.findItems(temp_name, Qt.MatchFlag.MatchExactly):
                    # Encontrou um nome vago
                    break
                i += 1
        # Se "Novo Bin" não existia, temp_name já é "Novo Bin"
        # --- Fim da lógica de numeração ---

        # Bloqueia sinais para evitar 'itemChanged' prematuro
        tree_widget.blockSignals(True)

        # Cria o item na UI
        item_bin = QTreeWidgetItem(tree_widget, [temp_name])
        item_bin.setFont(0, self.bin_font)
        item_bin.setIcon(0, self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon))
        
        # Define as flags (editável, mas não arrastável)
        flags = (Qt.ItemFlag.ItemIsSelectable | 
                 Qt.ItemFlag.ItemIsUserCheckable | 
                 Qt.ItemFlag.ItemIsEnabled | 
                 Qt.ItemFlag.ItemIsDropEnabled | 
                 Qt.ItemFlag.ItemIsEditable)
        item_bin.setFlags(flags)
        
        # Armazena os dados temporários no item
        item_bin.setData(0, self.IS_NEW_BIN_ROLE, True) # Marca como "novo"
        item_bin.setData(0, self.OLD_NAME_ROLE, temp_name) # Armazena nome
        
        # Desbloqueia os sinais
        tree_widget.blockSignals(False)
        
        # Garante foco e inicia a edição
        tree_widget.setFocus()
        tree_widget.setCurrentItem(item_bin)
        tree_widget.editItem(item_bin, 0) # Inicia a edição

    @QtCore.Slot(QTreeWidgetItem, int)
    def _on_bin_item_changed(self, item: QTreeWidgetItem, column: int):
        """
        Handler chamado QUANDO a edição de um item de bin (novo ou existente)
        é concluída.
        """
        # Ignora se não for a coluna 0 ou se for um item filho (um ativo)
        if column != 0 or item.parent():
            return
            
        tree_widget = item.treeWidget()
        if not tree_widget or tree_widget not in self.bin_tree_map:
            return

        # 1. Obter dados de contexto
        bin_key, banco_de_ativos = self.bin_tree_map[tree_widget]
        lista_bins_modelo = self.documento.banco_bins.get(bin_key, [])
        
        new_name = item.text(0).strip()
        is_new = item.data(0, self.IS_NEW_BIN_ROLE) or False
        old_name = item.data(0, self.OLD_NAME_ROLE)

        # 2. Lógica de Validação e Cancelamento
        
        # CASO A: Usuário cancelou a criação (pressionou Esc)
        # O QLineEdit reverte o texto para o old_name
        if new_name == old_name and is_new:
            tree_widget.blockSignals(True)
            tree_widget.takeTopLevelItem(tree_widget.indexOfTopLevelItem(item))
            tree_widget.blockSignals(False)
            return
        
        # CASO B: Nome ficou vazio (usuário apagou e deu Enter)
        if not new_name:
            tree_widget.blockSignals(True) 
            QMessageBox.warning(self, "Nome Inválido", "O nome do bin não pode ficar vazio.")
            # CORREÇÃO (v52): Sempre reverter, nunca deletar
            item.setText(0, old_name) 
            tree_widget.blockSignals(False) 
            return
            
        # CASO C: Nome reservado
        if new_name == "(Padrão)":
            tree_widget.blockSignals(True)
            QMessageBox.warning(self, "Nome Inválido", "Este nome é reservado.")
            # CORREÇÃO (v52): Sempre reverter, nunca deletar
            item.setText(0, old_name)
            tree_widget.blockSignals(False)
            return

        # CASO D: Nome duplicado
        # (Procura na lista de bins do modelo, ignorando o nome antigo)
        outros_nomes = [b.lower() for b in lista_bins_modelo if b.lower() != (old_name.lower() if old_name else None)]
        if new_name.lower() in outros_nomes:
            tree_widget.blockSignals(True)
            QMessageBox.warning(self, "Nome Duplicado", "Já existe um bin com este nome.")
            # CORREÇÃO (v52): Sempre reverter, nunca deletar
            item.setText(0, old_name)
            tree_widget.blockSignals(False)
            return

        # 3. Salvar no Modelo de Dados (Nome é válido)
        
        tree_widget.blockSignals(True)
        
        if is_new:
            # É um bin novo, apenas adiciona ao modelo
            lista_bins_modelo.append(new_name)
            self.documento.banco_bins[bin_key] = lista_bins_modelo
            # Remove a flag de "novo"
            item.setData(0, self.IS_NEW_BIN_ROLE, None) 
        
        else:
            # É uma renomeação de um bin existente
            # (Verifica se old_name está no modelo - pode não estar se a 
            #  edição anterior falhou, mas o old_name_role foi atualizado)
            if old_name in lista_bins_modelo:
                lista_bins_modelo.remove(old_name)
            
            lista_bins_modelo.append(new_name)
            self.documento.banco_bins[bin_key] = lista_bins_modelo
            
            # Atualiza todos os ativos que usavam o nome antigo
            for ativo in banco_de_ativos:
                if getattr(ativo, 'bin_name', None) == old_name:
                    ativo.bin_name = new_name
            
        # Atualiza o "nome antigo" para a próxima renomeação
        item.setData(0, self.OLD_NAME_ROLE, new_name)
        
        tree_widget.blockSignals(False)

    # --- FIM DA MODIFICAÇÃO (v52) ---


    def _remover_bin(self, tree_widget: BinTreeWidget, bin_key: str, banco_ativos: list):
        """Remove um bin, movendo todos os seus ativos para o bin (Padrão)."""
        item_selecionado = tree_widget.currentItem()
        if not item_selecionado or item_selecionado.parent():
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um bin (pasta) para remover.")
            return
            
        nome_bin = item_selecionado.text(0)
        
        # Proteção contra remoção de um item recém-criado
        if item_selecionado.data(0, self.IS_NEW_BIN_ROLE):
            tree_widget.takeTopLevelItem(tree_widget.indexOfTopLevelItem(item_selecionado))
            return
            
        if nome_bin == "(Padrão)":
            QMessageBox.warning(self, "Ação Inválida", "Não é possível remover o bin Padrão.")
            return
            
        resposta = QMessageBox.question(self, "Confirmar Remoção",
            f"Tem certeza que deseja remover o bin '{nome_bin}'?\n\n"
            f"Todos os itens dentro dele serão movidos para o bin '(Padrão)'.")
            
        if resposta == QMessageBox.StandardButton.Yes:
            # Remove do modelo de dados
            if nome_bin in self.documento.banco_bins.get(bin_key, []):
                self.documento.banco_bins[bin_key].remove(nome_bin)
                
            # Atualiza o bin_name de todos os ativos órfãos
            for ativo in banco_ativos:
                if getattr(ativo, 'bin_name', None) == nome_bin:
                    ativo.bin_name = None
                        
            # Redesenha todas as árvores (mais fácil do que mover os itens na UI)
            self.atualizar_bancos_visuais()

    def _get_item_selecionado(self, tree_widget: QTreeWidget) -> tuple[QTreeWidgetItem | None, object | None]:
        """
        Retorna o item e o objeto de dados (ativo) selecionado.
        Retorna (None, None) se um bin ou nada for selecionado.
        """
        item = tree_widget.currentItem()
        if not item or not item.parent():
            # Nenhum item selecionado, ou o item é um bin (não tem pai)
            return None, None
            
        asset = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        return item, asset
        
    def _get_bin_alvo(self, tree_widget: QTreeWidget) -> tuple[QTreeWidgetItem, str | None]:
        """
        Descobre em qual bin um novo ativo deve ser criado.
        Retorna (item_do_bin_widget, nome_do_bin_string).
        """
        item_selecionado = tree_widget.currentItem()
        item_bin_alvo = None
        
        if item_selecionado:
            if item_selecionado.parent() is None: # É um bin
                item_bin_alvo = item_selecionado
            else: # É um ativo
                item_bin_alvo = item_selecionado.parent()
        
        if not item_bin_alvo:
            # Nada selecionado, encontra o bin "(Padrão)"
            padrao_itens = tree_widget.findItems("(Padrão)", Qt.MatchFlag.MatchExactly)
            if padrao_itens:
                item_bin_alvo = padrao_itens[0]
            else:
                # Fallback de segurança (nunca deve acontecer)
                item_bin_alvo = tree_widget.invisibleRootItem()
        
        nome_bin = item_bin_alvo.text(0)
        
        # Proteção contra adição em um bin recém-criado e ainda não salvo
        if item_bin_alvo.data(0, self.IS_NEW_BIN_ROLE):
            item_bin_alvo = tree_widget.findItems("(Padrão)", Qt.MatchFlag.MatchExactly)[0]
            nome_bin = "(Padrão)"

        if nome_bin == "(Padrão)":
            return item_bin_alvo, None
        return item_bin_alvo, nome_bin

    def _inserir_marcador_selecionado(self, tree_widget: QTreeWidget, tipo_marcador: str):
        """Insere o marcador do ativo selecionado no editor."""
        item, asset = self._get_item_selecionado(tree_widget)
        if not asset:
            QMessageBox.warning(self, "Atenção", "Por favor, selecione um item (não um bin) para inserir.")
            return
            
        nome_ativo = getattr(asset, 'titulo', None) or getattr(asset, 'legenda', None)
        if nome_ativo:
            self._inserir_marcador_generico(tipo_marcador, nome_ativo)

    # --- FIM DA MODIFICAÇÃO (v46) ---


    @QtCore.Slot()
    def _adicionar_tabela(self):
        dialog = TabelaDialog(banco_tabelas=self.documento.banco_tabelas, parent=self)
        if dialog.exec():
            nova_tabela = dialog.get_dados_tabela()
            
            item_bin, nome_bin = self._get_bin_alvo(self.arvore_tabelas)
            nova_tabela.bin_name = nome_bin
            
            self.documento.banco_tabelas.append(nova_tabela)
            self.atualizar_bancos_visuais()
            if nova_tabela.titulo:
                self._inserir_marcador_generico("Tabela", nova_tabela.titulo)

    @QtCore.Slot()
    def _adicionar_figura(self):
        dialog = DialogoFigura(banco_figuras=self.documento.banco_figuras, parent=self)
        if dialog.exec():
            nova_figura = dialog.get_dados_figura()
            if nova_figura and nova_figura.caminho_processado:
                
                item_bin, nome_bin = self._get_bin_alvo(self.arvore_figuras)
                nova_figura.bin_name = nome_bin
                
                self.documento.banco_figuras.append(nova_figura)
                self.atualizar_bancos_visuais()
                if nova_figura.titulo:
                    self._inserir_marcador_generico("Figura", nova_figura.titulo)

    @QtCore.Slot()
    def _adicionar_formula(self):
        dialog = DialogoFormula(banco_formulas=self.documento.banco_formulas, parent=self)
        if dialog.exec():
            nova_formula = dialog.get_dados_formula()
            
            item_bin, nome_bin = self._get_bin_alvo(self.arvore_formulas)
            nova_formula.bin_name = nome_bin
            
            self.documento.banco_formulas.append(nova_formula)
            self.atualizar_bancos_visuais()
            if nova_formula.legenda:
                self._inserir_marcador_generico("Formula", nova_formula.legenda)

    @QtCore.Slot()
    def _adicionar_lista(self):
        dialog = ListaDialog(banco_listas=self.documento.banco_listas, parent=self)
        if dialog.exec():
            nova_lista = dialog.get_dados_lista()
            
            item_bin, nome_bin = self._get_bin_alvo(self.arvore_listas)
            nova_lista.bin_name = nome_bin
            
            self.documento.banco_listas.append(nova_lista)
            self.atualizar_bancos_visuais()
            self._inserir_marcador_generico("Lista", nova_lista.titulo)
            
    @QtCore.Slot()
    def _adicionar_grafico(self):
        dialog = ChartDialog(banco_graficos=self.documento.banco_graficos, parent=self)
        if dialog.exec():
            novo_grafico = dialog.get_dados_grafico()
            
            item_bin, nome_bin = self._get_bin_alvo(self.arvore_graficos)
            novo_grafico.bin_name = nome_bin
            
            self.documento.banco_graficos.append(novo_grafico)
            self.atualizar_bancos_visuais()
            self._inserir_marcador_generico("Grafico", novo_grafico.titulo)

    # --- MÉTODOS DE EDIÇÃO/REMOÇÃO ATUALIZADOS ---

    @QtCore.Slot()
    def _editar_tabela(self):
        item, tabela_original = self._get_item_selecionado(self.arvore_tabelas)
        if not tabela_original:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma tabela (não um bin) para editar.")
            return
        
        dialog = TabelaDialog(tabela=tabela_original, 
                              banco_tabelas=self.documento.banco_tabelas, 
                              parent=self)
        
        if dialog.exec():
            tabela_original.__dict__.update(dialog.get_dados_tabela().__dict__)
            self.atualizar_bancos_visuais() # Redesenha a árvore

    @QtCore.Slot()
    def _remover_tabela(self):
        item, tabela = self._get_item_selecionado(self.arvore_tabelas)
        if not tabela:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma tabela (não um bin) para remover.")
            return

        if QMessageBox.question(self, "Confirmar", f"Remover a tabela '{tabela.titulo}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_tabelas.remove(tabela)
            self.atualizar_bancos_visuais()
            
    @QtCore.Slot()
    def _editar_figura(self):
        item, figura_original = self._get_item_selecionado(self.arvore_figuras)
        if not figura_original:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma figura (não um bin) para editar.")
            return
        
        dialog = DialogoFigura(figura=figura_original, 
                               banco_figuras=self.documento.banco_figuras, 
                               parent=self)
        
        if dialog.exec():
            dados_novos = dialog.get_dados_figura()
            figura_original.__dict__.update(dados_novos.__dict__)
            self.atualizar_bancos_visuais()
    
    @QtCore.Slot()
    def _remover_figura(self):
        item, figura = self._get_item_selecionado(self.arvore_figuras)
        if not figura:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma figura (não um bin) para remover.")
            return
            
        if QMessageBox.question(self, "Confirmar", f"Remover a figura '{figura.titulo}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_figuras.remove(figura)
            self.atualizar_bancos_visuais()
            
    @QtCore.Slot()
    def _editar_grafico(self):
        item, grafico_original = self._get_item_selecionado(self.arvore_graficos)
        if not grafico_original:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um gráfico (não um bin) para editar.")
            return
        
        dialog = ChartDialog(grafico=grafico_original, 
                             banco_graficos=self.documento.banco_graficos, 
                             parent=self)
        
        if dialog.exec():
            dados_novos = dialog.get_dados_grafico()
            grafico_original.__dict__.update(dados_novos.__dict__)
            self.atualizar_bancos_visuais()

    @QtCore.Slot()
    def _remover_grafico(self):
        item, grafico = self._get_item_selecionado(self.arvore_graficos)
        if not grafico:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione um gráfico (não um bin) para remover.")
            return
        
        if QMessageBox.question(self, "Confirmar", f"Remover o gráfico '{grafico.titulo}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_graficos.remove(grafico)
            self.atualizar_bancos_visuais()
            
            try:
                if os.path.exists(grafico.caminho_imagem_processada): os.remove(grafico.caminho_imagem_processada)
                if os.path.exists(grafico.caminho_dados_json): os.remove(grafico.caminho_dados_json)
            except OSError as e:
                print(f"Aviso: Não foi possível remover arquivos de cache do gráfico: {e}")

    @QtCore.Slot()
    def _editar_formula(self):
        item, formula_original = self._get_item_selecionado(self.arvore_formulas)
        if not formula_original:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma fórmula (não um bin) para editar.")
            return
            
        dialog = DialogoFormula(formula=formula_original, 
                                banco_formulas=self.documento.banco_formulas, 
                                parent=self)
        
        if dialog.exec():
            formula_original.__dict__.update(dialog.get_dados_formula().__dict__)
            self.atualizar_bancos_visuais()
    
    @QtCore.Slot()
    def _remover_formula(self):
        item, formula = self._get_item_selecionado(self.arvore_formulas)
        if not formula:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma fórmula (não um bin) para remover.")
            return

        if QMessageBox.question(self, "Confirmar", f"Remover a fórmula '{formula.legenda}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_formulas.remove(formula)
            self.atualizar_bancos_visuais()
            
    @QtCore.Slot()
    def _editar_lista(self):
        item, lista_original = self._get_item_selecionado(self.arvore_listas)
        if not lista_original:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma lista (não um bin) para editar.")
            return
        
        dialog = ListaDialog(lista_existente=lista_original, 
                             banco_listas=self.documento.banco_listas, 
                             parent=self)
        
        if dialog.exec():
            lista_editada = dialog.get_dados_lista()
            lista_original.__dict__.update(lista_editada.__dict__)
            self.atualizar_bancos_visuais()

    @QtCore.Slot()
    def _remover_lista(self):
        item, lista = self._get_item_selecionado(self.arvore_listas)
        if not lista:
            QMessageBox.warning(self, "Ação Inválida", "Por favor, selecione uma lista (não um bin) para remover.")
            return
        
        if QMessageBox.question(self, "Confirmar", f"Remover a lista '{lista.titulo}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_listas.remove(lista)
            self.atualizar_bancos_visuais()

    # --- FIM DOS MÉTODOS DE EDIÇÃO/REMOÇÃO ---

    def _get_capitulo_selecionado(self) -> Capitulo | None:
        item = self.arvore_capitulos.currentItem()
        return item.data(0, QtCore.Qt.ItemDataRole.UserRole) if item else None

    @QtCore.Slot()
    def _salvar_conteudo_capitulo(self):
        if self._carregando_capitulo: return
        capitulo = self._get_capitulo_selecionado()
        if capitulo:
            capitulo.conteudo = self.editor_capitulo.toPlainText()

    def _popular_arvore(self):
        self.arvore_capitulos.blockSignals(True)
        self.arvore_capitulos.clear()
        def adicionar_filhos_recursivo(no_pai_modelo, no_pai_widget):
            for filho_modelo in no_pai_modelo.filhos:
                item_widget = QTreeWidgetItem([filho_modelo.titulo])
                item_widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, filho_modelo)
                item_widget.setFlags(item_widget.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
                if not filho_modelo.is_template_item and filho_modelo.pai == self.documento.estrutura_textual:
                    font = item_widget.font(0); font.setItalic(True)
                    item_widget.setFont(0, font)
                    item_widget.setForeground(0, QtGui.QColor('dimgray'))
                    item_widget.setToolTip(0, "Este é um capítulo personalizado (não pertence ao modelo padrão).")
                if no_pai_widget is self.arvore_capitulos:
                    no_pai_widget.addTopLevelItem(item_widget)
                else:
                    no_pai_widget.addChild(item_widget)
                adicionar_filhos_recursivo(filho_modelo, item_widget)
        adicionar_filhos_recursivo(self.documento.estrutura_textual, self.arvore_capitulos)
        self.arvore_capitulos.expandAll()
        self.arvore_capitulos.blockSignals(False)

    @QtCore.Slot()
    def _adicionar_topico_principal(self):
        novo_capitulo = Capitulo(titulo="Novo Tópico")
        self.documento.estrutura_textual.adicionar_filho(novo_capitulo)
        self._popular_arvore()

    @QtCore.Slot()
    def _adicionar_subtopico(self):
        item_pai_widget = self.arvore_capitulos.currentItem()
        if not item_pai_widget:
            QMessageBox.warning(self, "Atenção", "Selecione um tópico para adicionar um subtópico.")
            return
        no_pai_modelo = item_pai_widget.data(0, QtCore.Qt.ItemDataRole.UserRole)
        novo_subtopico = Capitulo(titulo="Novo Subtópico")
        no_pai_modelo.adicionar_filho(novo_subtopico)
        self._popular_arvore()
        item_pai_widget.setExpanded(True)
        
    @QtCore.Slot()
    def _remover_topico(self):
        item_selecionado = self.arvore_capitulos.currentItem()
        if not item_selecionado: return
        no_modelo = item_selecionado.data(0, QtCore.Qt.ItemDataRole.UserRole)
        mensagem = f"Remover o tópico '{no_modelo.titulo}'?"
        if no_modelo.filhos:
            mensagem = f"Remover o tópico '{no_modelo.titulo}' e todos os seus subtópicos?"
        resposta = QMessageBox.question(self, "Confirmar Remoção", mensagem,
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resposta == QMessageBox.StandardButton.Yes:
            no_pai_modelo = no_modelo.pai
            if no_pai_modelo:
                no_pai_modelo.filhos.remove(no_modelo)
                self._popular_arvore()
            
    @QtCore.Slot(QTreeWidgetItem, int)
    def _renomear_capitulo(self, item, column):
        no_modelo = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if no_modelo and no_modelo.titulo != item.text(column):
            no_modelo.titulo = item.text(column)
            if self.arvore_capitulos.currentItem() is item:
                self.label_capitulo_atual.setText(f"Editando: {no_modelo.titulo}")
            
    def sincronizar_conteudo_pendente(self):
        self._salvar_conteudo_capitulo()
        
    @QtCore.Slot()
    def _sincronizar_modelo_com_arvore(self):
        nova_raiz = Capitulo(titulo="Raiz do Documento")
        def percorrer_arvore_ui(parent_item_widget, parent_node_modelo):
            for i in range(parent_item_widget.childCount()):
                child_item_widget = parent_item_widget.child(i)
                child_node_modelo = child_item_widget.data(0, QtCore.Qt.ItemDataRole.UserRole)
                child_node_modelo.filhos.clear() 
                parent_node_modelo.adicionar_filho(child_node_modelo)
                percorrer_arvore_ui(child_item_widget, child_node_modelo)
        root_widget = self.arvore_capitulos.invisibleRootItem()
        percorrer_arvore_ui(root_widget, nova_raiz)
        self.documento.estrutura_textual.filhos = nova_raiz.filhos