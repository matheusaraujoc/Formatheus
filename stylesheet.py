# stylesheet.py
# Descrição: Folha de estilo QSS ESTRUTURAL para o Formatheus.
# Versão 4.2: Adiciona borda simples a TODOS os botões e estilo para QToolTip.

import os

# --- Lógica de Caminho de Ícone ---
_STYLESHEET_DIR = os.path.dirname(os.path.abspath(__file__))
_ICON_PATH = os.path.join(_STYLESHEET_DIR, 'assets', 'icons', 'arrow_down.png')
# Converte o caminho para um formato que o QSS entende (URL com /)
ICON_URL_PATH = _ICON_PATH.replace(os.path.sep, '/')
# ---------------------------------

_STYLE_SHEET_TEMPLATE = """

/* --- Fundo e Fonte Global --- */
QWidget {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 14px;
    /* Cores de fundo e texto são controladas pelo qdarktheme */
}}

/* --- Dicas (Tooltips) --- */
QToolTip {{
    /* Cores de fundo, texto e borda controladas pelo qdarktheme */
    padding: 5px;
    border-radius: 4px;
}}

/* --- Títulos (usar setProperty("cssClass", "titulo")) --- */
QLabel[cssClass="titulo"] {{
    font-size: 18px;
    font-weight: bold;
    /* Cor controlada pelo qdarktheme (será a cor primária) */
    padding-top: 10px;
    padding-bottom: 5px;
}}

/* --- Abas (Tabs) --- */
QTabWidget::pane {{
    /* Borda e fundo controlados pelo qdarktheme */
    border-top-right-radius: 5px;
    border-bottom-left-radius: 5px;
    border-bottom-right-radius: 5px;
}}
QTabBar::tab {{
    /* Borda e fundo controlados pelo qdarktheme */
    border-bottom: none;
    padding: 8px 12px;
    margin-right: 1px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}}
QTabBar::tab:selected {{
    /* Fundo controlado pelo qdarktheme (cor do 'pane') */
    font-weight: bold;
}}
QTabBar::tab:!selected:hover {{
    /* Cor controlada pelo qdarktheme */
}}

/* --- Botões --- */
QPushButton {{
    /* MUDANÇA: Borda padrão para TODOS os botões */
    border: 1px solid palette(mid); 
    padding: 8px 12px;
    border-radius: 5px;
    font-size: 14px;
    min-height: 20px;
}}
QPushButton:hover {{
    /* Cor de fundo e borda controladas pelo qdarktheme no hover */
}}

/* Botão de Ação Primária (Azul) */
QPushButton[cssClass="primary"] {{
    /* Fundo, cor e borda controlados pelo qdarktheme */
    font-weight: bold;
}}

/* Botão Gerar Docx (canto) */
QPushButton#GenerateBtn {{
    font-size: 16px;
    font-weight: bold;
    padding: 10px;
    border-radius: 0px; 
    /* Borda e cor controladas pelo qdarktheme */
}}

/* Botão Destrutivo (MANTEMOS A COR VERMELHA) */
QPushButton[cssClass="destructive"] {{
    background-color: #d13438;
    color: white; 
    min-width: 90px;
    border: 1px solid #d13438;
}}
QPushButton[cssClass="destructive"]:hover {{
    background-color: #a2282b;
    border: 1px solid #a2282b;
}}

/* Botão Utilitário (apenas define tamanho) */
QPushButton[cssClass="utility"] {{
    min-width: 90px;
    /* Borda já definida no QPushButton base */
}}

/* Botão com Borda (Outline) */
QPushButton[cssClass="outline-button"] {{
    background-color: transparent;
    /* Borda já definida no QPushButton base */
}}

/* --- Campos de Entrada --- */
QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    /* Borda e fundo controlados pelo qdarktheme */
    border-radius: 5px;
    padding: 5px;
    min-height: 20px;
}}
/* Foco é controlado pelo qdarktheme */

/* --- Correção do QComboBox (Setas) --- */
QComboBox {{
    padding-right: 5px;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    
    /* Borda e fundo controlados pelo qdarktheme */
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    
    /* MANTEMOS NOSSA SETA CUSTOMIZADA */
    image: url({ICON_URL_PATH}); 
    background-position: center center;
    background-repeat: no-repeat;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
    width: 0px;
    height: 0px;
}}
/* Dropdown (popup) é controlado pelo qdarktheme */


/* --- Listas, Árvores e Tabelas (Widgets) --- */
QListWidget, QTreeWidget, QTableWidget {{
    /* Borda e fundo controlados pelo qdarktheme */
    border-radius: 5px;
}}
/* Hover e Seleção são controlados pelo qdarktheme */


/* --- Estilo de Cartão (Tela Inicial) --- */
QWidget#ProjetoRecenteItem {{
    /* Borda e fundo controlados pelo qdarktheme */
    border-radius: 5px;
}}

QLabel[cssClass="caminho_projeto_recente"] {{
    color: #888888; 
}}
QListWidget::item:selected QLabel[cssClass="caminho_projeto_recente"] {{
    color: inherit; /* Herda a cor do texto selecionado do tema */
}}
/* ---------------------------------------------------- */


/* Header de Árvores e Tabelas */
QHeaderView::section {{
    /* Borda e fundo controlados pelo qdarktheme */
    padding: 4px;
    font-weight: bold;
}}

/* --- Outros Componentes --- */
QSplitter::handle {{
    /* Cor controlada pelo qdarktheme */
    width: 2px;
}}
QSplitter::handle:hover {{
    /* Cor controlada pelo qdarktheme */
    width: 4px;
}}

/* Menus são controlados pelo qdarktheme */
QMenuBar {{}}
QMenuBar::item:selected {{}}
QMenu {{}}
QMenu::item:selected {{}}

QCheckBox {{
    padding: 2px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
}}

/* Barras de Rolagem (Controladas pelo qdarktheme) */

/* --- Caixas de Diálogo --- */
QMessageBox, QInputDialog, QDialog {{}}

QMessageBox QLabel {{
    font-size: 14px;
}}

QMessageBox QPushButton, QDialogButtonBox QPushButton {{
    min-width: 90px;
}}

QInputDialog QLineEdit {{
    min-width: 250px;
}}

"""

def get_style_sheet():
    """
    Retorna a string da folha de estilo formatada com os
    caminhos de ícone corretos.
    """
    return _STYLE_SHEET_TEMPLATE.format(ICON_URL_PATH=ICON_URL_PATH)