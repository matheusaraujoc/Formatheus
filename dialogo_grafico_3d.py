# dialogo_grafico_3d.py
#
# Descrição: Editor de Gráficos 3D integrado ao sistema Formatheus.
#
# ATUALIZAÇÃO (v1.2 - Ajustes de UI):
# 1. Removido botão de alternar tema (agora é global).
# 2. Adicionado QCheckBox "Mostrar Título no Gráfico" na aba Geral.
# 3. O título do gráfico (ax.set_title) agora é condicional.
# 4. Mantidos os ajustes de tamanho de janela e botões.
#

import sys
import os
import traceback
import numpy as np
import json 
import re
import pandas as pd

from PySide6 import QtCore, QtGui
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QFileDialog, QCheckBox,
    QMessageBox, QGroupBox, QFormLayout, QTreeWidget, QTreeWidgetItem,
    QHeaderView, QColorDialog, QScrollArea, QStackedWidget,
    QMainWindow, QTabWidget, QDialog, QDialogButtonBox, QSplitter,
    QGridLayout, QSlider, QToolButton, QStyle, QTableWidget, QTableWidgetItem,
    QSpinBox
)
from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtGui import (
    QColor, QBrush, QFont,
    QAction, QKeySequence 
)

from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.ticker import MultipleLocator
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D 
from matplotlib import cm

# --- IMPORTAÇÃO 3D ---
from mpl_toolkits.mplot3d import Axes3D

# --- IMPORTAÇÃO DE DADOS DO PROJETO ---
from documento import Grafico3D  # Importa a classe real do documento

LEGEND_SIZE_MAP = {'Pequena': 8, 'Média': 10, 'Grande': 14}

COLORMAPS = [
    'viridis', 'plasma', 'inferno', 'magma', 'cividis',
    'coolwarm', 'bwr', 'seismic',
    'twilight', 'hsv',
    'flag', 'prism', 'ocean', 'gist_earth', 'terrain', 'gist_stern',
    'gnuplot', 'gnuplot2', 'CMRmap', 'cubehelix', 'brg',
    'gist_rainbow', 'rainbow', 'jet', 'turbo', 'nipy_spectral',
    'gist_ncar'
]

def parse_axis_limit(text):
    try:
        return float(text.strip())
    except ValueError:
        return None

class SeriesColorButton(QPushButton):
    def __init__(self, series_item, on_change_callback):
        super().__init__()
        self.series_item = series_item
        self.on_change = on_change_callback
        self.clicked.connect(self.pick_color)
        self.setFixedSize(25, 25)
        self.setText("")
        self.sync_color()

    def pick_color(self):
        current_color_hex = self.series_item.data(0, Qt.ItemDataRole.UserRole)
        dialog = QColorDialog(QColor(current_color_hex))
        
        if dialog.exec():
            new_color = dialog.selectedColor()
            self.series_item.setData(0, Qt.ItemDataRole.UserRole, new_color.name())
            self.sync_color()
            self.on_change()

    def sync_color(self):
        color_hex = self.series_item.data(0, Qt.ItemDataRole.UserRole)
        color = QColor(color_hex)
        self.setStyleSheet(f"background-color: {color_hex}; border: 1px solid #555;")


