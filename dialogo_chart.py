# dialogo_chart.py
#
# Descrição: Adaptação do gerador de gráfico Matplotlib (v37)
# para um QDialog integrado ao Formatheus.
#
# ATUALIZAÇÃO (v55 - Correção de "Crash" com Enter):
# 1. Corrigido o "crash" (fechamento acidental) ao pressionar
#    Enter. O botão "OK" foi configurado para não ser mais
#    o botão padrão, impedindo que a tecla Enter usada na
#    edição de dados acione o fechamento do diálogo.
# 2. Corrigido UserWarning ao não tentar desenhar legenda
#    para gráficos do tipo Boxplot (que não possuem labels).
# 3. Mantém as melhorias da v54 (Multi-Série, Excel, Altura).
#

import sys
import os
os.environ['QT_API'] = 'PySide6'
import traceback
import pandas as pd
import numpy as np
import json 
import re

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QCheckBox,
    QMessageBox, QGroupBox, QFormLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QColorDialog, QScrollArea, QStackedWidget,
    QMainWindow, QTabWidget, QDialog, QDialogButtonBox, QSplitter,
    QGridLayout, QSlider, QToolButton, QStyle, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtGui import (
    QColor, QBrush, QFont,
    QAction, QKeySequence 
)

# Import matplotlib for Qt
from matplotlib.backends.backend_qtagg import (  # MODIFICADO para o backend genérico 'qtagg'
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.ticker import MultipleLocator
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib import colormaps # NOVO: Importação mais segura para colormaps

# Importa a classe de dados do documento
from documento import Grafico

# --- CONSTANTES DO GERADOR DE GRÁFICO ---
SAMPLE_DATASETS = {} # Dataset Iris removido

LEGEND_SIZE_MAP = {'Pequena': 8, 'Média': 10, 'Grande': 14}
BAR_ALIGN_MAP = {'Centro': 'center', 'Borda Esquerda': 'edge'}


def prettify_style_name(name):
    """Converte nomes de estilo internos em nomes amigáveis."""
    if name.startswith('_') or 'gallery' in name:
        return None
    if name.startswith('seaborn-v0_8'):
        name = name.replace('seaborn-v0_8', 'Seaborn')
    name = name.replace('_', ' ').replace('-', ' ')
    parts = []
    for part in name.split():
        if not part.isdigit():
            parts.append(part.capitalize())
    return ' '.join(parts)

def parse_axis_limit(text):
    """
    Converte texto em float para limite de eixo ou intervalo,
    ou None se vazio/inválido.
    """
    try:
        return float(text.strip())
    except ValueError:
        return None

class SeriesColorButton(QPushButton):
    """
    Um "quadradinho" de cor que abre o QColorDialog e atualiza
    o item da árvore (série) e seu próprio visual.
    """
    def __init__(self, series_item, on_change_callback):
        super().__init__()
        self.series_item = series_item
        self.on_change = on_change_callback
        self.clicked.connect(self.pick_color)
        self.setFixedSize(25, 25)
        self.setText("")
        self.sync_color()

    def pick_color(self):
        """Abre o seletor de cores."""
        current_color_hex = self.series_item.data(0, Qt.ItemDataRole.UserRole)
        dialog = QColorDialog(QColor(current_color_hex))
        
        if dialog.exec():
            new_color = dialog.selectedColor()
            self.series_item.setData(0, Qt.ItemDataRole.UserRole, new_color.name())
            self.sync_color()
            self.on_change()

    def sync_color(self):
        """Atualiza a cor do botão e do texto do item da árvore."""
        color_hex = self.series_item.data(0, Qt.ItemDataRole.UserRole)
        color = QColor(color_hex)
        
        self.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #555;")
        self.series_item.setForeground(0, QBrush(color))

# --- FIM DAS CONSTANTES/CLASSES AUXILIARES ---


class DataSourcePanel(QWidget):
    """Painel lateral esquerdo, focado apenas na entrada de dados."""
    def __init__(self, on_change, is_dark: bool = False, icon_path: str = "."):
        super().__init__()
        self.on_change = on_change # Conectado ao trigger_redraw
        self.df = None
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- Fonte de Dados ---
        data_group = QGroupBox('Fonte de Dados')
        data_layout_main = QVBoxLayout() 
        
        # 1. Seletor da Fonte Atual e Botão de Carregar
        top_data_layout = QHBoxLayout()
        top_data_layout.addWidget(QLabel("Fonte Atual:"))
        self.dataset_cb = QComboBox()
        self.dataset_cb.addItems(['Personalizado'] + list(SAMPLE_DATASETS.keys()))
        self.dataset_cb.currentIndexChanged.connect(self._emit_change)
        
        # --- MODIFICAÇÃO (v54 - Suporte a Excel) ---
        self.load_file_btn = QPushButton('Carregar Dados...')
        suffix = "-white" if is_dark else ""
        self.load_file_btn.setIcon(QtGui.QIcon(os.path.join(icon_path, f"browser{suffix}.png")))
        self.load_file_btn.clicked.connect(self._load_data_file)
        
        top_data_layout.addWidget(self.dataset_cb)
        top_data_layout.addWidget(self.load_file_btn)
        # --- FIM DA MODIFICAÇÃO ---
        
        data_layout_main.addLayout(top_data_layout)

        # 2. Painel da Árvore (para "Personalizado")
        self.tree_controls_widget = QWidget()
        tree_layout = QVBoxLayout()
        tree_layout.setContentsMargins(0, 5, 0, 0)
        
        self.series_tree = QTreeWidget()
        self.series_tree.setColumnCount(4)
        self.series_tree.setHeaderLabels(["Rótulo", "Valor X", "Valor Y", "Cor"])
        self.series_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.series_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.series_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.series_tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        
        self.series_tree.setColumnWidth(1, 100) 
        self.series_tree.setColumnWidth(2, 100) 
        self.series_tree.setColumnWidth(3, 60)
        self.series_tree.setAlternatingRowColors(True)
        
        self.series_tree.itemChanged.connect(self._emit_change)
        tree_layout.addWidget(self.series_tree)
        
        # Troca QHBoxLayout por QGridLayout
        tree_btn_layout = QGridLayout()
        add_series_btn = QPushButton("Adicionar Série (+)")
        add_series_btn.clicked.connect(self.add_series_item)
        add_point_btn = QPushButton("Adicionar Ponto (+)")
        add_point_btn.clicked.connect(self.add_data_point_item)
        remove_btn = QPushButton("Remover Item (-)")
        remove_btn.clicked.connect(self.remove_tree_item)
        
        tree_btn_layout.addWidget(add_series_btn, 0, 0)
        tree_btn_layout.addWidget(add_point_btn, 0, 1)
        tree_btn_layout.addWidget(remove_btn, 1, 0, 1, 2) # Span 1 linha, 2 colunas
        
        tree_layout.addLayout(tree_btn_layout)
        
        self.tree_controls_widget.setLayout(tree_layout)

        # 3. Painel de Colunas (para "CSV")
        self.csv_controls_widget = QWidget()
        csv_layout = QFormLayout()
        csv_layout.setContentsMargins(0, 5, 0, 0)
        
        self.label_col_cb = QComboBox()
        self.label_col_cb.currentIndexChanged.connect(self._emit_change)
        self.csv_label_label = QLabel('Coluna Rótulo X (Texto):')
        
        self.x_col_cb = QComboBox()
        self.x_col_cb.currentIndexChanged.connect(self._emit_change)
        self.csv_x_label = QLabel('Coluna Eixo X (Numérico):')
        
        # --- MODIFICAÇÃO (v54 - Multi-Série) ---
        self.y_list_widget = QListWidget()
        self.y_list_widget.setMinimumHeight(100) # Espaço para ver as colunas
        self.y_list_widget.itemChanged.connect(self._emit_change)
        self.csv_y_label = QLabel('Colunas Y (Séries):')
        # --- FIM DA MODIFICAÇÃO ---
        
        csv_layout.addRow(self.csv_label_label, self.label_col_cb)
        csv_layout.addRow(self.csv_x_label, self.x_col_cb)
        csv_layout.addRow(self.csv_y_label, self.y_list_widget) # Modificado
        
        self.csv_controls_widget.setLayout(csv_layout)
        
        # 4. Painel Dinâmico (StackedWidget)
        self.data_panel_stack = QStackedWidget()
        self.data_panel_stack.addWidget(self.tree_controls_widget) # Index 0
        self.data_panel_stack.addWidget(self.csv_controls_widget)  # Index 1
        
        data_layout_main.addWidget(self.data_panel_stack)
        data_group.setLayout(data_layout_main)
        
        layout.addWidget(data_group)
        self.setLayout(layout)
        
    @Slot()
    def add_series_item(self):
        self.series_tree.blockSignals(True)
        series_item = QTreeWidgetItem(self.series_tree)
        series_item.setText(0, f"Nova Série {self.series_tree.topLevelItemCount()}")
        series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsEditable)
        series_item.setFont(0, QFont("Arial", 10, QFont.Weight.Bold))
        default_color = QColor.fromHsv(np.random.randint(0, 359), 200, 200).name()
        series_item.setData(0, Qt.ItemDataRole.UserRole, default_color)
        series_item.setExpanded(True)
        self._add_point_to_series(series_item)
        color_btn = SeriesColorButton(series_item, self.on_change)
        self.series_tree.setItemWidget(series_item, 3, color_btn)
        self.series_tree.blockSignals(False)
        self._emit_change()

    @Slot()
    def add_data_point_item(self):
        selected_item = self.series_tree.currentItem()
        if not selected_item:
            self.add_series_item()
            return
        series_item = selected_item
        if selected_item.parent():
            series_item = selected_item.parent()
        self._add_point_to_series(series_item)
        self._emit_change()

    def _add_point_to_series(self, series_item):
        self.series_tree.blockSignals(True)
        current_point_count = series_item.childCount()
        point_item = QTreeWidgetItem(series_item)
        default_y = str(np.random.randint(5, 20))
        new_x = "1"
        if current_point_count > 0:
            try:
                last_item = series_item.child(current_point_count - 1)
                if last_item:
                    last_x = float(last_item.text(1))
                    new_x = str(int(last_x + 1))
                else: new_x = str(current_point_count + 1)
            except (ValueError, TypeError):
                new_x = str(current_point_count + 1)
        point_item.setText(0, f"Rótulo {current_point_count + 1}")
        point_item.setText(1, new_x)
        point_item.setText(2, default_y)
        point_item.setFlags(point_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.series_tree.blockSignals(False)

    @Slot()
    def remove_tree_item(self):
        selected_item = self.series_tree.currentItem()
        if not selected_item: return
        (selected_item.parent() or self.series_tree.invisibleRootItem()).removeChild(selected_item)
        self._emit_change()

    def _emit_change(self, *args):
        self.on_change() # <-- Isto chama o trigger_redraw()

    def _populate_csv_controls(self, df):
        self.x_col_cb.clear(); self.label_col_cb.clear()
        
        # --- MODIFICAÇÃO (v54 - Multi-Série) ---
        self.y_list_widget.clear()
        # --- FIM DA MODIFICAÇÃO ---
        
        if df is None: return
        columns = list(df.columns)
        self.x_col_cb.addItems(columns)
        self.label_col_cb.addItems(columns)
        
        # --- MODIFICAÇÃO (v54 - Multi-Série) ---
        # Popula o QListWidget com checkboxes
        for col in columns:
            item = QListWidgetItem(col)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.y_list_widget.addItem(item)
        # --- FIM DA MODIFICAÇÃO ---
    
    @Slot()
    def _on_dataset_changed(self, chart_type='Barras', settings_panel=None):
        dataset_name = self.dataset_cb.currentText()
        
        if dataset_name == 'Personalizado': self.data_panel_stack.setCurrentIndex(0)
        else: self.data_panel_stack.setCurrentIndex(1)

        # --- MODIFICAÇÃO (v54 - Lógica de visibilidade) ---
        is_categorical_x = (chart_type in ['Barras', 'Pizza'])
        is_xy_types = (chart_type in ['Linha', 'Dispersão'])
        is_multi_value = (chart_type in ['Histograma', 'Boxplot'])
        
        if settings_panel:
            is_pie = (chart_type == 'Pizza')
            is_bar = (chart_type == 'Barras')
            settings_panel.update_visibility(is_pie, is_bar, is_categorical_x, is_multi_value)
            
        # Visibilidade dos painéis de dados (CSV)
        self.csv_label_label.setVisible(is_categorical_x)
        self.label_col_cb.setVisible(is_categorical_x)
        
        self.csv_x_label.setVisible(is_xy_types)
        self.x_col_cb.setVisible(is_xy_types)
        
        self.csv_y_label.setVisible(True) # Sempre visível no modo CSV
        self.y_list_widget.setVisible(True)
        
        if is_multi_value:
            self.csv_y_label.setText("Colunas de Dados (Valores):")
        else:
            self.csv_y_label.setText("Colunas Y (Séries):")

        # Visibilidade dos cabeçalhos da árvore (Personalizado)
        if is_categorical_x: # Barras, Pizza
            self.series_tree.setHeaderLabels(["Rótulo X (Texto)", "(Ignorado)", "Valor Y (Numérico)", "Cor"])
        elif is_multi_value: # Histograma, Boxplot
            self.series_tree.setHeaderLabels(["Série", "Valores (Numérico)", "(Ignorado)", "Cor"])
            # Renomeia o cabeçalho X para "Valores"
            self.series_tree.headerItem().setText(1, "Valores (Numérico)")
        else: # Linha, Dispersão
            self.series_tree.setHeaderLabels(["Série", "Ponto X (Numérico)", "Ponto Y (Numérico)", "Cor"])
            self.series_tree.headerItem().setText(1, "Ponto X (Numérico)")
        # --- FIM DA MODIFICAÇÃO ---
        
        if dataset_name == 'CSV Carregado' and settings_panel:
            settings_panel.title_input.setText('Dados do CSV')

    @Slot()
    def _load_data_file(self): # Renomeado (v54)
        # --- MODIFICAÇÃO (v54 - Suporte a Excel) ---
        filter = "Arquivos de Dados (*.csv *.xlsx);;Arquivos CSV (*.csv);;Arquivos Excel (*.xlsx);;Todos os Arquivos (*)"
        path, _ = QFileDialog.getOpenFileName(self, 'Carregar Dados', filter=filter)
        if not path: return
        
        try:
            if path.lower().endswith('.csv'):
                self.df = pd.read_csv(path)
            elif path.lower().endswith('.xlsx'):
                self.df = pd.read_excel(path)
            else:
                raise ValueError("Formato de arquivo não suportado. Use .csv ou .xlsx")
                
            # --- FIM DA MODIFICAÇÃO ---
            
            self._populate_csv_controls(self.df)
            if self.dataset_cb.findText('CSV Carregado') == -1: self.dataset_cb.addItem('CSV Carregado')
            self.dataset_cb.setCurrentText('CSV Carregado')
            
            # Tenta adivinhar as colunas (Ex: 1ª texto, 2ª num, 3ª num)
            if len(self.df.columns) > 0: self.label_col_cb.setCurrentIndex(0)
            if len(self.df.columns) > 1: self.x_col_cb.setCurrentIndex(1)
            # Tenta marcar a 3ª coluna no Y-List
            if len(self.df.columns) > 2:
                item = self.y_list_widget.item(2)
                if item: item.setCheckState(Qt.CheckState.Checked)
            
        except Exception as e:
            QMessageBox.critical(self, 'Erro ao Carregar', f'Não foi possível ler o arquivo:\n{e}')
            self.df = None
            self.dataset_cb.setCurrentText('Personalizado')
            
    def get_state(self):
        series_data = []
        if self.dataset_cb.currentText() == 'Personalizado':
            root = self.series_tree.invisibleRootItem()
            for i in range(root.childCount()):
                series_item = root.child(i)
                label_data, x_data, y_data = [], [], []
                for j in range(series_item.childCount()):
                    point_item = series_item.child(j)
                    label_data.append(point_item.text(0))
                    x_data.append(point_item.text(1))
                    y_data.append(point_item.text(2))
                series_data.append({
                    'legend': series_item.text(0),
                    'color': series_item.data(0, Qt.ItemDataRole.UserRole),
                    'label_data': label_data, 'x_data': x_data, 'y_data': y_data
                })
        
        # --- MODIFICAÇÃO (v54 - Multi-Série) ---
        y_cols_selected = []
        for i in range(self.y_list_widget.count()):
            item = self.y_list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                y_cols_selected.append(item.text())
        # --- FIM DA MODIFICAÇÃO ---
                
        return {
            'dataset': self.dataset_cb.currentText(), 'df': self.df, 
            'series_data': series_data, 'label_col': self.label_col_cb.currentText(),
            'x_col': self.x_col_cb.currentText(), 
            'y_cols': y_cols_selected, # Modificado
        }
        
    def get_state_for_save(self):
        state = self.get_state()
        if state['df'] is not None: state['df_json'] = state['df'].to_json(orient='split')
        else: state['df_json'] = None
        del state['df'] 
        return state
        
    def set_state(self, state):
        try:
            self.blockSignals(True) 
            self.df = None
            df_json = state.get('df_json')
            if df_json:
                try:
                    self.df = pd.read_json(df_json, orient='split')
                    self._populate_csv_controls(self.df)
                except Exception as e:
                    print(f"Erro ao carregar DataFrame do JSON: {e}")
                    self.df = None
            self.label_col_cb.setCurrentText(state.get('label_col', ''))
            self.x_col_cb.setCurrentText(state.get('x_col', ''))
            
            # --- MODIFICAÇÃO (v54 - Multi-Série) ---
            # Define os itens checados no QListWidget
            y_cols_to_check = state.get('y_cols', [])
            self.y_list_widget.itemChanged.disconnect(self._emit_change) # Desconecta temporariamente
            for i in range(self.y_list_widget.count()):
                item = self.y_list_widget.item(i)
                if item.text() in y_cols_to_check:
                    item.setCheckState(Qt.CheckState.Checked)
                else:
                    item.setCheckState(Qt.CheckState.Unchecked)
            self.y_list_widget.itemChanged.connect(self._emit_change) # Reconecta
            # --- FIM DA MODIFICAÇÃO ---

            self.series_tree.clear()
            series_data_list = state.get('series_data', [])
            for series_data in series_data_list:
                series_item = QTreeWidgetItem(self.series_tree)
                series_item.setText(0, series_data.get('legend', 'Série'))
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsEditable)
                series_item.setFont(0, QFont("Arial", 10, QFont.Weight.Bold))
                color = series_data.get('color', '#000000')
                series_item.setData(0, Qt.ItemDataRole.UserRole, color)
                series_item.setExpanded(True)
                color_btn = SeriesColorButton(series_item, self.on_change)
                self.series_tree.setItemWidget(series_item, 3, color_btn)
                labels = series_data.get('label_data', []); xs = series_data.get('x_data', []); ys = series_data.get('y_data', [])
                max_len = max(len(labels), len(xs), len(ys))
                for i in range(max_len):
                    point_item = QTreeWidgetItem(series_item)
                    point_item.setText(0, labels[i] if i < len(labels) else '')
                    point_item.setText(1, xs[i] if i < len(xs) else '')
                    point_item.setText(2, ys[i] if i < len(ys) else '')
                    point_item.setFlags(point_item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.dataset_cb.setCurrentText(state.get('dataset', 'Personalizado'))
        finally:
            self.blockSignals(False)
            if self.dataset_cb.currentText() == 'Personalizado':
                 self._on_dataset_changed() 
            self.on_change()

# ---------------------------------------------------------------

# Estilo para compactar o painel de configurações
COMPACT_STYLESHEET = """
    SettingsPanel#ChartSettingsPanel {
        font-size: 12px;
    }
    SettingsPanel#ChartSettingsPanel QTabWidget::pane {
        border: none;
    }
    SettingsPanel#ChartSettingsPanel QTabBar::tab {
        padding: 5px 8px;
        font-size: 12px;
    }
    SettingsPanel#ChartSettingsPanel QLabel {
        font-size: 12px;
        padding-top: 2px; /* Espaçamento entre linhas do form */
    }
    SettingsPanel#ChartSettingsPanel QLineEdit,
    SettingsPanel#ChartSettingsPanel QComboBox {
        font-size: 12px;
        padding: 3px;
        min-height: 18px; /* Altura reduzida */
    }
    SettingsPanel#ChartSettingsPanel QSlider {
        min-height: 20px;
    }
    /* MODIFICAÇÃO (v54): Seletores de Largura/Altura */
    SettingsPanel#ChartSettingsPanel QLabel#FigureWidthLabel,
    SettingsPanel#ChartSettingsPanel QLabel#FigureHeightLabel {
        font-size: 12px;
        font-weight: bold;
        padding: 3px;
        min-width: 45px; /* Alinha o "pol" */
    }
    SettingsPanel#ChartSettingsPanel QToolButton {
        padding: 2px;
        min-width: 20px;
        min-height: 20px;
    }
    SettingsPanel#ChartSettingsPanel QCheckBox {
        font-size: 12px;
    }
    SettingsPanel#ChartSettingsPanel QPushButton {
        font-size: 12px;
        padding: 4px 8px;
    }
    /* Estilo para o novo GroupBox da Legenda */
    SettingsPanel#ChartSettingsPanel QGroupBox {
        font-size: 12px;
        font-weight: bold;
        margin-top: 6px;
    }
    SettingsPanel#ChartSettingsPanel QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
    }
"""

class SettingsPanel(QWidget):
    """Painel lateral (inspector) com abas para todas as configurações."""
    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change # Conectado ao trigger_redraw
        
        self.style_map_display_to_internal = {}
        for internal_name in sorted(plt.style.available):
            display_name = prettify_style_name(internal_name)
            if display_name and display_name not in self.style_map_display_to_internal:
                self.style_map_display_to_internal[display_name] = internal_name
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5) # Margens para o inspector
        
        self.tab_widget = QTabWidget()
        self._create_geral_tab()
        self._create_eixos_tab()
        self._create_estilo_tab()
        
        self.tab_widget.addTab(self.tab_geral, "Geral")
        self.tab_widget.addTab(self.tab_eixos, "Eixos")
        self.tab_widget.addTab(self.tab_estilo, "Estilo e Legenda")
        
        main_layout.addWidget(self.tab_widget)
        
        controls_layout = QHBoxLayout()
        self.live_cb = QCheckBox('Pré-visualização em tempo real')
        self.live_cb.setChecked(True)
        self.live_cb.stateChanged.connect(self._emit_change)
        
        self.update_btn = QPushButton('Atualizar') # Texto menor
        self.update_btn.clicked.connect(self.on_change) # Conecta direto no redraw
        
        controls_layout.addWidget(self.live_cb)
        controls_layout.addStretch()
        controls_layout.addWidget(self.update_btn)
        main_layout.addLayout(controls_layout)
        
        self.setLayout(main_layout)
        
        # Aplica o estilo compacto
        self.setObjectName("ChartSettingsPanel")
        self.setStyleSheet(COMPACT_STYLESHEET)

    def _create_geral_tab(self):
        """Cria os widgets da primeira aba 'Geral'."""
        self.tab_geral = QWidget()
        layout = QFormLayout(self.tab_geral)
        
        self.type_cb = QComboBox()
        self.type_cb.addItems(['Barras', 'Linha', 'Dispersão', 'Pizza', 'Histograma', 'Boxplot'])
        layout.addRow('Tipo:', self.type_cb)

        self.title_input = QLineEdit()
        self.title_input.textChanged.connect(self._emit_change)
        layout.addRow('Título (Legenda):', self.title_input)

        self.xlabel_input = QLineEdit()
        self.xlabel_input.textChanged.connect(self._emit_change)
        self.xlabel_label = QLabel('Rótulo Eixo X:')
        layout.addRow(self.xlabel_label, self.xlabel_input)
        
        self.ylabel_input = QLineEdit()
        self.ylabel_input.textChanged.connect(self._emit_change)
        self.ylabel_label = QLabel('Rótulo Eixo Y:')
        layout.addRow(self.ylabel_label, self.ylabel_input)
        
        self.source_input = QLineEdit() 
        self.source_input.textChanged.connect(self._emit_change)
        layout.addRow('Fonte (ABNT):', self.source_input)
        
        self.largura_docx_combo = QComboBox()
        self.largura_docx_combo.addItems(["Pequena (8 cm)", "Média (12 cm)", "Grande (Largura Máxima)"])
        layout.addRow("Largura (DOCX):", self.largura_docx_combo)
        
        # --- MODIFICAÇÃO (v54 - Slider de Largura) ---
        slider_layout_w = QHBoxLayout()
        slider_layout_w.setContentsMargins(0, 0, 0, 0)
        
        self.figure_width_slider = QSlider(Qt.Orientation.Horizontal)
        self.figure_width_slider.setMinimum(50)  # 5.0 polegadas * 10
        self.figure_width_slider.setMaximum(150) # 15.0 polegadas * 10
        self.figure_width_slider.setValue(80)    # 8.0 polegadas * 10
        self.figure_width_slider.setSingleStep(5) # 0.5 polegadas
        self.figure_width_slider.setTickInterval(10) # 1.0 polegadas
        self.figure_width_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        self.figure_width_label = QLabel("8.0 pol")
        self.figure_width_label.setObjectName("FigureWidthLabel")
        
        self.figure_width_reset_btn = QToolButton()
        self.figure_width_reset_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        self.figure_width_reset_btn.setToolTip("Redefinir para 8.0 polegadas")
        
        slider_layout_w.addWidget(self.figure_width_slider)
        slider_layout_w.addWidget(self.figure_width_label)
        slider_layout_w.addWidget(self.figure_width_reset_btn)
        
        self.figure_width_slider.valueChanged.connect(self._on_width_slider_value_changed)
        self.figure_width_slider.sliderReleased.connect(self._on_width_slider_released)
        self.figure_width_reset_btn.clicked.connect(self._on_width_slider_reset)

        layout.addRow("Largura (Prévia):", slider_layout_w)
        # --- FIM DA MODIFICAÇÃO (v54) ---

        # --- INÍCIO DA MODIFICAÇÃO (v54 - Slider de Altura) ---
        slider_layout_h = QHBoxLayout()
        slider_layout_h.setContentsMargins(0, 0, 0, 0)
        
        self.figure_height_slider = QSlider(Qt.Orientation.Horizontal)
        self.figure_height_slider.setMinimum(30)  # 3.0 polegadas * 10
        self.figure_height_slider.setMaximum(120) # 12.0 polegadas * 10
        self.figure_height_slider.setValue(50)    # 5.0 polegadas * 10
        self.figure_height_slider.setSingleStep(5)
        self.figure_height_slider.setTickInterval(10)
        self.figure_height_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        
        self.figure_height_label = QLabel("5.0 pol")
        self.figure_height_label.setObjectName("FigureHeightLabel")
        
        self.figure_height_reset_btn = QToolButton()
        self.figure_height_reset_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogResetButton))
        self.figure_height_reset_btn.setToolTip("Redefinir para 5.0 polegadas")
        
        slider_layout_h.addWidget(self.figure_height_slider)
        slider_layout_h.addWidget(self.figure_height_label)
        slider_layout_h.addWidget(self.figure_height_reset_btn)
        
        self.figure_height_slider.valueChanged.connect(self._on_height_slider_value_changed)
        self.figure_height_slider.sliderReleased.connect(self._on_height_slider_released)
        self.figure_height_reset_btn.clicked.connect(self._on_height_slider_reset)
        
        layout.addRow("Altura (Prévia):", slider_layout_h)
        # --- FIM DA MODIFICAÇÃO (v54) ---

    def _create_eixos_tab(self):
        """Cria os widgets da segunda aba 'Eixos'."""
        self.tab_eixos = QWidget()
        layout = QFormLayout(self.tab_eixos)

        # Layout vertical para os limites
        self.x_min_label = QLabel("X Mín:")
        self.x_min_input = QLineEdit()
        self.x_min_input.textChanged.connect(self._emit_change)
        layout.addRow(self.x_min_label, self.x_min_input)

        self.x_max_label = QLabel("X Máx:")
        self.x_max_input = QLineEdit()
        self.x_max_input.textChanged.connect(self._emit_change)
        layout.addRow(self.x_max_label, self.x_max_input)

        self.y_min_label = QLabel("Y Mín:")
        self.y_min_input = QLineEdit()
        self.y_min_input.textChanged.connect(self._emit_change)
        layout.addRow(self.y_min_label, self.y_min_input)

        self.y_max_label = QLabel("Y Máx:")
        self.y_max_input = QLineEdit()
        self.y_max_input.textChanged.connect(self._emit_change)
        layout.addRow(self.y_max_label, self.y_max_input)

        self.x_interval_label = QLabel("Intervalo Eixo X:")
        self.x_tick_interval_input = QLineEdit()
        self.x_tick_interval_input.setPlaceholderText("Auto (ex: 0.1)")
        self.x_tick_interval_input.textChanged.connect(self._emit_change)
        layout.addRow(self.x_interval_label, self.x_tick_interval_input)
        
        self.y_interval_label = QLabel("Intervalo Eixo Y:")
        self.y_tick_interval_input = QLineEdit()
        self.y_tick_interval_input.setPlaceholderText("Auto (ex: 5)")
        self.y_tick_interval_input.textChanged.connect(self._emit_change)
        layout.addRow(self.y_interval_label, self.y_tick_interval_input)

    def _create_estilo_tab(self):
        """Cria os widgets da terceira aba 'Estilo'."""
        self.tab_estilo = QWidget()
        layout = QFormLayout(self.tab_estilo)

        self.style_cb = QComboBox()
        self.style_cb.addItems(sorted(self.style_map_display_to_internal.keys()))
        self.style_cb.setCurrentText('Classic')
        self.style_cb.currentIndexChanged.connect(self._emit_change)
        layout.addRow('Estilo:', self.style_cb)
        
        self.bar_align_cb = QComboBox()
        self.bar_align_cb.addItems(BAR_ALIGN_MAP.keys())
        self.bar_align_cb.currentIndexChanged.connect(self._emit_change)
        self.bar_align_label = QLabel("Alinhamento da Barra:")
        layout.addRow(self.bar_align_label, self.bar_align_cb)

        self.show_legend_cb = QCheckBox("Mostrar Legenda")
        self.show_legend_cb.setChecked(True)
        self.show_legend_cb.stateChanged.connect(self._emit_change)
        layout.addRow(self.show_legend_cb)
        
        # --- Lógica dos 3 Seletores de Legenda (v44) ---
        legend_group = QGroupBox("Posicionamento da Legenda")
        legend_layout = QFormLayout(legend_group)
        legend_layout.setContentsMargins(5, 10, 5, 5)
        
        self.legend_type_cb = QComboBox()
        self.legend_type_cb.addItems(["Automático", "Dentro do Gráfico", "Fora do Gráfico"])
        
        self.legend_pos_cb = QComboBox()
        self.legend_pos_cb.addItems(["Automático", "Superior", "Inferior", "Esquerda", "Direita", "Centro"])
        
        self.legend_align_cb = QComboBox()
        self.legend_align_cb.addItems(["Automático", "Esquerda", "Direita", "Centro", "Superior", "Inferior"])
        
        legend_layout.addRow("Local:", self.legend_type_cb)
        legend_layout.addRow("Posição:", self.legend_pos_cb)
        legend_layout.addRow("Alinhamento:", self.legend_align_cb)
        
        layout.addRow(legend_group)
        
        self.legend_type_cb.currentTextChanged.connect(self._update_legend_visibility)
        self.legend_pos_cb.currentTextChanged.connect(self._emit_change)
        self.legend_align_cb.currentTextChanged.connect(self._emit_change)
        # --- Fim da Lógica (v44) ---

        self.legend_size_cb = QComboBox()
        self.legend_size_cb.addItems(LEGEND_SIZE_MAP.keys())
        self.legend_size_cb.setCurrentText("Média")
        self.legend_size_cb.currentIndexChanged.connect(self._emit_change)
        self.legend_size_label = QLabel("Tamanho da Legenda:")
        layout.addRow(self.legend_size_label, self.legend_size_cb)
        
        self.show_data_labels_cb = QCheckBox("Mostrar Rótulos de Dados (Valores)")
        self.show_data_labels_cb.stateChanged.connect(self._emit_change)
        layout.addRow(self.show_data_labels_cb)
        
        self._update_legend_visibility()

    # --- MODIFICAÇÃO (v54): Handlers para sliders de Largura e Altura ---
    @Slot(int)
    def _on_width_slider_value_changed(self, value):
        float_val = value / 10.0
        self.figure_width_label.setText(f"{float_val:.1f} pol")
    
    @Slot()
    def _on_width_slider_released(self):
        self._emit_change()
        
    @Slot()
    def _on_width_slider_reset(self):
        self.figure_width_slider.setValue(80) # Padrão 8.0
        self._emit_change()

    @Slot(int)
    def _on_height_slider_value_changed(self, value):
        float_val = value / 10.0
        self.figure_height_label.setText(f"{float_val:.1f} pol")
    
    @Slot()
    def _on_height_slider_released(self):
        self._emit_change()
        
    @Slot()
    def _on_height_slider_reset(self):
        self.figure_height_slider.setValue(50) # Padrão 5.0
        self._emit_change()
    # --- FIM DA MODIFICAÇÃO (v54) ---
    
    @Slot()
    def _emit_change(self, *args):
        if hasattr(self, 'live_cb') and self.live_cb.isChecked(): 
            self.on_change() # <-- Isto chama o trigger_redraw()

    @Slot()
    def _update_legend_visibility(self):
        """Desabilita Posição/Alinhamento se o Local for 'Automático'."""
        is_auto = (self.legend_type_cb.currentText() == "Automático")
        self.legend_pos_cb.setEnabled(not is_auto)
        self.legend_align_cb.setEnabled(not is_auto)
        self._emit_change() # Aciona o redraw

    def _compute_legend_pos(self, type: str, pos: str, align: str) -> tuple[str, tuple | None]:
        """
        A "matriz de decisão" que converte as 3 opções
        de legenda em comandos 'loc' e 'bbox' para o Matplotlib.
        """
        if type == 'Automático':
            return ('best', None)
        
        if type == 'Dentro do Gráfico':
            loc_map = {
                ('Superior', 'Esquerda'): 'upper left', ('Superior', 'Centro'): 'upper center', ('Superior', 'Direita'): 'upper right',
                ('Inferior', 'Esquerda'): 'lower left', ('Inferior', 'Centro'): 'lower center', ('Inferior', 'Direita'): 'lower right',
                ('Esquerda', 'Superior'): 'upper left', ('Esquerda', 'Centro'): 'center left', ('Esquerda', 'Inferior'): 'lower left',
                ('Direita', 'Superior'): 'upper right', ('Direita', 'Centro'): 'center right', ('Direita', 'Inferior'): 'lower right',
                ('Centro', 'Centro'): 'center',
            }
            return (loc_map.get((pos, align), 'best'), None)
            
        if type == 'Fora do Gráfico':
            bbox_map = {
                ('Direita', 'Superior'): ('upper left', (1.02, 1.0)), ('Direita', 'Centro'): ('center left', (1.02, 0.5)), ('Direita', 'Inferior'): ('lower left', (1.02, 0.0)),
                ('Esquerda', 'Superior'): ('upper right', (-0.02, 1.0)), ('Esquerda', 'Centro'): ('center right', (-0.02, 0.5)), ('Esquerda', 'Inferior'): ('lower right', (-0.02, 0.0)),
                ('Superior', 'Esquerda'): ('lower left', (0.0, 1.05)), ('Superior', 'Centro'): ('lower center', (0.5, 1.05)), ('Superior', 'Direita'): ('lower right', (1.0, 1.05)),
                ('Inferior', 'Esquerda'): ('upper left', (0.0, -0.15)), ('Inferior', 'Centro'): ('upper center', (0.5, -0.15)), ('Inferior', 'Direita'): ('upper right', (1.0, -0.15)),
            }
            return bbox_map.get((pos, align), ('center left', (1.02, 0.5)))
            
        return ('best', None) # Fallback final

    def _reverse_map_legend_pos(self, key: str) -> tuple[str, str, str]:
        """Converte a chave de legenda do formato antigo (v37-v43) para o novo (v44)."""
        key_map = {
            'Automático': ('Automático', 'Automático', 'Automático'),
            'Superior Direito': ('Dentro do Gráfico', 'Superior', 'Direita'),
            'Superior Esquerdo': ('Dentro do Gráfico', 'Superior', 'Esquerda'),
            'Inferior Direito': ('Dentro do Gráfico', 'Inferior', 'Direita'),
            'Inferior Esquerdo': ('Dentro do Gráfico', 'Inferior', 'Esquerda'),
            'Centro': ('Dentro do Gráfico', 'Centro', 'Centro'),
            'Fora: Direita - Cima': ('Fora do Gráfico', 'Direita', 'Superior'),
            'Fora: Direita - Meio': ('Fora do Gráfico', 'Direita', 'Centro'),
            'Fora: Direita - Baixo': ('Fora do Gráfico', 'Direita', 'Inferior'),
            'Fora: Esquerda - Cima': ('Fora do Gráfico', 'Esquerda', 'Superior'),
            'Fora: Esquerda - Meio': ('Fora do Gráfico', 'Esquerda', 'Centro'),
            'Fora: Esquerda - Baixo': ('Fora do Gráfico', 'Esquerda', 'Inferior'),
            'Fora: Cima - Esquerda': ('Fora do Gráfico', 'Superior', 'Esquerda'),
            'Fora: Cima - Meio': ('Fora do Gráfico', 'Superior', 'Centro'),
            'Fora: Cima - Direita': ('Fora do Gráfico', 'Superior', 'Direita'),
            'Fora: Baixo - Esquerda': ('Fora do Gráfico', 'Inferior', 'Esquerda'),
            'Fora: Baixo - Meio': ('Fora do Gráfico', 'Inferior', 'Centro'),
            'Fora: Baixo - Direita': ('Fora do Gráfico', 'Inferior', 'Direita'),
        }
        return key_map.get(key, ('Automático', 'Automático', 'Automático'))

    def update_visibility(self, is_pie, is_bar, is_categorical_x, is_multi_value):
        """Atualiza a visibilidade dos controles com base no tipo de gráfico."""
        
        self.xlabel_input.setVisible(not is_pie); self.ylabel_input.setVisible(not is_pie)
        self.xlabel_label.setVisible(not is_pie); self.ylabel_label.setVisible(not is_pie)
        
        show_x_limits_and_interval = not (is_categorical_x or is_multi_value or is_pie)
        
        self.x_min_label.setVisible(show_x_limits_and_interval)
        self.x_min_input.setVisible(show_x_limits_and_interval)
        self.x_max_label.setVisible(show_x_limits_and_interval)
        self.x_max_input.setVisible(show_x_limits_and_interval)
        
        self.y_min_label.setVisible(not is_pie and not is_multi_value)
        self.y_min_input.setVisible(not is_pie and not is_multi_value)
        self.y_max_label.setVisible(not is_pie and not is_multi_value)
        self.y_max_input.setVisible(not is_pie and not is_multi_value)
        
        self.x_interval_label.setVisible(show_x_limits_and_interval)
        self.x_tick_interval_input.setVisible(show_x_limits_and_interval)
        self.y_interval_label.setVisible(not is_pie and not is_multi_value)
        self.y_tick_interval_input.setVisible(not is_pie and not is_multi_value)
        
        show_legend = (not is_pie) # Hist/Boxplot agora podem ter legenda
        self.show_legend_cb.setVisible(show_legend)
        self.legend_type_cb.parentWidget().setVisible(show_legend) # O GroupBox
        self.legend_size_cb.setVisible(show_legend)
        self.legend_size_label.setVisible(show_legend)
        self.bar_align_cb.setVisible(is_bar); self.bar_align_label.setVisible(is_bar)
        
    def get_state(self):
        """Retorna o estado APENAS dos controles de configurações."""
        display_name = self.style_cb.currentText()
        internal_style = self.style_map_display_to_internal.get(display_name, 'classic')
        
        largura_cm = 16.0 # Padrão
        largura_str = self.largura_docx_combo.currentText()
        if "Pequena" in largura_str: largura_cm = 8.0
        elif "Média" in largura_str: largura_cm = 12.0

        # --- MODIFICAÇÃO (v54 - Altura) ---
        figure_width_inches = self.figure_width_slider.value() / 10.0
        figure_height_inches = self.figure_height_slider.value() / 10.0
        # --- FIM DA MODIFICAÇÃO ---

        return {
            'type': self.type_cb.currentText(), 'title': self.title_input.text(),
            'xlabel': self.xlabel_input.text(), 'ylabel': self.ylabel_input.text(),
            'source': self.source_input.text(), 'style': internal_style,
            'show_legend': self.show_legend_cb.isChecked(),
            'legend_type': self.legend_type_cb.currentText(),
            'legend_pos_main': self.legend_pos_cb.currentText(),
            'legend_align': self.legend_align_cb.currentText(),
            'legend_size': self.legend_size_cb.currentText(), 'bar_align': self.bar_align_cb.currentText(),
            'show_data_labels': self.show_data_labels_cb.isChecked(),
            'x_min': parse_axis_limit(self.x_min_input.text()), 'x_max': parse_axis_limit(self.x_max_input.text()),
            'y_min': parse_axis_limit(self.y_min_input.text()), 'y_max': parse_axis_limit(self.y_max_input.text()),
            'x_interval': parse_axis_limit(self.x_tick_interval_input.text()),
            'y_interval': parse_axis_limit(self.y_tick_interval_input.text()),
            'live': self.live_cb.isChecked(),
            'largura_cm': largura_cm,
            'figure_width_inches': figure_width_inches,
            'figure_height_inches': figure_height_inches, # Adicionado
        }
        
    def set_state(self, state):
        """Define o estado dos controles de configurações com base em um dicionário."""
        
        self.type_cb.setCurrentText(state.get('type', 'Barras'))
        self.title_input.setText(state.get('title', ''))
        self.xlabel_input.setText(state.get('xlabel', ''))
        self.ylabel_input.setText(state.get('ylabel', ''))
        self.source_input.setText(state.get('source', ''))
        
        self.x_min_input.setText(str(state.get('x_min', '')) if state.get('x_min') is not None else '')
        self.x_max_input.setText(str(state.get('x_max', '')) if state.get('x_max') is not None else '')
        self.y_min_input.setText(str(state.get('y_min', '')) if state.get('y_min') is not None else '')
        self.y_max_input.setText(str(state.get('y_max', '')) if state.get('y_max') is not None else '')
        self.x_tick_interval_input.setText(str(state.get('x_interval', '')) if state.get('x_interval') is not None else '')
        self.y_tick_interval_input.setText(str(state.get('y_interval', '')) if state.get('y_interval') is not None else '')

        self.show_legend_cb.setChecked(state.get('show_legend', True))
        
        # Lógica de migração/carregamento da legenda
        if 'legend_type' in state: # Novo formato (v44+)
            self.legend_type_cb.setCurrentText(state.get('legend_type', 'Automático'))
            self.legend_pos_cb.setCurrentText(state.get('legend_pos_main', 'Automático'))
            self.legend_align_cb.setCurrentText(state.get('legend_align', 'Automático'))
        elif 'legend_pos' in state: # Formato antigo (v37-v43)
            saved_pos_key = state.get('legend_pos', 'Automático')
            tipo, pos, align = self._reverse_map_legend_pos(saved_pos_key)
            self.legend_type_cb.setCurrentText(tipo)
            self.legend_pos_cb.setCurrentText(pos)
            self.legend_align_cb.setCurrentText(align)
        
        self._update_legend_visibility() # Atualiza o estado habilitado/desabilitado
        
        self.legend_size_cb.setCurrentText(state.get('legend_size', 'Média'))
        self.bar_align_cb.setCurrentText(state.get('bar_align', 'Centro'))
        self.show_data_labels_cb.setChecked(state.get('show_data_labels', False))
        
        internal_style = state.get('style', 'classic')
        display_name_to_set = 'Classic' 
        for display, internal in self.style_map_display_to_internal.items():
            if internal == internal_style:
                display_name_to_set = display; break
        self.style_cb.setCurrentText(display_name_to_set)

        self.live_cb.setChecked(state.get('live', True))
        
        largura_cm = state.get('largura_cm', 16.0)
        if largura_cm == 8.0: self.largura_docx_combo.setCurrentIndex(0)
        elif largura_cm == 12.0: self.largura_docx_combo.setCurrentIndex(1)
        else: self.largura_docx_combo.setCurrentIndex(2)
        
        # --- MODIFICAÇÃO (v54 - Altura) ---
        figure_width_inches = state.get('figure_width_inches', 8.0)
        slider_val_w = int(max(5.0, figure_width_inches) * 10)
        self.figure_width_slider.setValue(slider_val_w)
        self.figure_width_label.setText(f"{slider_val_w / 10.0:.1f} pol")
        
        figure_height_inches = state.get('figure_height_inches', 5.0)
        slider_val_h = int(max(3.0, figure_height_inches) * 10)
        self.figure_height_slider.setValue(slider_val_h)
        self.figure_height_label.setText(f"{slider_val_h / 10.0:.1f} pol")
        # --- FIM DA MODIFICAÇÃO (v54) ---
        
