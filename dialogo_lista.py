# dialogo_lista.py
# Descrição: Janela de diálogo para a criação e edição de listas hierárquicas.
# CORREÇÃO: Corrigido o enum na linha 51 (de DragDropMode para SelectionMode).

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QTreeWidget,
                               QTreeWidgetItem, QDialogButtonBox, QMessageBox, QCheckBox,
                               QInputDialog)

from documento import ListaABNT, ItemLista, TipoEnumeracaoLista

class ListaDialog(QDialog):
    def __init__(self, lista_existente: ListaABNT = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Lista ABNT")
        self.setMinimumSize(700, 500)

        # Se estamos editando, usamos o objeto existente. Se for novo, criamos um.
        self.lista = lista_existente if lista_existente else ListaABNT(titulo="")
        if not self.lista.raiz.filhos and not lista_existente:
             # Garante que uma lista nova tenha pelo menos um item
             self.lista.raiz.adicionar_filho(ItemLista(texto="Item a)"))

        self.layout = QVBoxLayout(self)

        # --- Seção 1: Configurações da Lista ---
        config_layout = QtWidgets.QFormLayout()
        self.titulo_input = QLineEdit(self.lista.titulo)
        self.mostrar_titulo_check = QCheckBox("Mostrar título no documento")
        self.mostrar_titulo_check.setChecked(self.lista.mostrar_titulo)
        self.mostrar_titulo_check.setToolTip("Ex: 'Lista 1 - Título da Lista'")
        
        self.tipo_enumeracao_combo = QComboBox()
        # Tipos definidos na classe ListaABNT
        tipos: list[TipoEnumeracaoLista] = ["Híbrida (ABNT)", "Numérica (Seção)", "Alfabética", "Símbolos"]
        self.tipo_enumeracao_combo.addItems(tipos)
        self.tipo_enumeracao_combo.setCurrentText(self.lista.tipo_enumeracao)

        config_layout.addRow("Título da Lista (Identificador):", self.titulo_input)
        config_layout.addRow(self.mostrar_titulo_check)
        config_layout.addRow("Tipo de Enumeração:", self.tipo_enumeracao_combo)
        
        self.layout.addLayout(config_layout)

        # --- Seção 2: Estrutura da Lista (Árvore) ---
        self.layout.addWidget(QLabel("Estrutura Hierárquica da Lista:"))
        
        self.arvore_itens = QTreeWidget()
        self.arvore_itens.setHeaderLabel("Itens da Lista")
        self.arvore_itens.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        
        # --- INÍCIO DA CORREÇÃO (Linha 51) ---
        self.arvore_itens.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        # --- FIM DA CORREÇÃO ---
        
        self.arvore_itens.setDropIndicatorShown(True)
        self.popular_arvore_widget() # Carrega a lista no QTreeWidget
        self.arvore_itens.expandAll()
        
        # Conecta o duplo clique para edição
        self.arvore_itens.itemDoubleClicked.connect(self.editar_item)

        self.layout.addWidget(self.arvore_itens)

        # --- Seção 3: Botões de Edição da Árvore ---
        btn_tree_layout = QHBoxLayout()
        btn_add_item = QPushButton("Adicionar Item")
        btn_add_subitem = QPushButton("Adicionar Subitem")
        btn_edit_item = QPushButton("Editar Item")
        btn_del_item = QPushButton("Remover Item")

        btn_add_item.setProperty("cssClass", "utility")
        btn_add_subitem.setProperty("cssClass", "utility")
        btn_edit_item.setProperty("cssClass", "utility")
        btn_del_item.setProperty("cssClass", "destructive")

        btn_tree_layout.addWidget(btn_add_item)
        btn_tree_layout.addWidget(btn_add_subitem)
        btn_tree_layout.addWidget(btn_edit_item)
        btn_tree_layout.addWidget(btn_del_item)
        
        btn_add_item.clicked.connect(self.adicionar_item_raiz)
        btn_add_subitem.clicked.connect(self.adicionar_item_filho)
        btn_edit_item.clicked.connect(lambda: self.editar_item()) # Conexão lambda para slot sem args
        btn_del_item.clicked.connect(self.remover_item)

        self.layout.addLayout(btn_tree_layout)

        # --- Seção 4: Botões OK/Cancelar ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setProperty("cssClass", "utility")

        self.layout.addWidget(self.buttons)

    def popular_arvore_widget(self):
        """Carrega o modelo ItemLista no QTreeWidget."""
        self.arvore_itens.clear()
        
        def adicionar_filhos_recursivo(no_pai_modelo: ItemLista, no_pai_widget: QTreeWidget | QTreeWidgetItem):
            for filho_modelo in no_pai_modelo.filhos:
                item_widget = QTreeWidgetItem([filho_modelo.texto])
                # Armazena a referência ao objeto ItemLista real no item da árvore
                item_widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, filho_modelo)
                
                if isinstance(no_pai_widget, QTreeWidget):
                    no_pai_widget.addTopLevelItem(item_widget)
                else:
                    no_pai_widget.addChild(item_widget)
                
                adicionar_filhos_recursivo(filho_modelo, item_widget)

        # Começa a partir da raiz "invisível" do modelo
        adicionar_filhos_recursivo(self.lista.raiz, self.arvore_itens)

    def adicionar_item_raiz(self):
        """Adiciona um item no nível superior (raiz) da árvore."""
        novo_item_modelo = ItemLista(texto="Novo Item")
        item_widget = QTreeWidgetItem(["Novo Item"])
        item_widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, novo_item_modelo)
        self.arvore_itens.addTopLevelItem(item_widget)
        self.arvore_itens.setCurrentItem(item_widget)
        self.editar_item(item_widget) # Permite editar imediatamente

    def adicionar_item_filho(self):
        """Adiciona um subitem ao item atualmente selecionado."""
        item_pai_widget = self.arvore_itens.currentItem()
        if not item_pai_widget:
            QMessageBox.warning(self, "Atenção", "Selecione um item para adicionar um subitem.")
            return

        novo_item_modelo = ItemLista(texto="Novo Subitem")
        item_widget = QTreeWidgetItem(["Novo Subitem"])
        item_widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, novo_item_modelo)
        
        item_pai_widget.addChild(item_widget)
        item_pai_widget.setExpanded(True)
        self.arvore_itens.setCurrentItem(item_widget)
        self.editar_item(item_widget) # Permite editar imediatamente

    @QtCore.Slot(QTreeWidgetItem)
    def editar_item(self, item_widget: QTreeWidgetItem = None):
        """Edita o texto do item selecionado (ou do item passado por parâmetro)."""
        if not item_widget:
            item_widget = self.arvore_itens.currentItem()
            
        if not item_widget:
            # Não mostra aviso se for chamado por duplo clique em nada
            if self.sender() is not self.arvore_itens: 
                QMessageBox.warning(self, "Atenção", "Nenhum item selecionado para editar.")
            return
            
        item_modelo = item_widget.data(0, QtCore.Qt.ItemDataRole.UserRole)
        if not item_modelo: return # Segurança

        texto_atual = item_modelo.texto
        novo_texto, ok = QInputDialog.getText(self, "Editar Item", "Texto do item:", QLineEdit.Normal, texto_atual)
        
        if ok and novo_texto.strip():
            item_modelo.texto = novo_texto
            item_widget.setText(0, novo_texto)
        elif ok and not novo_texto.strip():
             QMessageBox.warning(self, "Texto Inválido", "O texto do item não pode ficar vazio.")

    def remover_item(self):
        """Remove o item atualmente selecionado e seus filhos."""
        item_widget = self.arvore_itens.currentItem()
        if not item_widget:
            QMessageBox.warning(self, "Atenção", "Nenhum item selecionado para remover.")
            return

        # Confirmação
        if item_widget.childCount() > 0:
            msg = f"Remover o item '{item_widget.text(0)}' e todos os seus subitens?"
        else:
            msg = f"Remover o item '{item_widget.text(0)}'?"
            
        resposta = QMessageBox.question(self, "Confirmar Remoção", msg,
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if resposta == QMessageBox.StandardButton.Yes:
            # Remove o item do QTreeWidget
            parent = item_widget.parent()
            if parent:
                parent.removeChild(item_widget)
            else:
                self.arvore_itens.invisibleRootItem().removeChild(item_widget)

    def _construir_modelo_da_arvore(self) -> ItemLista:
        """
        Converte a estrutura do QTreeWidget de volta para o modelo ItemLista.
        Este método é crucial e substitui o _sincronizar_modelo_com_arvore de 'aba_conteudo'.
        """
        nova_raiz_modelo = ItemLista(texto="Raiz da Lista")
        
        def percorrer_arvore_ui(parent_item_widget: QTreeWidgetItem | QTreeWidget, parent_node_modelo: ItemLista):
            # Define o número de filhos (se for a raiz da árvore ou um item)
            count = 0
            if isinstance(parent_item_widget, QTreeWidget):
                count = parent_item_widget.topLevelItemCount()
            else:
                count = parent_item_widget.childCount()

            for i in range(count):
                # Pega o filho
                child_item_widget = None
                if isinstance(parent_item_widget, QTreeWidget):
                    child_item_widget = parent_item_widget.topLevelItem(i)
                else:
                    child_item_widget = parent_item_widget.child(i)

                # Pega o objeto ItemLista armazenado no QTreeWidget
                child_node_modelo = child_item_widget.data(0, QtCore.Qt.ItemDataRole.UserRole)
                
                # Se for um item novo (criado agora), ele pode não ter o modelo ainda
                if not child_node_modelo:
                     child_node_modelo = ItemLista(texto=child_item_widget.text(0))
                
                # Atualiza o texto do modelo (caso tenha sido editado e não salvo)
                child_node_modelo.texto = child_item_widget.text(0)

                # Limpa os filhos antigos do modelo (pois a árvore é a nova fonte da verdade)
                child_node_modelo.filhos.clear() 
                
                # Adiciona o filho ao pai no modelo
                parent_node_modelo.adicionar_filho(child_node_modelo)
                
                # Continua a descida recursiva
                percorrer_arvore_ui(child_item_widget, child_node_modelo)

        # Inicia o processo a partir da raiz invisível do QTreeWidget
        percorrer_arvore_ui(self.arvore_itens, nova_raiz_modelo)
        
        return nova_raiz_modelo

    def accept(self):
        """Valida e salva os dados antes de fechar."""
        titulo = self.titulo_input.text().strip()
        if not titulo:
            QMessageBox.warning(self, "Título Obrigatório", 
                              "O título da lista não pode estar vazio. Ele é usado como identificador.")
            return

        # Salva os dados de volta no objeto self.lista
        self.lista.titulo = titulo
        self.lista.mostrar_titulo = self.mostrar_titulo_check.isChecked()
        self.lista.tipo_enumeracao = self.tipo_enumeracao_combo.currentText() # type: ignore
        
        # Reconstrói o modelo self.lista.raiz com base na árvore
        self.lista.raiz = self._construir_modelo_da_arvore()
        
        if not self.lista.raiz.filhos:
            QMessageBox.warning(self, "Lista Vazia", 
                              "A lista não pode estar vazia. Adicione pelo menos um item.")
            return

        super().accept()

    def get_dados_lista(self) -> ListaABNT:
        """Retorna o objeto ListaABNT configurado."""
        return self.lista