# --- PAINEL 1: DADOS POR PONTOS (Árvore) ---
class PointDataSourcePanel(QWidget):
    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        data_group = QGroupBox('Dados (Por Pontos)')
        tree_layout = QVBoxLayout(data_group)
        
        self.import_btn = QPushButton("Importar Pontos (CSV/Excel)...")
        self.import_btn.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.import_btn.clicked.connect(self._import_point_file)
        tree_layout.addWidget(self.import_btn)
        
        self.series_tree = QTreeWidget()
        self.series_tree.setColumnCount(5)
        self.series_tree.setHeaderLabels(["Série", "Ponto X", "Ponto Y", "Ponto Z", "Cor"])
        self.series_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for i in range(1, 4):
            self.series_tree.header().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.series_tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        
        self.series_tree.setColumnWidth(1, 80) 
        self.series_tree.setColumnWidth(2, 80) 
        self.series_tree.setColumnWidth(3, 80)
        self.series_tree.setColumnWidth(4, 60)
        
        self.series_tree.setAlternatingRowColors(True)
        self.series_tree.itemChanged.connect(self._emit_change)
        tree_layout.addWidget(self.series_tree)
        
        tree_btn_layout = QGridLayout()
        add_series_btn = QPushButton("Adicionar Série (+)")
        add_series_btn.clicked.connect(self.add_series_item)
        add_point_btn = QPushButton("Adicionar Ponto (+)")
        add_point_btn.clicked.connect(self.add_data_point_item)
        remove_btn = QPushButton("Remover Item (-)")
        remove_btn.clicked.connect(self.remove_tree_item)
        
        tree_btn_layout.addWidget(add_series_btn, 0, 0)
        tree_btn_layout.addWidget(add_point_btn, 0, 1)
        tree_btn_layout.addWidget(remove_btn, 1, 0, 1, 2)
        
        tree_layout.addLayout(tree_btn_layout)
        layout.addWidget(data_group)
        self.setLayout(layout)

    @Slot()
    def _import_point_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Pontos", 
            filter="Arquivos de Dados (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)"
        )
        if not path: return
        
        try:
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path)
            elif path.lower().endswith('.xlsx'):
                df = pd.read_excel(path)
            else:
                raise ValueError("Formato não suportado.")
            
            numeric_df = df.select_dtypes(include=[np.number])
            if numeric_df.shape[1] < 3:
                raise ValueError("O arquivo precisa ter pelo menos 3 colunas numéricas (X, Y, Z).")
            
            x_col = numeric_df.columns[0]
            y_col = numeric_df.columns[1]
            z_col = numeric_df.columns[2]
            
            text_cols = df.select_dtypes(include=['object', 'category']).columns
            series_col = text_cols[0] if len(text_cols) > 0 else None
            
            self.series_tree.blockSignals(True)
            self.series_tree.clear()
            
            groups = []
            if series_col:
                groups = df.groupby(series_col)
            else:
                groups = [("Série Importada", df)]
                
            for name, group in groups:
                series_item = QTreeWidgetItem(self.series_tree)
                series_item.setText(0, str(name))
                series_item.setFlags(series_item.flags() | Qt.ItemFlag.ItemIsEditable)
                series_item.setFont(0, QFont("Arial", 10, QFont.Weight.Bold))
                
                rand_color = QColor.fromHsv(np.random.randint(0, 359), 200, 200).name()
                series_item.setData(0, Qt.ItemDataRole.UserRole, rand_color)
                series_item.setExpanded(True)
                
                color_btn = SeriesColorButton(series_item, self.on_change)
                self.series_tree.setItemWidget(series_item, 4, color_btn)
                
                for _, row in group.iterrows():
                    point_item = QTreeWidgetItem(series_item)
                    point_item.setText(0, "") 
                    point_item.setText(1, str(row[x_col]))
                    point_item.setText(2, str(row[y_col]))
                    point_item.setText(3, str(row[z_col]))
                    point_item.setFlags(point_item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            self.series_tree.blockSignals(False)
            QMessageBox.information(self, "Sucesso", "Pontos importados com sucesso!")
            self.on_change()
            
        except Exception as e:
            QMessageBox.critical(self, "Erro de Importação", f"Falha ao ler arquivo:\n{e}")
        
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
        self.series_tree.setItemWidget(series_item, 4, color_btn) 
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
        
        default_y = str(np.random.randint(1, 10))
        default_z = str(np.random.randint(1, 10))
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
        point_item.setText(0, f"Ponto {current_point_count + 1}")
        point_item.setText(1, new_x)
        point_item.setText(2, default_y)
        point_item.setText(3, default_z)
        
        point_item.setFlags(point_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.series_tree.blockSignals(False)

    @Slot()
    def remove_tree_item(self):
        selected_item = self.series_tree.currentItem()
        if not selected_item: return
        (selected_item.parent() or self.series_tree.invisibleRootItem()).removeChild(selected_item)
        self._emit_change()

    def _emit_change(self, *args):
        self.on_change()

    def get_state(self):
        series_data = []
        root = self.series_tree.invisibleRootItem()
        for i in range(root.childCount()):
            series_item = root.child(i)
            label_data, x_data, y_data, z_data = [], [], [], []
            for j in range(series_item.childCount()):
                point_item = series_item.child(j)
                label_data.append(point_item.text(0))
                x_data.append(point_item.text(1))
                y_data.append(point_item.text(2))
                z_data.append(point_item.text(3))
            series_data.append({
                'legend': series_item.text(0),
                'color': series_item.data(0, Qt.ItemDataRole.UserRole),
                'label_data': label_data, 'x_data': x_data, 'y_data': y_data,
                'z_data': z_data 
            })
        return {'series_data': series_data}
        
    def set_state(self, state):
        try:
            self.series_tree.blockSignals(True)
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
                self.series_tree.setItemWidget(series_item, 4, color_btn)
                
                labels = series_data.get('label_data', []); xs = series_data.get('x_data', []); 
                ys = series_data.get('y_data', []); zs = series_data.get('z_data', [])
                max_len = max(len(labels), len(xs), len(ys), len(zs))
                for i in range(max_len):
                    point_item = QTreeWidgetItem(series_item)
                    point_item.setText(0, labels[i] if i < len(labels) else '')
                    point_item.setText(1, xs[i] if i < len(xs) else '')
                    point_item.setText(2, ys[i] if i < len(ys) else '')
                    point_item.setText(3, zs[i] if i < len(zs) else '') 
                    point_item.setFlags(point_item.flags() | Qt.ItemFlag.ItemIsEditable)
        finally:
            self.series_tree.blockSignals(False)
            self.on_change()


# --- PAINEL 2: DADOS POR GRADE (Tabela) ---
class GridDataSourcePanel(QWidget):
    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)

        data_group = QGroupBox('Dados (Por Grade/Superfície)')
        form_layout = QFormLayout(data_group)

        self.x_min_input = QLineEdit("-5")
        self.x_max_input = QLineEdit("5")
        self.x_step_spin = QSpinBox()
        self.x_step_spin.setRange(2, 100)
        self.x_step_spin.setValue(20)
        
        self.y_min_input = QLineEdit("-5")
        self.y_max_input = QLineEdit("5")
        self.y_step_spin = QSpinBox()
        self.y_step_spin.setRange(2, 100)
        self.y_step_spin.setValue(20)

        # Conectar sinais para recriar tabela
        self.x_min_input.editingFinished.connect(self._recreate_table)
        self.x_max_input.editingFinished.connect(self._recreate_table)
        self.x_step_spin.valueChanged.connect(self._recreate_table)
        self.y_min_input.editingFinished.connect(self._recreate_table)
        self.y_max_input.editingFinished.connect(self._recreate_table)
        self.y_step_spin.valueChanged.connect(self._recreate_table)
        
        form_layout.addRow("X Mín:", self.x_min_input)
        form_layout.addRow("X Máx:", self.x_max_input)
        form_layout.addRow("Passos X (Cols):", self.x_step_spin)
        form_layout.addRow("Y Mín:", self.y_min_input)
        form_layout.addRow("Y Máx:", self.y_max_input)
        form_layout.addRow("Passos Y (Lins):", self.y_step_spin)
        
        # Controle de Colormap
        color_layout = QVBoxLayout()
        
        self.use_cmap_cb = QCheckBox("Colorir por Altura (Mapa de Cores)")
        self.use_cmap_cb.setChecked(True)
        self.use_cmap_cb.stateChanged.connect(self._toggle_color_mode)
        self.use_cmap_cb.stateChanged.connect(self._emit_change)
        
        self.cmap_combo = QComboBox()
        self.cmap_combo.addItems(COLORMAPS)
        self.cmap_combo.setCurrentText("coolwarm")
        self.cmap_combo.currentIndexChanged.connect(self._emit_change)
        
        self.color_btn = QPushButton("Cor Sólida")
        self.current_color = QColor("#0078d4")
        self.color_btn.clicked.connect(self._pick_color)
        
        color_layout.addWidget(self.use_cmap_cb)
        color_layout.addWidget(self.cmap_combo)
        color_layout.addWidget(self.color_btn)
        
        form_layout.addRow(color_layout)
        
        self.import_btn = QPushButton("Importar Matriz (CSV/Excel)...")
        self.import_btn.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.import_btn.clicked.connect(self._import_grid_file)
        form_layout.addRow(self.import_btn)
        
        form_layout.addRow(QLabel("Valores Z (Matriz):"))
        self.table_z_data = QTableWidget()
        self.table_z_data.itemChanged.connect(self._emit_change)
        form_layout.addRow(self.table_z_data)
        
        layout.addWidget(data_group)
        self.setLayout(layout)
        
        self._recreate_table() 
        self._sync_color_button()
        self._toggle_color_mode()

    @Slot()
    def _import_grid_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar Matriz de Dados", 
            filter="Arquivos de Dados (*.csv *.xlsx);;CSV (*.csv);;Excel (*.xlsx)"
        )
        
        if not path: return
        
        try:
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path, header=None)
            elif path.lower().endswith('.xlsx'):
                df = pd.read_excel(path, header=None)
            else:
                raise ValueError("Formato não suportado.")
            
            df_numeric = df.apply(pd.to_numeric, errors='coerce')
            
            if df_numeric.isna().any().any():
                reply = QMessageBox.question(
                    self, "Aviso de Validação",
                    "O arquivo contém valores não numéricos.\nDeseja substituir por 0 e continuar?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply == QMessageBox.StandardButton.No: return
                df_numeric = df_numeric.fillna(0)
            
            rows, cols = df_numeric.shape
            if rows < 2 or cols < 2:
                QMessageBox.warning(self, "Erro", "A matriz deve ter pelo menos 2x2.")
                return

            self.blockSignals(True)
            self.y_step_spin.setValue(rows)
            self.x_step_spin.setValue(cols)
            self.blockSignals(False)
            
            self.table_z_data.blockSignals(True)
            self.table_z_data.setRowCount(rows)
            self.table_z_data.setColumnCount(cols)
            
            x_min = float(self.x_min_input.text()); x_max = float(self.x_max_input.text())
            y_min = float(self.y_min_input.text()); y_max = float(self.y_max_input.text())
            x_vals = np.linspace(x_min, x_max, cols)
            y_vals = np.linspace(y_min, y_max, rows)
            self.table_z_data.setHorizontalHeaderLabels([f"{v:.1f}" for v in x_vals])
            self.table_z_data.setVerticalHeaderLabels([f"{v:.1f}" for v in y_vals])
            
            for r in range(rows):
                for c in range(cols):
                    val = df_numeric.iat[r, c]
                    item = QTableWidgetItem(f"{val:.2f}")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_z_data.setItem(r, c, item)
            
            self.table_z_data.blockSignals(False)
            
            QMessageBox.information(self, "Sucesso", f"Matriz {rows}x{cols} importada.")
            self.on_change() 
            
        except Exception as e:
            QMessageBox.critical(self, "Erro de Importação", f"Falha ao ler o arquivo:\n{e}")

    @Slot()
    def _toggle_color_mode(self):
        use_cmap = self.use_cmap_cb.isChecked()
        self.cmap_combo.setVisible(use_cmap)
        self.color_btn.setVisible(not use_cmap)

    @Slot()
    def _pick_color(self):
        dialog = QColorDialog(self.current_color)
        if dialog.exec():
            self.current_color = dialog.selectedColor()
            self._sync_color_button()
            self.on_change()
            
    def _sync_color_button(self):
        self.color_btn.setStyleSheet(f"background-color: {self.current_color.name()}; border: 1px solid #555; color: white;")

    @Slot()
    def _recreate_table(self):
        self.table_z_data.blockSignals(True)
        
        try:
            x_steps = self.x_step_spin.value()
            y_steps = self.y_step_spin.value()
            
            old_z_data = []
            for r in range(self.table_z_data.rowCount()):
                row_data = []
                for c in range(self.table_z_data.columnCount()):
                    item = self.table_z_data.item(r, c)
                    row_data.append(float(item.text()) if item and item.text() else 0.0)
                old_z_data.append(row_data)

            self.table_z_data.setRowCount(y_steps)
            self.table_z_data.setColumnCount(x_steps)

            x_min = float(self.x_min_input.text()); x_max = float(self.x_max_input.text())
            y_min = float(self.y_min_input.text()); y_max = float(self.y_max_input.text())
            
            x_vals = np.linspace(x_min, x_max, x_steps)
            y_vals = np.linspace(y_min, y_max, y_steps)

            self.table_z_data.setHorizontalHeaderLabels([f"{v:.1f}" for v in x_vals])
            self.table_z_data.setVerticalHeaderLabels([f"{v:.1f}" for v in y_vals])

            for r in range(y_steps):
                for c in range(x_steps):
                    value = 0.0
                    if r < len(old_z_data) and c < len(old_z_data[r]):
                        value = old_z_data[r][c]
                    else:
                        x = x_vals[c]
                        y = y_vals[r]
                        value = np.sin(np.sqrt(x**2 + y**2)) 
                        
                    item = QTableWidgetItem(f"{value:.2f}")
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table_z_data.setItem(r, c, item)
            
        except ValueError:
            pass 
        finally:
            self.table_z_data.blockSignals(False)
            self._emit_change()

    def _emit_change(self, *args):
        self.on_change()

    def get_state(self):
        z_data = []
        for r in range(self.table_z_data.rowCount()):
            row_data = []
            for c in range(self.table_z_data.columnCount()):
                item = self.table_z_data.item(r, c)
                try:
                    val = float(item.text()) if item and item.text() else 0.0
                except ValueError:
                    val = 0.0
                row_data.append(val)
            z_data.append(row_data)
            
        return {
            'x_min': float(self.x_min_input.text()),
            'x_max': float(self.x_max_input.text()),
            'x_steps': self.x_step_spin.value(),
            'y_min': float(self.y_min_input.text()),
            'y_max': float(self.y_max_input.text()),
            'y_steps': self.y_step_spin.value(),
            'z_grid': z_data, 
            'use_cmap': self.use_cmap_cb.isChecked(),
            'cmap_name': self.cmap_combo.currentText(),
            'grid_color': self.current_color.name()
        }
    
    def set_state(self, state):
        self.x_min_input.setText(str(state.get('x_min', '-5')))
        self.x_max_input.setText(str(state.get('x_max', '5')))
        self.x_step_spin.setValue(state.get('x_steps', 20))
        self.y_min_input.setText(str(state.get('y_min', '-5')))
        self.y_max_input.setText(str(state.get('y_max', '5')))
        self.y_step_spin.setValue(state.get('y_steps', 20))
        
        self.use_cmap_cb.setChecked(state.get('use_cmap', True))
        self.cmap_combo.setCurrentText(state.get('cmap_name', 'coolwarm'))
        self._toggle_color_mode()
        
        self.current_color = QColor(state.get('grid_color', '#0078d4'))
        self._sync_color_button()
        
        self._recreate_table()
        
        saved_z = state.get('z_grid', [])
        self.table_z_data.blockSignals(True)
        for r, row in enumerate(saved_z):
            if r < self.table_z_data.rowCount():
                for c, val in enumerate(row):
                    if c < self.table_z_data.columnCount():
                        self.table_z_data.item(r, c).setText(f"{val:.2f}")
        self.table_z_data.blockSignals(False)
        self.on_change()


# ---------------------------------------------------------------
COMPACT_STYLESHEET = """
    SettingsPanel#ChartSettingsPanel { font-size: 12px; }
    SettingsPanel#ChartSettingsPanel QTabWidget::pane { border: none; }
    SettingsPanel#ChartSettingsPanel QTabBar::tab { padding: 5px 8px; font-size: 12px; }
    SettingsPanel#ChartSettingsPanel QLabel { font-size: 12px; padding-top: 2px; }
    SettingsPanel#ChartSettingsPanel QLineEdit,
    SettingsPanel#ChartSettingsPanel QComboBox,
    SettingsPanel#ChartSettingsPanel QSpinBox { font-size: 12px; padding: 3px; min-height: 18px; }
    SettingsPanel#ChartSettingsPanel QSlider { min-height: 20px; }
    SettingsPanel#ChartSettingsPanel QLabel#FigureWidthLabel,
    SettingsPanel#ChartSettingsPanel QLabel#FigureHeightLabel,
    SettingsPanel#ChartSettingsPanel QLabel#ElevLabel,
    SettingsPanel#ChartSettingsPanel QLabel#AzimLabel {
        font-size: 12px; font-weight: bold; padding: 3px; min-width: 45px;
    }
    SettingsPanel#ChartSettingsPanel QToolButton { padding: 2px; min-width: 20px; min-height: 20px; }
    SettingsPanel#ChartSettingsPanel QCheckBox { font-size: 12px; }
    SettingsPanel#ChartSettingsPanel QPushButton { font-size: 12px; padding: 4px 8px; }
    SettingsPanel#ChartSettingsPanel QGroupBox { font-size: 12px; font-weight: bold; margin-top: 6px; }
    SettingsPanel#ChartSettingsPanel QGroupBox::title {
        subcontrol-origin: margin; subcontrol-position: top left; padding: 0 3px;
    }
"""

class SettingsPanel(QWidget):
    """Painel de configurações simplificado para 3D."""
    def __init__(self, on_change):
        super().__init__()
        self.on_change = on_change
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        self.tab_widget = QTabWidget()
        self._create_geral_tab()
        self._create_eixos_tab()
        self._create_estilo_tab()
        
        self.tab_widget.addTab(self.tab_geral, "Geral")
        self.tab_widget.addTab(self.tab_eixos, "Eixos")
        self.tab_widget.addTab(self.tab_estilo, "Estilo e Ângulos")
        
        main_layout.addWidget(self.tab_widget)
        
        controls_layout = QHBoxLayout()
        self.live_cb = QCheckBox('Pré-visualização em tempo real')
        self.live_cb.setChecked(True)
        self.live_cb.stateChanged.connect(self._emit_change)
        self.update_btn = QPushButton('Atualizar')
        self.update_btn.clicked.connect(self.on_change)
        controls_layout.addWidget(self.live_cb)
        controls_layout.addStretch()
        controls_layout.addWidget(self.update_btn)
        main_layout.addLayout(controls_layout)
        
        self.setLayout(main_layout)
        self.setObjectName("ChartSettingsPanel")
        self.setStyleSheet(COMPACT_STYLESHEET)

    def _create_geral_tab(self):
        self.tab_geral = QWidget()
        layout = QFormLayout(self.tab_geral)
        
        self.data_mode_cb = QComboBox()
        self.data_mode_cb.addItems(['Dados por Pontos', 'Dados por Grade'])
        self.data_mode_cb.currentIndexChanged.connect(self._emit_change)
        layout.addRow("Modo de Dados:", self.data_mode_cb)
        
        self.type_cb = QComboBox()
        self.type_cb.addItems([
            'Dispersão (Pontos)', 'Linhas 3D', 'Barras 3D', 
            'Superfície (Triangulação)', 'Arame (Wireframe)',
            'Superfície de Grade', 'Malha de Grade (Wireframe)'
        ])
        self.type_cb.currentIndexChanged.connect(self._emit_change)
        layout.addRow("Tipo de Gráfico:", self.type_cb)

        self.title_input = QLineEdit("Gráfico 3D")
        self.title_input.textChanged.connect(self._emit_change)
        layout.addRow('Título (Legenda):', self.title_input)
        
        # --- INÍCIO: Checkbox "Mostrar Título" ---
        self.show_title_cb = QCheckBox("Mostrar Título no Gráfico")
        self.show_title_cb.setChecked(True)
        self.show_title_cb.stateChanged.connect(self._emit_change)
        layout.addRow(self.show_title_cb)
        # --- FIM: Checkbox "Mostrar Título" ---

        self.xlabel_input = QLineEdit("Eixo X")
        self.xlabel_input.textChanged.connect(self._emit_change)
        layout.addRow('Rótulo Eixo X:', self.xlabel_input)
        
        self.ylabel_input = QLineEdit("Eixo Y")
        self.ylabel_input.textChanged.connect(self._emit_change)
        layout.addRow('Rótulo Eixo Y:', self.ylabel_input)
        
        self.zlabel_input = QLineEdit("Eixo Z")
        self.zlabel_input.textChanged.connect(self._emit_change)
        layout.addRow('Rótulo Eixo Z:', self.zlabel_input)
        
        self.source_input = QLineEdit("Própria")
        self.source_input.textChanged.connect(self._emit_change)
        layout.addRow('Fonte (ABNT):', self.source_input)
        
        slider_layout_w = QHBoxLayout()
        self.figure_width_slider = QSlider(Qt.Orientation.Horizontal, minimum=50, maximum=150, value=80, singleStep=5)
        self.figure_width_label = QLabel("8.0 pol")
        self.figure_width_label.setObjectName("FigureWidthLabel")
        slider_layout_w.addWidget(self.figure_width_slider)
        slider_layout_w.addWidget(self.figure_width_label)
        self.figure_width_slider.valueChanged.connect(lambda v: self.figure_width_label.setText(f"{v/10.0:.1f} pol"))
        self.figure_width_slider.sliderReleased.connect(self._emit_change)
        layout.addRow("Largura (Prévia):", slider_layout_w)
        
        slider_layout_h = QHBoxLayout()
        self.figure_height_slider = QSlider(Qt.Orientation.Horizontal, minimum=30, maximum=120, value=60, singleStep=5)
        self.figure_height_label = QLabel("6.0 pol")
        self.figure_height_label.setObjectName("FigureHeightLabel")
        slider_layout_h.addWidget(self.figure_height_slider)
        slider_layout_h.addWidget(self.figure_height_label)
        self.figure_height_slider.valueChanged.connect(lambda v: self.figure_height_label.setText(f"{v/10.0:.1f} pol"))
        self.figure_height_slider.sliderReleased.connect(self._emit_change)
        layout.addRow("Altura (Prévia):", slider_layout_h)

    def _create_eixos_tab(self):
        self.tab_eixos = QWidget()
        layout = QFormLayout(self.tab_eixos)

        self.x_min_input = QLineEdit()
        self.x_min_input.textChanged.connect(self._emit_change)
        layout.addRow("X Mín:", self.x_min_input)
        self.x_max_input = QLineEdit()
        self.x_max_input.textChanged.connect(self._emit_change)
        layout.addRow("X Máx:", self.x_max_input)

        self.y_min_input = QLineEdit()
        self.y_min_input.textChanged.connect(self._emit_change)
        layout.addRow("Y Mín:", self.y_min_input)
        self.y_max_input = QLineEdit()
        self.y_max_input.textChanged.connect(self._emit_change)
        layout.addRow("Y Máx:", self.y_max_input)

        self.z_min_input = QLineEdit()
        self.z_min_input.textChanged.connect(self._emit_change)
        layout.addRow("Z Mín:", self.z_min_input)
        self.z_max_input = QLineEdit()
        self.z_max_input.textChanged.connect(self._emit_change)
        layout.addRow("Z Máx:", self.z_max_input)

    def _create_estilo_tab(self):
        self.tab_estilo = QWidget()
        layout = QFormLayout(self.tab_estilo)

        self.style_cb = QComboBox()
        self.style_cb.addItems(['classic', 'ggplot', 'seaborn-v0_8-darkgrid', 'bmh', 'dark_background'])
        self.style_cb.setCurrentText('classic')
        self.style_cb.currentIndexChanged.connect(self._emit_change)
        layout.addRow('Estilo:', self.style_cb)
        
        self.show_legend_cb = QCheckBox("Mostrar Legenda")
        self.show_legend_cb.setChecked(True)
        self.show_legend_cb.stateChanged.connect(self._emit_change)
        layout.addRow(self.show_legend_cb)
        
        self.legend_size_cb = QComboBox()
        self.legend_size_cb.addItems(LEGEND_SIZE_MAP.keys())
        self.legend_size_cb.setCurrentText("Média")
        self.legend_size_cb.currentIndexChanged.connect(self._emit_change)
        layout.addRow("Tamanho da Legenda:", self.legend_size_cb)
        
        angle_group = QGroupBox("Ângulos de Visão")
        angle_layout = QFormLayout(angle_group)
        angle_layout.setContentsMargins(5, 10, 5, 5)

        elev_layout = QHBoxLayout()
        self.elev_slider = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=90, value=30, singleStep=5)
        self.elev_label = QLabel("30°")
        self.elev_label.setObjectName("ElevLabel")
        elev_layout.addWidget(self.elev_slider)
        elev_layout.addWidget(self.elev_label)
        self.elev_slider.valueChanged.connect(lambda v: self.elev_label.setText(f"{v}°"))
        self.elev_slider.sliderReleased.connect(self._emit_change)
        angle_layout.addRow("Elevação:", elev_layout)

        azim_layout = QHBoxLayout()
        self.azim_slider = QSlider(Qt.Orientation.Horizontal, minimum=0, maximum=360, value=45, singleStep=10)
        self.azim_label = QLabel("45°")
        self.azim_label.setObjectName("AzimLabel")
        azim_layout.addWidget(self.azim_slider)
        azim_layout.addWidget(self.azim_label)
        self.azim_slider.valueChanged.connect(lambda v: self.azim_label.setText(f"{v}°"))
        self.azim_slider.sliderReleased.connect(self._emit_change)
        angle_layout.addRow("Giro (Azimute):", azim_layout)
        
        self.rotate_view_cb = QCheckBox("Visualização em Rotação")
        self.rotate_view_cb.stateChanged.connect(self._emit_change)
        angle_layout.addRow(self.rotate_view_cb)
        
        layout.addRow(angle_group)

    @Slot()
    def _emit_change(self, *args):
        if hasattr(self, 'live_cb') and self.live_cb.isChecked(): 
            self.on_change()

    def get_state(self):
        return {
            'data_mode': self.data_mode_cb.currentText(), 
            'type': self.type_cb.currentText(),
            'title': self.title_input.text(),
            'show_title': self.show_title_cb.isChecked(), # <-- ADICIONADO
            'xlabel': self.xlabel_input.text(), 'ylabel': self.ylabel_input.text(),
            'zlabel': self.zlabel_input.text(),
            'source': self.source_input.text(), 'style': self.style_cb.currentText(),
            'show_legend': self.show_legend_cb.isChecked(),
            'legend_size': self.legend_size_cb.currentText(),
            'x_min': parse_axis_limit(self.x_min_input.text()), 'x_max': parse_axis_limit(self.x_max_input.text()),
            'y_min': parse_axis_limit(self.y_min_input.text()), 'y_max': parse_axis_limit(self.y_max_input.text()),
            'z_min': parse_axis_limit(self.z_min_input.text()), 'z_max': parse_axis_limit(self.z_max_input.text()),
            'live': self.live_cb.isChecked(),
            'largura_cm': 16.0, 
            'figure_width_inches': self.figure_width_slider.value() / 10.0,
            'figure_height_inches': self.figure_height_slider.value() / 10.0,
            'elev': self.elev_slider.value(),
            'azim': self.azim_slider.value(),
            'rotate_view': self.rotate_view_cb.isChecked(),
        }
        
    def set_state(self, state):
        self.data_mode_cb.setCurrentText(state.get('data_mode', 'Dados por Pontos'))
        self.type_cb.setCurrentText(state.get('type', 'Dispersão (Pontos)'))
        
        self.title_input.setText(state.get('title', ''))
        self.show_title_cb.setChecked(state.get('show_title', True)) # <-- ADICIONADO
        self.xlabel_input.setText(state.get('xlabel', ''))
        self.ylabel_input.setText(state.get('ylabel', ''))
        self.zlabel_input.setText(state.get('zlabel', ''))
        self.source_input.setText(state.get('source', ''))
        
        self.x_min_input.setText(str(state.get('x_min', '')) if state.get('x_min') is not None else '')
        self.x_max_input.setText(str(state.get('x_max', '')) if state.get('x_max') is not None else '')
        self.y_min_input.setText(str(state.get('y_min', '')) if state.get('y_min') is not None else '')
        self.y_max_input.setText(str(state.get('y_max', '')) if state.get('y_max') is not None else '')
        self.z_min_input.setText(str(state.get('z_min', '')) if state.get('z_min') is not None else '')
        self.z_max_input.setText(str(state.get('z_max', '')) if state.get('z_max') is not None else '')

        self.show_legend_cb.setChecked(state.get('show_legend', True))
        self.legend_size_cb.setCurrentText(state.get('legend_size', 'Média'))
        self.style_cb.setCurrentText(state.get('style', 'classic'))
        self.live_cb.setChecked(state.get('live', True))
        
        slider_val_w = int(state.get('figure_width_inches', 8.0) * 10)
        self.figure_width_slider.setValue(slider_val_w)
        self.figure_width_label.setText(f"{slider_val_w / 10.0:.1f} pol")
        
        slider_val_h = int(state.get('figure_height_inches', 6.0) * 10)
        self.figure_height_slider.setValue(slider_val_h)
        self.figure_height_label.setText(f"{slider_val_h / 10.0:.1f} pol")
        
        elev_val = int(state.get('elev', 30))
        self.elev_slider.setValue(elev_val)
        self.elev_label.setText(f"{elev_val}°")
        
        azim_val = int(state.get('azim', 45))
        self.azim_slider.setValue(azim_val)
        self.azim_label.setText(f"{azim_val}°")
        
        self.rotate_view_cb.setChecked(state.get('rotate_view', False))
        