# ---------------------------------------------------------------
# --- CLASSE PRINCIPAL: ChartDialog (QDialog) ---
# ---------------------------------------------------------------

class ChartDialog(QDialog):
    
    def __init__(self, grafico: Grafico = None, banco_graficos: list[Grafico] = None, is_dark: bool = False, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Gráfico (Matplotlib)")
        self.resize(1400, 800) 
        self.setMinimumSize(1200, 750)
        
        self.grafico_original_para_edicao = grafico
        self.grafico_final = grafico if grafico else Grafico()
        self.banco_graficos = banco_graficos if banco_graficos else []

        self.is_dark = is_dark 
        self.ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icons")

        main_layout = QVBoxLayout(self) 
        
        self.fig = None 
        self.canvas = None
        self.toolbar = None
        
        # --- INÍCIO DA MODIFICAÇÃO (v46) ---
        # Cria o timer de debouncing
        self.redraw_timer = QtCore.QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(500) # 500ms de atraso
        self.redraw_timer.timeout.connect(self.redraw)
        
        # Passa o 'trigger_redraw' para os painéis,
        # mas o botão 'Atualizar' se conecta diretamente ao 'redraw'.
        self.settings_panel = SettingsPanel(self.trigger_redraw)
        self.data_panel = DataSourcePanel(self.trigger_redraw, self.is_dark, self.ICON_PATH)
        self.settings_panel.update_btn.clicked.connect(self.redraw) # Força redraw
        # --- FIM DA MODIFICAÇÃO (v46) ---
        
        # Conexões
        self.settings_panel.type_cb.currentIndexChanged.connect(self._on_chart_type_changed)
        self.data_panel.dataset_cb.currentIndexChanged.connect(self._on_dataset_type_changed)
        
        # --- MODIFICAÇÃO (v54): Conecta ambos os sliders ---
        self.settings_panel.figure_width_slider.sliderReleased.connect(self.trigger_redraw)
        self.settings_panel.figure_height_slider.sliderReleased.connect(self.trigger_redraw)
        # --- FIM DA MODIFICAÇÃO ---

        self.settings_panel.legend_type_cb.currentTextChanged.connect(self.trigger_redraw)
        self.settings_panel.legend_pos_cb.currentTextChanged.connect(self.trigger_redraw)
        self.settings_panel.legend_align_cb.currentTextChanged.connect(self.trigger_redraw)


        # Layout de 3 painéis
        self.h_splitter = QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        
        # Painel 1: Dados (Esquerda)
        self.data_panel.setFixedWidth(450) 
        self.h_splitter.addWidget(self.data_panel)
        
        # Painel 2: Pré-visualização (Centro)
        self.preview_widget = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(0,0,0,0)
        self.h_splitter.addWidget(self.preview_widget)
        
        # Painel 3: Configurações (Direita - "Inspector")
        self.settings_panel.setFixedWidth(260) 
        self.settings_panel.tab_widget.setStyleSheet("QTabWidget::pane { border: none; }")
        self.h_splitter.addWidget(self.settings_panel) 
        
        self.h_splitter.setSizes([450, 690, 260]) 
        
        main_layout.addWidget(self.h_splitter, 1) 

        # --- Botões OK/Cancelar ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept) 
        self.buttons.rejected.connect(self.reject)
        
        # --- INÍCIO DA MODIFICAÇÃO (v55 - Correção de "Crash") ---
        # Impede que a tecla "Enter" (usada na entrada de dados)
        # acione acidentalmente o botão "OK", fechando o diálogo.
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setAutoDefault(False)
        ok_button.setDefault(False)
        # --- FIM DA MODIFICAÇÃO ---

        main_layout.addWidget(self.buttons)

        self._carregar_dados_iniciais()
        
        self.redraw()

    def _carregar_dados_iniciais(self):
        """Carrega os dados de um 'Grafico' existente no editor."""
        
        if not self.grafico_original_para_edicao:
            self.settings_panel.largura_docx_combo.setCurrentText("Média (12 cm)")
            return
            
        grafico = self.grafico_original_para_edicao
        
        if grafico.caminho_dados_json and os.path.exists(grafico.caminho_dados_json):
            try:
                with open(grafico.caminho_dados_json, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                self.settings_panel.set_state(state_data)
                self.data_panel.set_state(state_data) 
                
            except Exception as e:
                QMessageBox.warning(self, "Erro ao Carregar Dados",
                                    f"Não foi possível carregar os dados do gráfico salvo:\n{e}\n\O editor começará com os padrões.")
        
        self.settings_panel.title_input.setText(grafico.titulo)
        self.settings_panel.source_input.setText(grafico.fonte)
        
        if grafico.largura_cm == 8.0: self.settings_panel.largura_docx_combo.setCurrentIndex(0)
        elif grafico.largura_cm == 12.0: self.settings_panel.largura_docx_combo.setCurrentIndex(1)
        else: self.settings_panel.largura_docx_combo.setCurrentIndex(2) 

    # --- INÍCIO DA MODIFICAÇÃO (v46) ---
    @Slot()
    def trigger_redraw(self):
        """Aciona um redraw "debounced" (atrasado)."""
        if self.settings_panel.live_cb.isChecked():
            self.redraw_timer.start() # Reinicia o timer
    # --- FIM DA MODIFICAÇÃO (v46) ---

    @Slot()
    def _on_chart_type_changed(self):
        """Quando o TIPO de gráfico muda, atualiza a visibilidade do painel de dados."""
        self.data_panel._on_dataset_changed(
            chart_type=self.settings_panel.type_cb.currentText(),
            settings_panel=self.settings_panel
        )
        self.trigger_redraw() # <-- Usa o trigger
        
    @Slot()
    def _on_dataset_type_changed(self):
        """Quando a FONTE de dados muda, atualiza a visibilidade do painel de dados."""
        self.data_panel._on_dataset_changed(
            chart_type=self.settings_panel.type_cb.currentText(),
            settings_panel=self.settings_panel
        )
        self.trigger_redraw() # <-- Usa o trigger

    # --- Lógica de Plotagem (v45) ---
    
    # --- INÍCIO DA MODIFICAÇÃO (v54 - Multi-Série CSV) ---
    def _plot_csv_data(self, ax, s):
        plot_type = s['type']; df = s['df']; y_cols = s['y_cols']
        
        if not y_cols:
            raise ValueError("Nenhuma coluna de dados (Y) foi selecionada.")

        if plot_type in ['Linha', 'Dispersão']:
            x = df[s['x_col']]
            for y_col in y_cols:
                y = df[y_col]
                if plot_type == 'Linha':
                    ax.plot(x, y, label=y_col)
                else:
                    ax.scatter(x, y, label=y_col)
                if s['show_data_labels']:
                    for xi, yi in zip(x, y): ax.text(xi, yi, f' {yi:.2f}', va='bottom', fontsize=8)

        elif plot_type == 'Barras':
            x_labels = df[s['label_col']]
            num_series = len(y_cols)
            x_pos = np.arange(len(x_labels))
            align_val = BAR_ALIGN_MAP.get(s['bar_align'], 'center')
            
            if align_val == 'edge':
                # No modo 'edge', o matplotlib espera uma largura negativa
                # para agrupar à esquerda, o que é complexo.
                # Simulamos 'edge' tratando-o como 'center' com offsets.
                align_val = 'center'

            if num_series == 1:
                y_values = df[y_cols[0]]
                bars = ax.bar(x_labels, y_values, label=y_cols[0], align=align_val)
                if s['show_data_labels']:
                    ax.bar_label(bars, fmt='%.2f', padding=3, fontsize=8)
            else:
                total_width = 0.8; bar_width = total_width / num_series
                for i, y_col in enumerate(y_cols):
                    y_values = df[y_col]
                    offset = (i - (num_series - 1) / 2) * bar_width
                    bars = ax.bar(x_pos + offset, y_values, width=bar_width, label=y_col)
                    if s['show_data_labels']:
                        labels_for_bars = [f'{v:.2f}' if v != 0 else '' for v in y_values]
                        ax.bar_label(bars, labels=labels_for_bars, padding=3, fontsize=8)
                if len(x_labels): ax.set_xticks(x_pos, x_labels)

        elif plot_type in ['Histograma', 'Boxplot']:
            data_to_plot = [df[y_col].dropna() for y_col in y_cols]
            if not data_to_plot:
                raise ValueError("Colunas selecionadas não contêm dados numéricos.")
            
            if plot_type == 'Histograma':
                for i, y_col in enumerate(y_cols):
                    ax.hist(data_to_plot[i], bins=15, edgecolor='k', label=y_col, alpha=0.7)
            else: # Boxplot
                bp = ax.boxplot(data_to_plot, patch_artist=True)
                ax.set_xticklabels(y_cols)
                
                # --- INÍCIO DA CORREÇÃO ---
                # Tenta colorir as caixas (opcional)
                # MODIFICADO: Usa a API orientada a objetos (colormaps) em vez do plt.cm
                cmap = colormaps.get_cmap('Pastel1') 
                colors = cmap(np.linspace(0, 1, len(y_cols)))
                for patch, color in zip(bp['boxes'], colors):
                # --- FIM DA CORREÇÃO ---
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                        
        elif plot_type == 'Pizza':
            x_labels = df[s['label_col']]
            y_col = y_cols[0]
            if len(y_cols) > 1:
                # Adiciona aviso ao título se múltiplas colunas foram selecionadas
                s['title'] += f" (mostrando apenas '{y_col}')"
                ax.set_title(s['title'], fontsize=12) # Re-aplica o título
                
            y = df[y_col]
            if any(v < 0 for v in y): raise ValueError("Gráfico de Pizza não aceita valores negativos")
            
            wedges, texts, autotexts = ax.pie(y, labels=x_labels, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 8})
            if not s['show_data_labels']:
                for t in autotexts: t.set_visible(False)
            ax.axis('equal')
            
    def _plot_custom_data(self, ax, s):
        series_list = s['series_data']; plot_type = s['type']
        if not series_list:
            ax.text(0.5, 0.5, 'Clique em "Adicionar Série (+)" para começar', ha='center', va='center', fontsize=10)
            return
        if plot_type == 'Barras':
            all_x_labels = []; all_series_parsed = []
            for series in series_list:
                labels = series['label_data']; 
                try: values = [float(v) for v in series['y_data']] 
                except ValueError as e: raise ValueError(f"Valor Y inválido na série '{series['legend']}': '{e.args[0]}'")
                if len(labels) != len(values): raise ValueError(f"Série '{series['legend']}' tem X ({len(labels)}) e Y ({len(values)}) de tamanhos diferentes")
                all_series_parsed.append({'series': series, 'data': dict(zip(labels, values))})
                for label in labels:
                    if label not in all_x_labels: all_x_labels.append(label)
            num_series = len(series_list)
            if num_series == 1:
                align_val = BAR_ALIGN_MAP.get(s['bar_align'], 'center')
                parsed = all_series_parsed[0]; series = parsed['series']
                y_values = [parsed['data'].get(label, 0) for label in all_x_labels]
                bars = ax.bar(all_x_labels, y_values, label=series['legend'], color=series['color'], align=align_val)
                if s['show_data_labels']:
                    labels_for_bars = [f'{v:.2f}' if v != 0 else '' for v in y_values]
                    ax.bar_label(bars, labels=labels_for_bars, padding=3, fontsize=8)
            else:
                x_pos = np.arange(len(all_x_labels)); total_width = 0.8; bar_width = total_width / num_series
                for i, parsed in enumerate(all_series_parsed):
                    series = parsed['series']; data_dict = parsed['data']
                    y_values = [data_dict.get(label, 0) for label in all_x_labels]
                    offset = (i - (num_series - 1) / 2) * bar_width
                    bars = ax.bar(x_pos + offset, y_values, width=bar_width, label=series['legend'], color=series['color'])
                    if s['show_data_labels']:
                        labels_for_bars = [f'{v:.2f}' if v != 0 else '' for v in y_values]
                        ax.bar_label(bars, labels=labels_for_bars, padding=3, fontsize=8)
                if all_x_labels: ax.set_xticks(x_pos, all_x_labels)
        else:
            all_series_legends = [] 
            data_to_plot = [] # Para Boxplot
            
            for i, series in enumerate(series_list):
                legend = series['legend']; color = series['color']
                if plot_type in ['Linha', 'Dispersão']:
                    try: x = [float(p) for p in series['x_data']]; y = [float(p) for p in series['y_data']] 
                    except ValueError as e: raise ValueError(f"Valor X/Y inválido na série '{legend}'. Todos os pontos devem ser numéricos. (Erro: {e})")
                    if len(x) != len(y): raise ValueError(f"Série '{legend}' tem X ({len(x)}) e Y ({len(y)}) de tamanhos diferentes")
                    if plot_type == 'Linha': ax.plot(x, y, label=legend, color=color)
                    else: ax.scatter(x, y, label=legend, color=color)
                    if s['show_data_labels']:
                        for xi, yi in zip(x, y): ax.text(xi, yi, f' {yi:.2f}', va='bottom', fontsize=8)
                elif plot_type in ['Histograma', 'Boxplot']:
                    try: x = [float(p) for p in series['x_data']] 
                    except ValueError as e: raise ValueError(f"Valor X inválido na série '{legend}'. Todos os valores devem ser numéricos. (Erro: {e})")
                    if not x: continue
                    all_series_legends.append(legend)
                    if plot_type == 'Histograma': ax.hist(x, bins=15, edgecolor='k', color=color, label=legend, alpha=0.7)
                    else: data_to_plot.append(x) # Acumula dados para boxplot
                elif plot_type == 'Pizza':
                    if i > 0: break 
                    x = series['label_data']
                    try: y = [float(p) for p in series['y_data']]
                    except ValueError as e: raise ValueError(f"Valor Y inválido na série '{legend}'. Valores devem ser numéricos. (Erro: {e})")
                    if len(x) != len(y): raise ValueError(f"Série '{legend}' tem X ({len(x)}) e Y ({len(y)}) de tamanhos diferentes")
                    if any(v < 0 for v in y): raise ValueError("Gráfico de Pizza não aceita valores negativos")
                    wedges, texts, autotexts = ax.pie(y, labels=x, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 8})
                    if not s['show_data_labels']:
                        for t in autotexts: t.set_visible(False)
                    ax.axis('equal')
                    
            if plot_type == 'Boxplot' and data_to_plot:
                bp = ax.boxplot(data_to_plot, patch_artist=True)
                if all_series_legends: ax.set_xticklabels(all_series_legends)
                # Colore as caixas com as cores da série
                for i, patch in enumerate(bp['boxes']):
                    color = series_list[i].get('color', '#FFFFFF')
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                        
    @Slot()
    def redraw(self):
        s = {} 
        try:
            data_state = self.data_panel.get_state()
            settings_state = self.settings_panel.get_state()
            s = {**data_state, **settings_state}

            # --- MODIFICAÇÃO (v54 - Altura) ---
            figure_width = s.get('figure_width_inches', 8.0)
            figure_height = s.get('figure_height_inches', 5.0)
            
            current_size = (0,0)
            if self.fig:
                current_size = self.fig.get_size_inches()

            # Recria a figura se o tamanho mudar
            if self.fig is None or current_size[0] != figure_width or current_size[1] != figure_height:
            # --- FIM DA MODIFICAÇÃO ---
                if self.toolbar: self.preview_layout.removeWidget(self.toolbar); self.toolbar.deleteLater()
                if self.canvas: self.preview_layout.removeWidget(self.canvas); self.canvas.deleteLater()

                self.fig = Figure(figsize=(figure_width, figure_height))
                self.canvas = FigureCanvas(self.fig)
                self.toolbar = NavigationToolbar(self.canvas, self)
                
                self.preview_layout.addWidget(self.toolbar)
                self.preview_layout.addWidget(self.canvas, 1)

            with plt.style.context(s['style']):
                self.fig.clear()
                ax = self.fig.add_subplot(111)
                
                # --- INÍCIO DA MODIFICAÇÃO (v45) ---
                # Define tamanhos de fonte fixos
                ax.set_title(s['title'], fontsize=12)
                if s['type'] != 'Pizza': 
                    ax.set_xlabel(s['xlabel'], fontsize=10)
                    ax.set_ylabel(s['ylabel'], fontsize=10)
                
                ax.tick_params(axis='both', labelsize=8) # Tamanho dos números/rótulos dos eixos
                # --- FIM DA MODIFICAÇÃO (v45) ---
                
                if s['dataset'] == 'Personalizado': self._plot_custom_data(ax, s)
                elif 'df' in s and s['df'] is not None: self._plot_csv_data(ax, s)
                
                # --- INÍCIO DA MODIFICAÇÃO (v55 - Correção Warning) ---
                # Não tenta desenhar legenda para Pizza ou Boxplot
                if s['show_legend'] and s['type'] not in ['Pizza', 'Boxplot']:
                # --- FIM DA MODIFICAÇÃO ---
                    loc, bbox = self.settings_panel._compute_legend_pos(
                        s.get('legend_type'), 
                        s.get('legend_pos_main'), 
                        s.get('legend_align')
                    )
                    size = LEGEND_SIZE_MAP.get(s['legend_size'], 10)
                    ax.legend(loc=loc, bbox_to_anchor=bbox, fontsize=size)
                
                if s['type'] not in ['Pizza', 'Barras', 'Boxplot']: ax.set_xlim(left=s['x_min'], right=s['x_max'])
                if s['type'] not in ['Pizza', 'Boxplot']: ax.set_ylim(bottom=s['y_min'], top=s['y_max'])
                
                if s['x_interval'] is not None and s['x_interval'] > 0 and s['type'] not in ['Pizza', 'Barras', 'Boxplot']:
                    ax.xaxis.set_major_locator(MultipleLocator(s['x_interval']))
                
                if s['y_interval'] is not None and s['y_interval'] > 0 and s['type'] != 'Pizza':
                    ax.yaxis.set_major_locator(MultipleLocator(s['y_interval']))
                
                # --- REMOVIDO (v45): ax.text para a fonte ABNT ---
                
                try: self.fig.tight_layout()
                except ValueError: pass
                self.canvas.draw()
        except ValueError as e:
            self.fig.clear(); ax = self.fig.add_subplot(111)
            error_message = f"Erro nos dados:\n{e}"; error_str = str(e).lower(); chart_type = s.get('type', 'desconhecido')
            if "could not convert string to float" in error_str:
                if chart_type in ['Linha', 'Dispersão']: error_message = (f"Erro: O gráfico de '{chart_type}' falhou.\nVerifique se 'Valor X' e 'Valor Y' são NÚMEROS.")
                elif chart_type in ['Histograma', 'Boxplot']: error_message = (f"Erro: O gráfico de '{chart_type}' falhou.\nVerifique se 'Valor X' ou as 'Colunas de Dados' são NÚMEROS.")
                elif chart_type == 'Barras' or chart_type == 'Pizza': error_message = (f"Erro: O gráfico de '{chart_type}' falhou.\nVerifique se 'Valor Y' ou as 'Colunas Y' são NÚMEROS.")
            elif "different sizes" in error_str: error_message = (f"Erro: Séries têm tamanhos diferentes.\n{e}")
            elif "no columns" in error_str: error_message = "Erro: Nenhuma coluna de dados (Y) foi selecionada."
            ax.text(0.5, 0.5, error_message, ha='center', va='center', color='red', fontsize=12, wrap=True, bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="red", lw=1))
            self.fig.tight_layout(); self.canvas.draw()
        except Exception as e:
            msg = f'Erro ao redesenhar Matplotlib:\n{e}\n\n{traceback.format_exc()}'
            QMessageBox.critical(self, 'Erro de Plotagem', msg)

    # --- Lógica de Aceitar/Salvar ---
    
    def _sanitizar_nome_arquivo(self, nome: str) -> str:
        """Remove caracteres inválidos para nomes de arquivo."""
        nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
        nome = nome.replace(' ', '_')
        return nome[:100] # Limita o comprimento

    def accept(self):
        """
        Chamado quando o usuário clica em OK.
        Valida, salva os arquivos (imagem e JSON) e atualiza o objeto Grafico.
        """
        
        novo_titulo = self.settings_panel.title_input.text().strip()
        if not novo_titulo:
            QMessageBox.warning(self, "Campo Obrigatório", "O campo 'Título (Legenda do Gráfico)' não pode estar vazio.")
            return

        for g_existente in self.banco_graficos:
            if g_existente.titulo.strip().lower() == novo_titulo.lower():
                if self.grafico_original_para_edicao is g_existente:
                    continue 
                
                QMessageBox.warning(self, "Título Duplicado", 
                                    f"Já existe um gráfico com o título '{novo_titulo}'.\n"
                                    "O título do gráfico deve ser único.")
                return 

        pasta_imagens = "_imagens_processadas"
        pasta_dados_chart = "_chart_data"
        os.makedirs(pasta_imagens, exist_ok=True)
        os.makedirs(pasta_dados_chart, exist_ok=True)

        nome_arquivo_base = self._sanitizar_nome_arquivo(novo_titulo)
        caminho_imagem_png = os.path.join(pasta_imagens, f"{nome_arquivo_base}.png")
        caminho_dados_json = os.path.join(pasta_dados_chart, f"{nome_arquivo_base}.chartjson")
        
        if self.grafico_original_para_edicao and self.grafico_original_para_edicao.titulo != novo_titulo:
            try:
                if os.path.exists(self.grafico_original_para_edicao.caminho_imagem_processada):
                    os.remove(self.grafico_original_para_edicao.caminho_imagem_processada)
                if os.path.exists(self.grafico_original_para_edicao.caminho_dados_json):
                    os.remove(self.grafico_original_para_edicao.caminho_dados_json)
            except OSError as e:
                print(f"Aviso: Não foi possível remover arquivos antigos do gráfico renomeado: {e}")

        try:
            self.fig.savefig(caminho_imagem_png, dpi=300, bbox_inches='tight')
            
            data_state = self.data_panel.get_state_for_save()
            settings_state = self.settings_panel.get_state()
            full_state = {**data_state, **settings_state}
            
            with open(caminho_dados_json, 'w', encoding='utf-8') as f:
                json.dump(full_state, f, indent=4)

        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar Arquivos", f"Não foi possível salvar os arquivos do gráfico:\n{e}")
            return
            
        self.grafico_final.titulo = novo_titulo
        self.grafico_final.fonte = self.settings_panel.source_input.text().strip() # Fonte ABNT salva aqui
        self.grafico_final.caminho_imagem_processada = caminho_imagem_png
        self.grafico_final.caminho_dados_json = caminho_dados_json
        
        self.grafico_final.largura_cm = self.settings_panel.get_state()['largura_cm']

        super().accept()

    def get_dados_grafico(self) -> Grafico:
        """Retorna o objeto Grafico finalizado para a AbaConteudo."""
        return self.grafico_final
    
    def done(self, result):
        """
        Sobrescreve o método 'done' do QDialog para limpar os recursos do Matplotlib
        antes de fechar, prevenindo vazamentos de memória.
        """
        print("Limpando recursos do Matplotlib...")
        try:
            if self.fig:
                # Limpa todos os eixos da figura
                self.fig.clear() 
                # Fecha a figura no estado global do pyplot (CRUCIAL)
                plt.close(self.fig)
            if self.canvas:
                # Remove o widget da interface
                self.canvas.close() 
                # Marca para exclusão segura
                self.canvas.deleteLater()
            if self.toolbar:
                self.toolbar.close()
                self.toolbar.deleteLater()
                
            self.fig = None
            self.canvas = None
            self.toolbar = None
            
        except Exception as e:
            # Mesmo se falhar, não impede o fechamento do diálogo
            print(f"Erro ao limpar recursos do Matplotlib: {e}")
        
        # Chama a implementação original para fechar o diálogo
        super().done(result)