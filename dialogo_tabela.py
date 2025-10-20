# dialogo_tabela.py
# Descrição: Janela de diálogo para a criação e edição detalhada de tabelas.

from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, 
                               QTableWidget, QTableWidgetItem, QDialogButtonBox,
                               QMessageBox) # ADICIONADO: QMessageBox para o alerta

from documento import Tabela

class TabelaDialog(QDialog):
    def __init__(self, tabela: Tabela = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Tabela ABNT")
        self.setMinimumSize(600, 400)

        self.tabela = tabela if tabela else Tabela(dados=[["Cabeçalho 1", "Cabeçalho 2"], ["Dado 1", "Dado 2"]])

        self.layout = QVBoxLayout(self)

        self.titulo_input = QLineEdit(self.tabela.titulo)
        self.fonte_input = QLineEdit(self.tabela.fonte)
        
        self.estilo_borda_combo = QComboBox()
        self.estilo_borda_combo.addItems(["ABNT (Padrão)", "Grade Completa"])
        if self.tabela.estilo_borda == 'grade':
            self.estilo_borda_combo.setCurrentIndex(1)
        
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Título (sem a palavra 'Tabela X'):", self.titulo_input)
        form_layout.addRow("Fonte:", self.fonte_input)
        form_layout.addRow("Estilo da Borda:", self.estilo_borda_combo)
        self.layout.addLayout(form_layout)

        self.table_widget = QTableWidget()
        self.popular_tabela_widget()
        self.layout.addWidget(self.table_widget)

        btn_layout = QHBoxLayout()
        btn_add_linha = QPushButton("Adicionar Linha"); btn_del_linha = QPushButton("Remover Linha")
        btn_add_col = QPushButton("Adicionar Coluna"); btn_del_col = QPushButton("Remover Coluna")
        btn_layout.addWidget(btn_add_linha); btn_layout.addWidget(btn_del_linha)
        btn_layout.addWidget(btn_add_col); btn_layout.addWidget(btn_del_col)
        btn_add_linha.clicked.connect(self.adicionar_linha); btn_del_linha.clicked.connect(self.remover_linha)
        btn_add_col.clicked.connect(self.adicionar_coluna); btn_del_col.clicked.connect(self.remover_coluna)
        self.layout.addLayout(btn_layout)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept) # Esta conexão agora chama nosso método personalizado
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    # =============================================================================
    # NOVO MÉTODO: Sobrescreve o comportamento padrão do botão "OK"
    # =============================================================================
    def accept(self):
        """
        Executa a validação ANTES de fechar a janela.
        """
        # 1. Verifica se o título está vazio
        if not self.titulo_input.text().strip():
            # 2. Se estiver vazio, exibe o alerta
            QMessageBox.warning(self, "Título Obrigatório", 
                                      "O título da tabela não pode estar vazio. Por favor, preencha o campo para salvar.")
            # 3. Impede o fechamento da janela ao não chamar super().accept()
            return
        
        # 4. Se o título for válido, chama o comportamento padrão para fechar a janela
        super().accept()
    # =============================================================================

    def popular_tabela_widget(self):
        dados = self.tabela.dados
        if not dados: return
        num_rows = len(dados); num_cols = len(dados[0])
        self.table_widget.setRowCount(num_rows); self.table_widget.setColumnCount(num_cols)
        for i, row_data in enumerate(dados):
            for j, cell_data in enumerate(row_data):
                self.table_widget.setItem(i, j, QTableWidgetItem(cell_data))

    def adicionar_linha(self): self.table_widget.insertRow(self.table_widget.rowCount())
    
    def remover_linha(self):
        row = self.table_widget.currentRow()
        if row != -1: self.table_widget.removeRow(row)

    def adicionar_coluna(self): self.table_widget.insertColumn(self.table_widget.columnCount())
    
    def remover_coluna(self):
        col = self.table_widget.currentColumn()
        if col != -1: self.table_widget.removeColumn(col)
            
    def get_dados_tabela(self) -> Tabela:
        self.tabela.titulo = self.titulo_input.text()
        self.tabela.fonte = self.fonte_input.text()
        self.tabela.estilo_borda = 'abnt' if self.estilo_borda_combo.currentIndex() == 0 else 'grade'
        
        num_rows = self.table_widget.rowCount()
        num_cols = self.table_widget.columnCount()
        novos_dados = []
        for i in range(num_rows):
            row_data = []
            for j in range(num_cols):
                item = self.table_widget.item(i, j)
                row_data.append(item.text() if item else "")
            novos_dados.append(row_data)
        
        self.tabela.dados = novos_dados
        return self.tabela