# ---------------------------------------------------------------
# --- CLASSE PRINCIPAL: Grafico3DDialog (QDialog) ---
# ---------------------------------------------------------------

class Grafico3DDialog(QDialog):
    
    def __init__(self, grafico: Grafico3D = None, banco_graficos_3d: list[Grafico3D] = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Gráfico 3D (Matplotlib)")
        self.resize(1400, 800) 
        self.setMinimumSize(1200, 700)
        
        self.grafico_original_para_edicao = grafico
        self.grafico_final = grafico if grafico else Grafico3D()
        self.banco_graficos_3d = banco_graficos_3d if banco_graficos_3d else []
        
        self.is_dark_theme = True 

        main_layout = QVBoxLayout(self) 
        
        self.fig = None 
        self.canvas = None
        self.toolbar = None
        
        self.redraw_timer = QtCore.QTimer(self)
        self.redraw_timer.setSingleShot(True)
        self.redraw_timer.setInterval(500)
        self.redraw_timer.timeout.connect(self.redraw)
        
        self.rotation_timer = QtCore.QTimer(self)
        self.rotation_timer.setInterval(100) 
        self.rotation_timer.timeout.connect(self._on_rotation_tick)
        
        self.settings_panel = SettingsPanel(self.trigger_redraw)
        
        self.point_data_panel = PointDataSourcePanel(self.trigger_redraw)
        self.grid_data_panel = GridDataSourcePanel(self.trigger_redraw)
        
        self.data_stack = QStackedWidget()
        self.data_stack.addWidget(self.point_data_panel) # Index 0
        self.data_stack.addWidget(self.grid_data_panel)  # Index 1
        
        self.settings_panel.update_btn.clicked.connect(self.redraw)
        
        self.settings_panel.figure_width_slider.sliderReleased.connect(self.trigger_redraw)
        self.settings_panel.figure_height_slider.sliderReleased.connect(self.trigger_redraw)
        self.settings_panel.elev_slider.sliderReleased.connect(self.trigger_redraw)
        self.settings_panel.azim_slider.sliderReleased.connect(self.trigger_redraw)
        
        self.settings_panel.type_cb.currentIndexChanged.connect(self.trigger_redraw)
        self.settings_panel.data_mode_cb.currentIndexChanged.connect(self._on_data_mode_changed)

        self.h_splitter = QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        
        data_container = QWidget()
        dc_layout = QVBoxLayout(data_container)
        dc_layout.setContentsMargins(0,0,0,0)
        dc_layout.addWidget(self.data_stack)
        data_container.setFixedWidth(450) 
        self.h_splitter.addWidget(data_container)
        
        self.preview_widget = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_widget)
        self.preview_layout.setContentsMargins(0,0,0,0)
        self.h_splitter.addWidget(self.preview_widget)
        
        self.settings_panel.setFixedWidth(260) 
        self.settings_panel.tab_widget.setStyleSheet("QTabWidget::pane { border: none; }")
        self.h_splitter.addWidget(self.settings_panel) 
        
        self.h_splitter.setSizes([450, 690, 260]) 
        main_layout.addWidget(self.h_splitter, 1) 

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept) 
        self.buttons.rejected.connect(self.reject)
        
        ok_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setAutoDefault(False)
        ok_button.setDefault(False)
        
        self.buttons.setStyleSheet("QPushButton { font-size: 12px; padding: 4px 15px; min-width: 80px; }")
        
        main_layout.addWidget(self.buttons)

        if self.grafico_original_para_edicao:
            self._carregar_dados_iniciais()
        else:
            self.point_data_panel.add_series_item()
            self.point_data_panel.add_data_point_item()
            self._on_data_mode_changed()
            self.redraw()

    def _carregar_dados_iniciais(self):
        grafico = self.grafico_original_para_edicao
        
        if grafico.caminho_dados_json and os.path.exists(grafico.caminho_dados_json):
            try:
                with open(grafico.caminho_dados_json, 'r', encoding='utf-8') as f:
                    state_data = json.load(f)
                
                self.settings_panel.set_state(state_data)
                self.point_data_panel.set_state(state_data.get('point_data', {}))
                self.grid_data_panel.set_state(state_data.get('grid_data', {}))
                
            except Exception as e:
                QMessageBox.warning(self, "Erro ao Carregar Dados",
                                    f"Não foi possível carregar os dados do gráfico 3D salvo:\n{e}\nO editor começará com os padrões.")
        
        self.settings_panel.title_input.setText(grafico.titulo)
        self.settings_panel.source_input.setText(grafico.fonte)
        
        self._on_data_mode_changed()
        self.redraw()

    @Slot()
    def _on_data_mode_changed(self):
        mode = self.settings_panel.data_mode_cb.currentText()
        if mode == 'Dados por Pontos':
            self.data_stack.setCurrentIndex(0)
        else:
            self.data_stack.setCurrentIndex(1)
        self.trigger_redraw()

    @Slot()
    def trigger_redraw(self):
        if self.settings_panel.live_cb.isChecked():
            self.redraw_timer.start()

    def _plot_points(self, ax, s):
        series_list = s['series_data']
        plot_type = s['type'] 
        legend_proxies, legend_labels = [], []
        
        if not series_list:
            return [], []

        for i, series in enumerate(series_list):
            legend = series['legend']; color = series['color']
            try: 
                x = np.array([float(p) for p in series['x_data']])
                y = np.array([float(p) for p in series['y_data']])
                z = np.array([float(p) for p in series['z_data']])
            except ValueError: continue
            
            if not (len(x) == len(y) == len(z)): continue
            if len(x) == 0: continue

            if plot_type == 'Dispersão (Pontos)':
                ax.scatter(x, y, z, color=color, s=40)
                legend_proxies.append(Line2D([0], [0], linestyle="none", c=color, marker='o'))
                legend_labels.append(legend)
                
            elif plot_type == 'Linhas 3D':
                ax.plot(x, y, z, color=color)
                legend_proxies.append(Line2D([0], [0], linestyle="-", c=color, lw=2))
                legend_labels.append(legend)

            elif plot_type == 'Barras 3D':
                z_base = np.zeros_like(z)
                dx = np.ones_like(x) * 0.5
                dy = np.ones_like(y) * 0.5
                ax.bar3d(x - dx/2, y - dy/2, z_base, dx, dy, z, color=color, alpha=0.8, shade=True)
                legend_proxies.append(Line2D([0], [0], linestyle="none", c=color, marker='s'))
                legend_labels.append(legend)

            elif plot_type == 'Superfície (Triangulação)':
                if len(x) >= 3:
                    try:
                        ax.plot_trisurf(x, y, z, color=color, alpha=0.6, linewidth=0.2, shade=True)
                        legend_proxies.append(Line2D([0], [0], linestyle="none", c=color, marker='s', alpha=0.6))
                        legend_labels.append(legend)
                    except: pass 

            elif plot_type == 'Arame (Wireframe)': 
                 if len(x) >= 3:
                    try:
                        ax.plot_trisurf(x, y, z, color=(0,0,0,0), edgecolor=color, linewidth=1)
                        legend_proxies.append(Line2D([0], [0], linestyle="none", markeredgecolor=color, markerfacecolor='none', marker='s'))
                        legend_labels.append(legend)
                    except: pass

        return legend_proxies, legend_labels

    def _plot_grid(self, ax, data_state, s):
        plot_type = s['type']
        
        z_grid = np.array(data_state['z_grid'])
        rows, cols = z_grid.shape
        
        x_vals = np.linspace(data_state['x_min'], data_state['x_max'], cols)
        y_vals = np.linspace(data_state['y_min'], data_state['y_max'], rows)
        X, Y = np.meshgrid(x_vals, y_vals)
        Z = z_grid
        
        color = data_state['grid_color']
        
        plot_kwargs = {
            'alpha': 0.8,
            'rstride': 1,
            'cstride': 1,
            'linewidth': 0,
            'antialiased': True,
            'shade': True
        }
        
        if data_state['use_cmap']:
            plot_kwargs['cmap'] = data_state['cmap_name']
        else:
            plot_kwargs['color'] = color

        if plot_type == 'Superfície de Grade':
            ax.plot_surface(X, Y, Z, **plot_kwargs)
        
        elif plot_type == 'Malha de Grade (Wireframe)':
            if 'cmap' in plot_kwargs: del plot_kwargs['cmap']; plot_kwargs['color'] = color 
            ax.plot_wireframe(X, Y, Z, rstride=1, cstride=1, color=color)
            
        else:
            ax.scatter(X.flatten(), Y.flatten(), Z.flatten(), color=color)

    @Slot()
    def _on_rotation_tick(self):
        if not self.fig or not self.fig.axes:
            return
        
        try:
            ax = self.fig.axes[0]
            if not isinstance(ax, Axes3D):
                return
                
            current_elev = self.settings_panel.elev_slider.value()
            current_azim = self.settings_panel.azim_slider.value()
            
            new_azim = (current_azim + 2) % 360 
            
            self.settings_panel.azim_slider.setValue(new_azim)
            
            ax.view_init(elev=current_elev, azim=new_azim)
            self.canvas.draw()
            
        except Exception as e:
            print(f"Erro na rotação: {e}")
            self.rotation_timer.stop() 

    @Slot()
    def redraw(self):
        s = {} 
        try:
            point_data = self.point_data_panel.get_state()
            grid_data = self.grid_data_panel.get_state()
            settings_state = self.settings_panel.get_state()
            s = {**settings_state} 

            is_rotating = s.get('rotate_view', False)
            
            if is_rotating:
                if not self.rotation_timer.isActive():
                    self.rotation_timer.start()
                self.settings_panel.elev_slider.setEnabled(False)
                self.settings_panel.azim_slider.setEnabled(False)
            else:
                if self.rotation_timer.isActive():
                    self.rotation_timer.stop()
                self.settings_panel.elev_slider.setEnabled(True)
                self.settings_panel.azim_slider.setEnabled(True)

            figure_width = s.get('figure_width_inches', 8.0)
            figure_height = s.get('figure_height_inches', 6.0)
            
            current_size = (0,0)
            if self.fig: current_size = self.fig.get_size_inches()

            if self.fig is None or current_size[0] != figure_width or current_size[1] != figure_height:
                if self.toolbar: self.preview_layout.removeWidget(self.toolbar); self.toolbar.deleteLater()
                if self.canvas: self.preview_layout.removeWidget(self.canvas); self.canvas.deleteLater()

                self.fig = Figure(figsize=(figure_width, figure_height))
                self.canvas = FigureCanvas(self.fig)
                self.toolbar = NavigationToolbar(self.canvas, self)
                
                self.preview_layout.addWidget(self.toolbar)
                self.preview_layout.addWidget(self.canvas, 1)

            with plt.style.context(s['style']):
                self.fig.clear()
                ax = self.fig.add_subplot(projection='3d')
                
                # --- INÍCIO: Título Condicional ---
                if s.get('show_title', True):
                    ax.set_title(s['title'], fontsize=12) 
                # --- FIM: Título Condicional ---
                
                ax.set_xlabel(s['xlabel'], fontsize=10)
                ax.set_ylabel(s['ylabel'], fontsize=10)
                ax.set_zlabel(s['zlabel'], fontsize=10) 
                ax.tick_params(axis='both', labelsize=8)
                
                proxies, labels = [], []
                
                if s['data_mode'] == 'Dados por Pontos':
                    s['series_data'] = point_data['series_data'] 
                    proxies, labels = self._plot_points(ax, s)
                else:
                    self._plot_grid(ax, grid_data, s)
                
                if s['show_legend'] and proxies:
                    size = LEGEND_SIZE_MAP.get(s['legend_size'], 10)
                    ax.legend(proxies, labels, loc='center left', bbox_to_anchor=(1.0, 0.5), fontsize=size)
                
                ax.set_xlim(left=s['x_min'], right=s['x_max'])
                ax.set_ylim(bottom=s['y_min'], top=s['y_max'])
                ax.set_zlim(bottom=s['z_min'], top=s['z_max']) 
                
                ax.view_init(elev=s['elev'], azim=s['azim'])
                
                try: self.fig.tight_layout()
                except ValueError: pass
                
                if not self.rotation_timer.isActive():
                    self.canvas.draw()
                
        except ValueError as e:
            self.fig.clear(); ax = self.fig.add_subplot(111) 
            error_message = f"Erro nos dados:\n{e}"
            ax.text(0.5, 0.5, error_message, ha='center', va='center', color='red', fontsize=12, wrap=True)
            self.canvas.draw()
        except Exception as e:
            msg = f'Erro ao redesenhar Matplotlib:\n{e}\n\n{traceback.format_exc()}'
            QMessageBox.critical(self, 'Erro de Plotagem', msg)
            if self.rotation_timer.isActive(): 
                self.rotation_timer.stop()

    def _sanitizar_nome_arquivo(self, nome: str) -> str:
        nome = re.sub(r'[<>:"/\\|?*]', '_', nome)
        nome = nome.replace(' ', '_')
        return nome[:100]

    def accept(self):
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
            
        novo_titulo = self.settings_panel.title_input.text().strip()
        if not novo_titulo:
            QMessageBox.warning(self, "Campo Obrigatório", "O 'Título (Legenda)' não pode estar vazio.")
            return

        for g_existente in self.banco_graficos_3d:
            if g_existente.titulo.strip().lower() == novo_titulo.lower():
                if self.grafico_original_para_edicao is g_existente:
                    continue 
                QMessageBox.warning(self, "Título Duplicado", 
                                    f"Já existe um gráfico 3D com o título '{novo_titulo}'.\n"
                                    "O título deve ser único.")
                return 

        pasta_imagens = "_imagens_processadas"
        pasta_dados_chart = "_chart_data"
        os.makedirs(pasta_imagens, exist_ok=True)
        os.makedirs(pasta_dados_chart, exist_ok=True)
        
        nome_arquivo_base = self._sanitizar_nome_arquivo(novo_titulo)
        caminho_imagem_png = os.path.join(pasta_imagens, f"{nome_arquivo_base}_3d.png")
        caminho_dados_json = os.path.join(pasta_dados_chart, f"{nome_arquivo_base}_3d.chartjson")
        
        if self.grafico_original_para_edicao and self.grafico_original_para_edicao.titulo != novo_titulo:
            try:
                if os.path.exists(self.grafico_original_para_edicao.caminho_imagem_processada):
                    os.remove(self.grafico_original_para_edicao.caminho_imagem_processada)
                if os.path.exists(self.grafico_original_para_edicao.caminho_dados_json):
                    os.remove(self.grafico_original_para_edicao.caminho_dados_json)
            except OSError as e:
                print(f"Aviso: Não foi possível remover arquivos antigos do gráfico 3D renomeado: {e}")

        try:
            self.fig.savefig(caminho_imagem_png, dpi=300, bbox_inches='tight')
            
            point_data = self.point_data_panel.get_state()
            grid_data = self.grid_data_panel.get_state()
            settings_state = self.settings_panel.get_state()
            
            full_state = {
                **settings_state,
                'point_data': point_data,
                'grid_data': grid_data
            }
            
            with open(caminho_dados_json, 'w', encoding='utf-8') as f:
                json.dump(full_state, f, indent=4)
                
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Salvar Arquivos", f"Não foi possível salvar os arquivos do gráfico 3D:\n{e}")
            return
            
        self.grafico_final.titulo = novo_titulo
        self.grafico_final.fonte = self.settings_panel.source_input.text().strip()
        self.grafico_final.caminho_imagem_processada = caminho_imagem_png
        self.grafico_final.caminho_dados_json = caminho_dados_json
        self.grafico_final.largura_cm = 16.0 

        super().accept()

    def reject(self):
        if self.rotation_timer.isActive():
            self.rotation_timer.stop()
        super().reject()

    def get_dados_grafico_3d(self) -> Grafico3D:
        return self.grafico_final


# --- INICIALIZADOR STANDALONE (Para testes) ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        # Tenta carregar o tema escuro para o teste standalone
        import qdarktheme
        app.setStyleSheet(qdarktheme.load_stylesheet())
    except ImportError:
        pass # Roda com o tema padrão do sistema

    dialog = Grafico3DDialog()
    dialog.exec()
    
    sys.exit()