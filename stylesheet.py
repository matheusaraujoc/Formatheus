# stylesheet.py
# Descrição: Folha de estilo QSS global para o Formatheus.
# Versão 3.7: Corrige o "ValueError: Single '}' encountered..."
# escapando todos os colchetes literais do QSS (ex: {{, }}).

import os

# --- Lógica de Caminho de Ícone ---
_STYLESHEET_DIR = os.path.dirname(os.path.abspath(__file__))
_ICON_PATH = os.path.join(_STYLESHEET_DIR, 'assets', 'icons', 'arrow_down.png')
ICON_URL_PATH = _ICON_PATH.replace(os.path.sep, '/')
# ---------------------------------

# --- Paleta de Cores (para Referência) ---
# ... (mesma paleta de antes) ...

# NOTA: Todos os { e } literais foram dobrados para {{ e }} para 
#       escapar a função .format() do Python.
_STYLE_SHEET_TEMPLATE = """

/* --- Fundo e Fonte Global --- */
QWidget {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    color: #333333;
    background-color: #f8f8f8; /* BG_LIGHT */
}}

/* --- Títulos (usar setProperty("cssClass", "titulo")) --- */
QLabel[cssClass="titulo"] {{
    font-size: 18px;
    font-weight: bold;
    color: #005a9e; /* PRIMARY_HOVER */
    padding-top: 10px;
    padding-bottom: 5px;
}}

/* --- Abas (Tabs) --- */
QTabWidget::pane {{
    border: 1px solid #dcdcdc; /* BORDER_COLOR */
    background-color: #ffffff; /* BG_WHITE */
    border-top-right-radius: 5px;
    border-bottom-left-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QTabBar::tab {{
    background-color: #f0f0f0; 
    border: 1px solid #dcdcdc; /* BORDER_COLOR */
    border-bottom: none;
    padding: 8px 12px;
    margin-right: 1px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}
QTabBar::tab:selected {{
    background-color: #ffffff; /* BG_WHITE */
    border-bottom: 1px solid #ffffff; /* Cobre a borda do pane */
    font-weight: bold;
}}
QTabBar::tab:!selected:hover {{
    background-color: #e0e0e0;
}}

/* --- Botões --- */
QPushButton {{
    background-color: #0078d4; /* PRIMARY_COLOR */
    color: white;
    border: none;
    padding: 8px 12px;
    border-radius: 5px;
    font-size: 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    background-color: #005a9e; /* PRIMARY_HOVER */
}}
QPushButton:disabled {{
    background-color: #aaaaaa;
    color: #555555;
}}

QPushButton#GenerateBtn {{
    font-size: 16px;
    font-weight: bold;
    padding: 10px;
    border-radius: 0px; 
}}

QPushButton[cssClass="destructive"] {{
    background-color: #d13438;
    min-width: 90px;
}}
QPushButton[cssClass="destructive"]:hover {{
    background-color: #a2282b;
}}

QPushButton[cssClass="utility"] {{
    background-color: #e0e0e0;
    color: #333333;
    min-width: 90px;
}}
QPushButton[cssClass="utility"]:hover {{
    background-color: #c8c8c8;
}}

/* --- Campos de Entrada --- */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background-color: #ffffff; /* BG_WHITE */
    border: 1px solid #dcdcdc; /* BORDER_COLOR */
    border-radius: 5px;
    padding: 5px;
    min-height: 20px;
}}
QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid #0078d4; /* PRIMARY_COLOR */
}}

/* --- Correção do QComboBox (Setas) --- */
QComboBox {{
    padding-right: 5px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px; /* Largura do botão */
    
    border-left: 1px solid #dcdcdc; /* Linha separadora */
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 #f8f8f8, stop:1 #e0e0e0);

    /* Seta (PNG Base64) como FUNDO do botão drop-down */
    /* ESTA É A ÚNICA LINHA QUE USA O COLCHETE SIMPLES */
    background-image: url({ICON_URL_PATH});
    background-position: center center;
    background-repeat: no-repeat;
}}
QComboBox::drop-down:hover {{
    background-color: #c8c8c8; /* UTILITY_HOVER */
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}

QComboBox QAbstractItemView {{
    background-color: #ffffff;
    border: 1px solid #dcdcdc;
    selection-background-color: #0078d4;
    selection-color: white;
}}


/* --- Listas, Árvores e Tabelas (Widgets) --- */
QListWidget, QTreeWidget, QTableWidget {{
    background-color: #ffffff; /* BG_WHITE */
    border: 1px solid #dcdcdc; /* BORDER_COLOR */
    border-radius: 5px;
    alternate-background-color: #f8f8f8; /* BG_LIGHT (para zebrado, se habilitado) */
}}
QListWidget::item:hover, QTreeWidget::item:hover, QTableWidget::item:hover {{
    background-color: #f0f0f0; /* Fundo de hover mais claro */
    color: #333333;
}}

/* Cor de seleção mais suave */
QListWidget::item:selected, QTreeWidget::item:selected, QTableWidget::item:selected {{
    background-color: #dbeafe; /* Azul claro e suave */
    color: #333333; /* Texto escuro para contraste */
}}

/* --- Correção (Tela Inicial - Estilo de Cartão) --- */
QWidget#ProjetoRecenteItem {{
    background-color: white;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
}}

QListWidget::item:hover QWidget#ProjetoRecenteItem {{
    background-color: #f8f8f8; /* BG_LIGHT */
    border: 1px solid #c8c8c8;
}}

/* Usamos a cor da "Lista" genérica para a seleção do cartão */
QListWidget::item:selected QWidget#ProjetoRecenteItem {{
    background-color: #dbeafe; /* Azul claro suave */
    border: 1px solid #0078d4; /* Borda primária */
}}

QLabel[cssClass="caminho_projeto_recente"] {{
    color: #666666; /* Cor padrão para o caminho */
}}

QListWidget::item:selected QLabel,
QListWidget::item:selected QLabel[cssClass="caminho_projeto_recente"] {{
    color: #333333; /* Texto escuro */
    background-color: transparent; /* Garante que o label não pinte sobre o azul */
}}
/* ---------------------------------------------------- */


/* Header de Árvores e Tabelas */
QHeaderView::section {{
    background-color: #f0f0f0;
    border: 1px solid #dcdcdc;
    padding: 4px;
    font-weight: bold;
}}

/* --- Outros Componentes --- */
QSplitter::handle {{
    background-color: #dcdcdc;
    width: 2px;
}}
QSplitter::handle:hover {{
    background-color: #0078d4;
    width: 4px;
}}

QMenuBar {{
    background-color: #ffffff;
    border-bottom: 1px solid #dcdcdc;
}}
QMenuBar::item:selected {{
    background-color: #e0e0e0;
}}
QMenu {{
    background-color: #ffffff;
    border: 1px solid #cccccc;
}}
QMenu::item:selected {{
    background-color: #0078d4;
    color: white;
}}

QCheckBox {{
    padding: 2px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

/* --- Barras de Rolagem (COM CORREÇÃO) --- */
QScrollBar:vertical {{
    border: none;
    background: #f0f0f0;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: #c0c0c0;
    min-height: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{
    background: #a0a0a0;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    width: 0px;
    background: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    border: none;
    background: #f0f0f0;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background: #c0c0c0;
    min-width: 20px;
    border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{
    background: #a0a0a0;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0px;
    width: 0px;
    background: none;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: none;
}}


/* --- Caixas de Diálogo --- */
QMessageBox, QInputDialog, QDialog {{
    background-color: #f8f8f8; /* BG_LIGHT */
}}

QMessageBox QLabel {{
    font-size: 14px;
}}

QMessageBox QPushButton, QDialogButtonBox QPushButton {{
    min-width: 90px; /* Garante que OK/Cancelar tenham boa largura */
}}

QInputDialog QLineEdit {{
    min-width: 250px; /* Garante que o input não seja minúsculo */
}}

"""

def get_style_sheet():
    """
    Retorna a string da folha de estilo formatada com os
    caminhos de ícone corretos.
    """
    return _STYLE_SHEET_TEMPLATE.format(ICON_URL_PATH=ICON_URL_PATH)