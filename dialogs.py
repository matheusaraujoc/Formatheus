# dialogs.py
# Descrição: Contém as classes de janelas de diálogo utilizadas pela aplicação.

import os
import shutil
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QFormLayout, QVBoxLayout, QDialogButtonBox, QListWidget,
                               QListWidgetItem, QTableWidget, QTableWidgetItem, QMessageBox,
                               QPushButton, QHBoxLayout, QFileDialog, QDoubleSpinBox)
from PySide6.QtGui import QPixmap
from PIL import Image
from datetime import datetime

from referencia import Livro, Artigo, Site
from documento import Tabela, Figura

LARGURA_MAXIMA_CM = 16.0

class DialogoFigura(QDialog):
    def __init__(self, figura: Figura = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Figura ABNT")
        self.setMinimumSize(800, 400)

        self.figura = figura if figura else Figura()
        self.caminho_imagem_atual = self.figura.caminho_original or self.figura.caminho_processado

        self.layout = QHBoxLayout(self)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        form_layout = QtWidgets.QFormLayout()

        self.titulo_input = QLineEdit(self.figura.titulo)
        self.fonte_input = QLineEdit(self.figura.fonte)
        self.caminho_input = QLineEdit(self.figura.caminho_original)
        self.caminho_input.setReadOnly(True)
        self.largura_combo = QComboBox()
        self.largura_combo.addItems(["Pequena (8 cm)", "Média (12 cm)", "Grande (Largura Máxima)"])

        if self.figura.largura_cm == 8.0: self.largura_combo.setCurrentIndex(0)
        elif self.figura.largura_cm == 12.0: self.largura_combo.setCurrentIndex(1)
        else: self.largura_combo.setCurrentIndex(2)

        btn_procurar = QPushButton("Procurar...")
        btn_procurar.clicked.connect(self.procurar_arquivo)

        caminho_layout = QHBoxLayout()
        caminho_layout.addWidget(self.caminho_input)
        caminho_layout.addWidget(btn_procurar)

        form_layout.addRow("Título (sem a palavra 'Figura X'):", self.titulo_input)
        form_layout.addRow("Fonte:", self.fonte_input)
        form_layout.addRow("Arquivo da Imagem:", caminho_layout)
        form_layout.addRow("Largura da Imagem:", self.largura_combo)

        left_layout.addLayout(form_layout)
        left_layout.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        left_layout.addWidget(self.buttons)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)

        self.preview_label = QLabel("A prévia da imagem aparecerá aqui.")
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px dashed gray; padding: 5px;")
        self.preview_label.setMinimumSize(300, 300)

        right_layout.addWidget(QLabel("<b>Pré-visualização:</b>"))
        right_layout.addWidget(self.preview_label, 1)

        self.layout.addWidget(left_panel, 1)
        self.layout.addWidget(right_panel, 1)

        if self.caminho_imagem_atual:
            self._atualizar_preview(self.caminho_imagem_atual)

    def procurar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem", "",
                  "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_input.setText(caminho)
            self.caminho_imagem_atual = caminho
            self._atualizar_preview(caminho)

    def _atualizar_preview(self, caminho_imagem):
        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self.preview_label.setText("Imagem não encontrada.")
            self.preview_label.setPixmap(QPixmap())
            return

        pixmap = QPixmap(caminho_imagem)
        scaled_pixmap = pixmap.scaled(self.preview_label.size(),
                                      QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                      QtCore.Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.caminho_imagem_atual:
            self._atualizar_preview(self.caminho_imagem_atual)

    def accept(self):
        if not self.titulo_input.text().strip():
            QMessageBox.warning(self, "Dados Incompletos", "O título da figura é obrigatório.")
            return
        if not self.caminho_input.text():
            QMessageBox.warning(self, "Dados Incompletos", "É necessário selecionar um arquivo de imagem.")
            return
        if not self._processar_imagem():
            return
        super().accept()

    def _processar_imagem(self) -> bool:
        caminho_original = self.caminho_input.text()
        if not caminho_original:
            return False
        if self.figura.caminho_original == caminho_original and self.figura.caminho_processado and os.path.exists(self.figura.caminho_processado):
             return True

        try:
            pasta_imagens = "_imagens_processadas"
            os.makedirs(pasta_imagens, exist_ok=True)
            nome_arquivo = os.path.basename(caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            caminho_saida = os.path.join(pasta_imagens, f"{nome_base}.png")
            contador = 1
            while os.path.exists(caminho_saida):
                caminho_saida = os.path.join(pasta_imagens, f"{nome_base}_{contador}.png")
                contador += 1
            with Image.open(caminho_original) as img:
                img = img.convert("RGB")
                largura_maxima_px = LARGURA_MAXIMA_CM * 37.8
                if img.width > largura_maxima_px:
                    ratio = largura_maxima_px / img.width
                    nova_altura = int(img.height * ratio)
                    img = img.resize((int(largura_maxima_px), nova_altura), Image.Resampling.LANCZOS)
                img.save(caminho_saida, "PNG")
                self.figura.caminho_processado = caminho_saida
                return True
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Processar Imagem", f"Não foi possível processar o arquivo de imagem:\n{e}")
            return False

    def get_dados_figura(self) -> Figura:
        self.figura.titulo = self.titulo_input.text()
        self.figura.fonte = self.fonte_input.text()
        self.figura.caminho_original = self.caminho_input.text()
        largura_str = self.largura_combo.currentText()
        if "Pequena" in largura_str: self.figura.largura_cm = 8.0
        elif "Média" in largura_str: self.figura.largura_cm = 12.0
        else: self.figura.largura_cm = LARGURA_MAXIMA_CM
        return self.figura

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
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def accept(self):
        if not self.titulo_input.text().strip():
            QMessageBox.warning(self, "Título Obrigatório", "O título da tabela não pode estar vazio.")
            return
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
        self.tabela.titulo = self.titulo_input.text()
        self.tabela.fonte = self.fonte_input.text()
        self.tabela.estilo_borda = 'abnt' if self.estilo_borda_combo.currentIndex() == 0 else 'grade'
        num_rows = self.table_widget.rowCount(); num_cols = self.table_widget.columnCount()
        novos_dados = []
        for i in range(num_rows):
            row_data = []
            for j in range(num_cols):
                item = self.table_widget.item(i, j)
                row_data.append(item.text() if item else "")
            novos_dados.append(row_data)
        self.tabela.dados = novos_dados
        return self.tabela

class ReferenciaDialog(QDialog):
    def __init__(self, ref=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adicionar/Editar Referência")
        self.layout = QVBoxLayout(self); self.form_layout = QFormLayout()
        self.tipo_combo = QComboBox(); self.tipo_combo.addItems(["Livro", "Artigo", "Site"])
        self.autores_input = QLineEdit(); self.autores_input.setPlaceholderText("Autor 1; Autor 2")
        self.titulo_input = QLineEdit(); self.ano_input = QLineEdit()
        self.campos_livro = { "Local": QLineEdit(), "Editora": QLineEdit() }
        self.campos_artigo = { "Revista": QLineEdit(), "Volume": QLineEdit(), "Pág. Inicial": QLineEdit(), "Pág. Final": QLineEdit() }
        self.campos_site = { "URL": QLineEdit(), "Data de Acesso": QLineEdit("dd/mm/aaaa") }
        self.layout.addWidget(QLabel("Tipo de Referência:")); self.layout.addWidget(self.tipo_combo)
        self.layout.addLayout(self.form_layout); self.form_layout.addRow("Autores:", self.autores_input)
        self.form_layout.addRow("Título:", self.titulo_input); self.form_layout.addRow("Ano:", self.ano_input)
        for label, widget in self.campos_livro.items(): self.form_layout.addRow(label, widget)
        for label, widget in self.campos_artigo.items(): self.form_layout.addRow(label, widget)
        for label, widget in self.campos_site.items(): self.form_layout.addRow(label, widget)
        self.tipo_combo.currentTextChanged.connect(self.update_form_visibility)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)
        if ref: self._popular_campos(ref)
        else: self.update_form_visibility(self.tipo_combo.currentText())

    def _popular_campos(self, ref):
        self.tipo_combo.setCurrentText(ref.tipo); self.autores_input.setText(ref.autores)
        self.titulo_input.setText(ref.titulo); self.ano_input.setText(str(ref.ano))
        if isinstance(ref, Livro): self.campos_livro["Local"].setText(ref.local); self.campos_livro["Editora"].setText(ref.editora)
        elif isinstance(ref, Artigo):
            self.campos_artigo["Revista"].setText(ref.revista); self.campos_artigo["Volume"].setText(ref.volume)
            self.campos_artigo["Pág. Inicial"].setText(str(ref.pagina_inicial)); self.campos_artigo["Pág. Final"].setText(str(ref.pagina_final))
        elif isinstance(ref, Site): self.campos_site["URL"].setText(ref.url); self.campos_site["Data de Acesso"].setText(ref.data_acesso)
        self.update_form_visibility(ref.tipo)

    def update_form_visibility(self, tipo):
        all_specific_fields = {**self.campos_livro, **self.campos_artigo, **self.campos_site}
        for widget in all_specific_fields.values():
            label = self.form_layout.labelForField(widget)
            if label: label.setVisible(False)
            widget.setVisible(False)
        fields_to_show = {}
        if tipo == "Livro": fields_to_show = self.campos_livro
        elif tipo == "Artigo": fields_to_show = self.campos_artigo
        elif tipo == "Site": fields_to_show = self.campos_site
        for widget in fields_to_show.values():
            label = self.form_layout.labelForField(widget)
            if label: label.setVisible(True)
            widget.setVisible(True)

    def get_data(self):
        tipo = self.tipo_combo.currentText()
        try: ano_val = int(self.ano_input.text()) if self.ano_input.text().isdigit() else 0
        except ValueError: ano_val = 0
        common_data = { "autores": self.autores_input.text(), "titulo": self.titulo_input.text(), "ano": ano_val }
        if tipo == "Livro":
            specific_data = { "local": self.campos_livro["Local"].text(), "editora": self.campos_livro["Editora"].text()}
            return Livro(**common_data, **specific_data)
        elif tipo == "Artigo":
            try: pg_ini, pg_fim = int(self.campos_artigo["Pág. Inicial"].text() or 0), int(self.campos_artigo["Pág. Final"].text() or 0)
            except ValueError: pg_ini, pg_fim = 0, 0
            specific_data = { "revista": self.campos_artigo["Revista"].text(), "volume": self.campos_artigo["Volume"].text(), "pagina_inicial": pg_ini, "pagina_final": pg_fim }
            return Artigo(**common_data, **specific_data)
        elif tipo == "Site":
            specific_data = { "url": self.campos_site["URL"].text(), "data_acesso": self.campos_site["Data de Acesso"].text()}
            return Site(**common_data, **specific_data)
        return None

# --- NOVA E MELHORADA CLASSE DE RECUPERAÇÃO ---

class DialogoRecuperacao(QDialog):
    def __init__(self, arquivos: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recuperação de Arquivos")
        self.setMinimumWidth(550)

        self.arquivos_para_recuperar = []
        self.arquivos_para_descartar = []
        self.acao = None # 'recuperar', 'descartar', ou None se fechar

        layout = QVBoxLayout(self)

        label = QLabel("O programa foi encerrado inesperadamente.\n"
                       "Marque os arquivos que deseja recuperar ou descartar.")
        layout.addWidget(label)

        self.lista_arquivos = QListWidget()
        
        for arq_info in arquivos:
            nome = arq_info.get('original_name', 'Desconhecido')
            try:
                data_str = datetime.fromisoformat(arq_info['recovery_save_time']).strftime('%d/%m/%Y %H:%M:%S')
            except (ValueError, TypeError):
                data_str = "Data desconhecida"

            item_texto = f"'{nome}' - Salvo em: {data_str}"
            item = QListWidgetItem(item_texto)
            
            # Adiciona a funcionalidade de checkbox
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(QtCore.Qt.CheckState.Unchecked)
            
            # Armazena todo o dicionário de informações para uso posterior
            item.setData(QtCore.Qt.ItemDataRole.UserRole, arq_info)
            self.lista_arquivos.addItem(item)
        
        layout.addWidget(self.lista_arquivos)

        # Botões personalizados para ações claras
        button_layout = QHBoxLayout()
        btn_recuperar = QPushButton("Recuperar Selecionados")
        btn_descartar = QPushButton("Descartar Selecionados")
        btn_depois = QPushButton("Decidir Depois")

        btn_recuperar.clicked.connect(self._recuperar_clicado)
        btn_descartar.clicked.connect(self._descartar_clicado)
        btn_depois.clicked.connect(self.reject) # Rejeitar significa "não fazer nada agora"

        button_layout.addWidget(btn_depois)
        button_layout.addStretch()
        button_layout.addWidget(btn_descartar)
        button_layout.addWidget(btn_recuperar)
        
        layout.addLayout(button_layout)

    def _processar_selecao(self):
        """Preenche as listas de resultados com base nos checkboxes marcados."""
        self.arquivos_para_recuperar.clear()
        self.arquivos_para_descartar.clear()
        
        for i in range(self.lista_arquivos.count()):
            item = self.lista_arquivos.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                arq_info = item.data(QtCore.Qt.ItemDataRole.UserRole)
                if self.acao == 'recuperar':
                    self.arquivos_para_recuperar.append(arq_info)
                elif self.acao == 'descartar':
                    self.arquivos_para_descartar.append(arq_info)

    def _recuperar_clicado(self):
        self.acao = 'recuperar'
        self._processar_selecao()
        if not self.arquivos_para_recuperar:
            QMessageBox.warning(self, "Nenhuma Seleção", "Por favor, marque pelo menos um arquivo para recuperar.")
            return
        self.accept()

    def _descartar_clicado(self):
        self.acao = 'descartar'
        self._processar_selecao()
        if not self.arquivos_para_descartar:
            QMessageBox.warning(self, "Nenhuma Seleção", "Por favor, marque pelo menos um arquivo para descartar.")
            return
        
        resposta = QMessageBox.question(self, "Confirmar Exclusão",
                                          "Tem certeza que deseja descartar permanentemente os arquivos de recuperação selecionados?\n"
                                          "Esta ação não pode ser desfeita.",
                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if resposta == QMessageBox.StandardButton.Yes:
            self.accept()