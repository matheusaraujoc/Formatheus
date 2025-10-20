# aba_conteudo.py
# Descrição: Versão completa com QTabWidget e proporções de layout ajustadas.

import re
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QWidget, QLabel, QTextEdit, QPushButton, QListWidget, QCheckBox,
                               QVBoxLayout, QHBoxLayout, QMessageBox, QTreeWidget,
                               QTreeWidgetItem, QInputDialog, QAbstractItemView, QLineEdit, QTabWidget)

from documento import Capitulo, Tabela, Figura, Formula
from dialogs import TabelaDialog, DialogoFigura
from DialogoFormula import DialogoFormula

class ArvoreConteudo(QTreeWidget):
    estruturaAlterada = QtCore.Signal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragDropMode(QAbstractItemView.DragDropMode.NoDragDrop)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDropIndicatorShown(True)
        
    def dropEvent(self, event: QtGui.QDropEvent):
        if self.dragDropMode() == QAbstractItemView.DragDropMode.InternalMove:
            super().dropEvent(event)
            self.estruturaAlterada.emit()
        else:
            event.ignore()

class AbaConteudo(QWidget):
    def __init__(self, documento, parent=None):
        super().__init__(parent)
        self.documento = documento
        self._carregando_capitulo = False
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(350)

        left_layout.addWidget(QLabel("Estrutura do Documento"))
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
        btn_layout.addWidget(btn_add_topico)
        btn_layout.addWidget(btn_add_sub)
        btn_layout.addWidget(btn_del)
        btn_add_topico.clicked.connect(self._adicionar_topico_principal)
        btn_add_sub.clicked.connect(self._adicionar_subtopico)
        btn_del.clicked.connect(self._remover_topico)
        left_layout.addLayout(btn_layout)
        layout.addWidget(left_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.label_capitulo_atual = QLabel("Selecione um tópico para editar")
        self.editor_capitulo = QTextEdit()
        self.editor_capitulo.textChanged.connect(self._on_editor_text_changed)
        
        self.lista_tabelas = QListWidget()
        self.lista_figuras = QListWidget()
        self.lista_formulas = QListWidget()

        # Cria o QTabWidget que vai conter os bancos
        self.bancos_tabs = QTabWidget()

        # Cria o widget para a aba "Tabelas"
        tabelas_widget = QWidget()
        tabelas_v_layout = QVBoxLayout(tabelas_widget)
        tabelas_v_layout.addWidget(QLabel("Banco de Tabelas do Projeto:"))
        self.filtro_tabelas_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_tabelas_check.stateChanged.connect(self.atualizar_bancos_visuais)
        tabelas_v_layout.addWidget(self.filtro_tabelas_check)
        tabelas_v_layout.addWidget(self.lista_tabelas)
        tabelas_btn_layout = QHBoxLayout()
        btn_add_tabela = QPushButton("Criar")
        btn_edit_tabela = QPushButton("Editar")
        btn_del_tabela = QPushButton("Remover")
        tabelas_btn_layout.addWidget(btn_add_tabela)
        tabelas_btn_layout.addWidget(btn_edit_tabela)
        tabelas_btn_layout.addWidget(btn_del_tabela)
        tabelas_v_layout.addLayout(tabelas_btn_layout)
        btn_ins_tabela = QPushButton("Inserir no Texto")
        tabelas_v_layout.addWidget(btn_ins_tabela)
        
        btn_add_tabela.clicked.connect(self._adicionar_tabela)
        btn_edit_tabela.clicked.connect(self._editar_tabela)
        btn_del_tabela.clicked.connect(self._remover_tabela)
        btn_ins_tabela.clicked.connect(self._inserir_marcador_tabela)
        
        # Cria o widget para a aba "Figuras"
        figuras_widget = QWidget()
        figuras_v_layout = QVBoxLayout(figuras_widget)
        figuras_v_layout.addWidget(QLabel("Banco de Figuras do Projeto:"))
        self.filtro_figuras_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_figuras_check.stateChanged.connect(self.atualizar_bancos_visuais)
        figuras_v_layout.addWidget(self.filtro_figuras_check)
        figuras_v_layout.addWidget(self.lista_figuras)
        figuras_btn_layout = QHBoxLayout()
        btn_add_figura = QPushButton("Criar")
        btn_edit_figura = QPushButton("Editar")
        btn_del_figura = QPushButton("Remover")
        figuras_btn_layout.addWidget(btn_add_figura)
        figuras_btn_layout.addWidget(btn_edit_figura)
        figuras_btn_layout.addWidget(btn_del_figura)
        figuras_v_layout.addLayout(figuras_btn_layout)
        btn_ins_figura = QPushButton("Inserir no Texto")
        figuras_v_layout.addWidget(btn_ins_figura)
        
        btn_add_figura.clicked.connect(self._adicionar_figura)
        btn_edit_figura.clicked.connect(self._editar_figura)
        btn_del_figura.clicked.connect(self._remover_figura)
        btn_ins_figura.clicked.connect(self._inserir_marcador_figura)

        # Cria o widget para a aba "Fórmulas"
        formulas_widget = QWidget()
        formulas_v_layout = QVBoxLayout(formulas_widget)
        formulas_v_layout.addWidget(QLabel("Banco de Fórmulas do Projeto:"))
        self.filtro_formulas_check = QCheckBox("Mostrar apenas do tópico atual")
        self.filtro_formulas_check.stateChanged.connect(self.atualizar_bancos_visuais)
        formulas_v_layout.addWidget(self.filtro_formulas_check)
        formulas_v_layout.addWidget(self.lista_formulas)
        formulas_btn_layout = QHBoxLayout()
        btn_add_formula = QPushButton("Criar")
        btn_edit_formula = QPushButton("Editar")
        btn_del_formula = QPushButton("Remover")
        formulas_btn_layout.addWidget(btn_add_formula)
        formulas_btn_layout.addWidget(btn_edit_formula)
        formulas_btn_layout.addWidget(btn_del_formula)
        formulas_v_layout.addLayout(formulas_btn_layout)
        btn_ins_formula = QPushButton("Inserir no Texto")
        formulas_v_layout.addWidget(btn_ins_formula)
        
        btn_add_formula.clicked.connect(self._adicionar_formula)
        btn_edit_formula.clicked.connect(self._editar_formula)
        btn_del_formula.clicked.connect(self._remover_formula)
        btn_ins_formula.clicked.connect(self._inserir_marcador_formula)
        
        # Adiciona os widgets criados como abas no QTabWidget
        self.bancos_tabs.addTab(tabelas_widget, "Tabelas")
        self.bancos_tabs.addTab(figuras_widget, "Figuras")
        self.bancos_tabs.addTab(formulas_widget, "Fórmulas")

        # Adiciona os widgets ao layout principal com as novas proporções
        right_layout.addWidget(self.label_capitulo_atual)
        right_layout.addWidget(self.editor_capitulo, 3) # Editor de texto com mais espaço (fator 3)
        right_layout.addWidget(self.bancos_tabs, 2)     # Abas com espaço equilibrado (fator 2)
        layout.addWidget(right_panel)
        
        self._popular_arvore()
        if self.arvore_capitulos.topLevelItemCount() > 0:
            self.arvore_capitulos.setCurrentItem(self.arvore_capitulos.topLevelItem(0))

    @QtCore.Slot()
    def atualizar_bancos_visuais(self):
        capitulo_selecionado = self._get_capitulo_selecionado()
        conteudo_capitulo = capitulo_selecionado.conteudo if capitulo_selecionado else ""
        
        self.lista_tabelas.clear()
        if self.filtro_tabelas_check.isChecked() and capitulo_selecionado:
            titulos_usados = set(re.findall(r"\{\{Tabela:([^}]+)\}\}", conteudo_capitulo))
            for tabela in self.documento.banco_tabelas:
                if tabela.titulo in titulos_usados: self.lista_tabelas.addItem(tabela.titulo)
        else:
            for tabela in self.documento.banco_tabelas: self.lista_tabelas.addItem(tabela.titulo)

        self.lista_figuras.clear()
        if self.filtro_figuras_check.isChecked() and capitulo_selecionado:
            titulos_usados = set(re.findall(r"\{\{Figura:([^}]+)\}\}", conteudo_capitulo))
            for figura in self.documento.banco_figuras:
                if figura.titulo in titulos_usados: self.lista_figuras.addItem(figura.titulo)
        else:
            for figura in self.documento.banco_figuras: self.lista_figuras.addItem(figura.titulo)
            
        self.lista_formulas.clear()
        if self.filtro_formulas_check.isChecked() and capitulo_selecionado:
            legendas_usadas = set(re.findall(r"\{\{Formula:([^}]+)\}\}", conteudo_capitulo))
            for formula in self.documento.banco_formulas:
                if formula.legenda in legendas_usadas:
                    self.lista_formulas.addItem(formula.legenda)
        else:
            for formula in self.documento.banco_formulas:
                self.lista_formulas.addItem(formula.legenda)
    
    @QtCore.Slot()
    def _on_editor_text_changed(self):
        self._salvar_conteudo_capitulo()
        self.atualizar_bancos_visuais()

    @QtCore.Slot(QTreeWidgetItem, QTreeWidgetItem)
    def _on_capitulo_selecionado_changed(self, item_atual, item_anterior):
        self._carregar_capitulo_no_editor(item_atual, item_anterior)
        self.atualizar_bancos_visuais()

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

    @QtCore.Slot()
    def _adicionar_tabela(self):
        dialog = TabelaDialog(parent=self)
        if dialog.exec():
            self.documento.banco_tabelas.append(dialog.get_dados_tabela())
            self.atualizar_bancos_visuais()

    @QtCore.Slot()
    def _adicionar_figura(self):
        dialog = DialogoFigura(parent=self)
        if dialog.exec():
            nova_figura = dialog.get_dados_figura()
            if nova_figura and nova_figura.caminho_processado:
                self.documento.banco_figuras.append(nova_figura)
                self.atualizar_bancos_visuais()

    @QtCore.Slot()
    def _adicionar_formula(self):
        dialog = DialogoFormula(parent=self)
        if dialog.exec():
            nova_formula = dialog.get_dados_formula()
            self.documento.banco_formulas.append(nova_formula)
            self.atualizar_bancos_visuais()

    @QtCore.Slot()
    def _inserir_marcador_tabela(self):
        item_selecionado = self.lista_tabelas.currentItem()
        if not item_selecionado:
            QMessageBox.warning(self, "Atenção", "Selecione uma tabela do banco para inserir.")
            return
        marcador = f"\n{{{{Tabela:{item_selecionado.text()}}}}}\n"
        self.editor_capitulo.insertPlainText(marcador)

    @QtCore.Slot()
    def _inserir_marcador_figura(self):
        item_selecionado = self.lista_figuras.currentItem()
        if not item_selecionado:
            QMessageBox.warning(self, "Atenção", "Selecione uma figura do banco para inserir.")
            return
        marcador = f"\n{{{{Figura:{item_selecionado.text()}}}}}\n"
        self.editor_capitulo.insertPlainText(marcador)

    @QtCore.Slot()
    def _inserir_marcador_formula(self):
        item_selecionado = self.lista_formulas.currentItem()
        if not item_selecionado:
            QMessageBox.warning(self, "Atenção", "Selecione uma fórmula do banco para inserir.")
            return
        marcador = f"\n{{{{Formula:{item_selecionado.text()}}}}}\n"
        self.editor_capitulo.insertPlainText(marcador)

    def _get_capitulo_selecionado(self) -> Capitulo | None:
        item = self.arvore_capitulos.currentItem()
        return item.data(0, QtCore.Qt.ItemDataRole.UserRole) if item else None

    @QtCore.Slot()
    def _salvar_conteudo_capitulo(self):
        if self._carregando_capitulo: return
        capitulo = self._get_capitulo_selecionado()
        if capitulo:
            capitulo.conteudo = self.editor_capitulo.toPlainText()

    @QtCore.Slot()
    def _editar_tabela(self):
        linha = self.lista_tabelas.currentRow()
        if linha == -1: return
        titulo_tabela = self.lista_tabelas.item(linha).text()
        tabela_original = next((t for t in self.documento.banco_tabelas if t.titulo == titulo_tabela), None)
        if not tabela_original: return
        
        dialog = TabelaDialog(tabela=tabela_original, parent=self)
        if dialog.exec():
            tabela_original.__dict__.update(dialog.get_dados_tabela().__dict__)
            self.atualizar_bancos_visuais()


    @QtCore.Slot()
    def _remover_tabela(self):
        linha = self.lista_tabelas.currentRow()
        if linha == -1: return
        titulo_tabela = self.lista_tabelas.item(linha).text()
        if QMessageBox.question(self, "Confirmar", f"Remover a tabela '{titulo_tabela}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_tabelas = [t for t in self.documento.banco_tabelas if t.titulo != titulo_tabela]
            self.atualizar_bancos_visuais()
            
    @QtCore.Slot()
    def _editar_figura(self):
        linha = self.lista_figuras.currentRow()
        if linha == -1: return
        titulo_figura = self.lista_figuras.item(linha).text()
        figura_original = next((f for f in self.documento.banco_figuras if f.titulo == titulo_figura), None)
        if not figura_original: return
        
        dialog = DialogoFigura(figura=figura_original, parent=self)
        if dialog.exec():
            figura_original.__dict__.update(dialog.get_dados_figura().__dict__)
            self.atualizar_bancos_visuais()
    
    @QtCore.Slot()
    def _remover_figura(self):
        linha = self.lista_figuras.currentRow()
        if linha == -1: return
        titulo_figura = self.lista_figuras.item(linha).text()
        if QMessageBox.question(self, "Confirmar", f"Remover a figura '{titulo_figura}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_figuras = [f for f in self.documento.banco_figuras if f.titulo != titulo_figura]
            self.atualizar_bancos_visuais()
            
    @QtCore.Slot()
    def _editar_formula(self):
        linha = self.lista_formulas.currentRow()
        if linha == -1: return
        legenda_formula = self.lista_formulas.item(linha).text()
        formula_original = next((f for f in self.documento.banco_formulas if f.legenda == legenda_formula), None)
        if not formula_original: return
        
        dialog = DialogoFormula(formula=formula_original, parent=self)
        if dialog.exec():
            formula_original.__dict__.update(dialog.get_dados_formula().__dict__)
            self.atualizar_bancos_visuais()
    
    @QtCore.Slot()
    def _remover_formula(self):
        linha = self.lista_formulas.currentRow()
        if linha == -1: return
        legenda_formula = self.lista_formulas.item(linha).text()
        if QMessageBox.question(self, "Confirmar", f"Remover a fórmula '{legenda_formula}' do projeto?") == QMessageBox.StandardButton.Yes:
            self.documento.banco_formulas = [f for f in self.documento.banco_formulas if f.legenda != legenda_formula]
            self.atualizar_bancos_visuais()
    
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