# dialogo_tabela.py
# Descrição: Janela de diálogo para a criação e edição detalhada de tabelas.
# Versão atualizada com opção de centralização de conteúdo.
# ATUALIZAÇÃO: Adicionada verificação de título duplicado
# no método accept() para evitar bugs de referência.

from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, 
                               QTableWidget, QTableWidgetItem, QDialogButtonBox,
                               QMessageBox, QCheckBox) # Adicionado QCheckBox

from documento import Tabela

class TabelaDialog(QDialog):
    
    # --- INÍCIO DA MODIFICAÇÃO (Adiciona banco_tabelas) ---
    def __init__(self, tabela: Tabela = None, banco_tabelas: list[Tabela] = None, parent: QWidget = None):
    # --- FIM DA MODIFICAÇÃO ---
        
        super().__init__(parent)
        self.setWindowTitle("Editor de Tabela ABNT")
        self.setMinimumSize(600, 400)

        # --- INÍCIO DA MODIFICAÇÃO (Armazena dependências) ---
        self.tabela_original_para_edicao = tabela
        self.tabela = tabela if tabela else Tabela(dados=[["Cabeçalho 1", "Cabeçalho 2"], ["Dado 1", "Dado 2"]])
        self.banco_tabelas = banco_tabelas if banco_tabelas else []
        # --- FIM DA MODIFICAÇÃO ---

        self.layout = QVBoxLayout(self)

        self.titulo_input = QLineEdit(self.tabela.titulo)
        self.fonte_input = QLineEdit(self.tabela.fonte)
        
        self.estilo_borda_combo = QComboBox()
        self.estilo_borda_combo.addItems(["ABNT (Padrão)", "Grade Completa"])
        if self.tabela.estilo_borda == 'grade':
            self.estilo_borda_combo.setCurrentIndex(1)
        
        # --- NOVO CHECKBOX DE CENTRALIZAÇÃO ---
        self.centralizar_check = QCheckBox("Centralizar conteúdo das células (Padrão ABNT)")
        self.centralizar_check.setChecked(self.tabela.centralizar_conteudo)
        self.centralizar_check.setToolTip(
            "Desmarque esta opção apenas em casos específicos onde a ABNT\n"
            "permite alinhamento à esquerda (ex: tabelas com muito texto)."
        )
        # --- FIM DO NOVO CHECKBOX ---
        
        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Título (sem a palavra 'Tabela X'):", self.titulo_input)
        form_layout.addRow("Fonte:", self.fonte_input)
        form_layout.addRow("Estilo da Borda:", self.estilo_borda_combo)
        form_layout.addRow(self.centralizar_check) # Adiciona o checkbox ao formulário
        
        self.layout.addLayout(form_layout)

        self.table_widget = QTableWidget()
        self.popular_tabela_widget()
        self.layout.addWidget(self.table_widget)

        btn_layout = QHBoxLayout()
        btn_add_linha = QPushButton("Adicionar Linha")
        btn_del_linha = QPushButton("Remover Linha")
        btn_add_col = QPushButton("Adicionar Coluna")
        btn_del_col = QPushButton("Remover Coluna")
        
        # --- MUDANÇA (Define classes QSS) ---
        btn_add_linha.setProperty("cssClass", "utility")
        btn_del_linha.setProperty("cssClass", "destructive")
        btn_add_col.setProperty("cssClass", "utility")
        btn_del_col.setProperty("cssClass", "destructive")
        # ------------------------------------

        btn_layout.addWidget(btn_add_linha); btn_layout.addWidget(btn_del_linha)
        btn_layout.addWidget(btn_add_col); btn_layout.addWidget(btn_del_col)
        btn_add_linha.clicked.connect(self.adicionar_linha); btn_del_linha.clicked.connect(self.remover_linha)
        btn_add_col.clicked.connect(self.adicionar_coluna); btn_del_col.clicked.connect(self.remover_coluna)
        self.layout.addLayout(btn_layout)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept) 
        self.buttons.rejected.connect(self.reject)
        
        # --- MUDANÇA (Define classe QSS para o botão Cancelar) ---
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setProperty("cssClass", "utility")
        # --------------------------------------------------------

        self.layout.addWidget(self.buttons)

    def accept(self):
        """
        Executa a validação ANTES de fechar a janela.
        """
        
        # --- INÍCIO DA MODIFICAÇÃO (Verificação de Duplicidade) ---
        novo_titulo = self.titulo_input.text().strip()

        if not novo_titulo:
            QMessageBox.warning(self, "Título Obrigatório", 
                                  "O título da tabela não pode estar vazio. Por favor, preencha o campo para salvar.")
            return # Não fecha o diálogo

        # Compara com todas as tabelas no banco
        for tabela_existente in self.banco_tabelas:
            # 1. Compara o título
            if tabela_existente.titulo.strip().lower() == novo_titulo.lower():
                
                # 2. Verifica se é a MESMA tabela que estamos editando
                if self.tabela_original_para_edicao is tabela_existente:
                    continue # É o mesmo objeto, permite salvar.

                # 3. Se for uma tabela DIFERENTE com o mesmo nome, bloqueia.
                QMessageBox.warning(self, "Título Duplicado", 
                                    f"Já existe uma tabela com o título '{novo_titulo}'.\n"
                                    "O título da tabela deve ser único.")
                return # Não fecha o diálogo
        # --- FIM DA MODIFICAÇÃO ---
        
        super().accept()

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
        # Atualiza o título com o texto já tratado
        self.tabela.titulo = self.titulo_input.text().strip()
        self.tabela.fonte = self.fonte_input.text()
        self.tabela.estilo_borda = 'abnt' if self.estilo_borda_combo.currentIndex() == 0 else 'grade'
        
        # --- SALVA O VALOR DO CHECKBOX ---
        self.tabela.centralizar_conteudo = self.centralizar_check.isChecked()
        # -----------------------------------
        
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