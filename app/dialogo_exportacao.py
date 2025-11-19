# dialogo_exportacao.py
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QRadioButton, QCheckBox, QPushButton, QGroupBox, 
                               QButtonGroup, QStyle)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

class DialogoExportacao(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exportar Documento")
        self.setFixedWidth(400)
        self.setModal(True)
        
        self.layout = QVBoxLayout(self)

        # --- Grupo 1: Formato ---
        grp_formato = QGroupBox("Formato do Arquivo")
        layout_formato = QVBoxLayout()
        
        self.radio_docx = QRadioButton("Documento Word (.docx)")
        self.radio_docx.setChecked(True) # Padrão
        self.radio_docx.setToolTip("Arquivo editável, ideal para ajustes finais.")
        
        self.radio_pdf = QRadioButton("Documento PDF (.pdf)")
        self.radio_pdf.setToolTip("Arquivo final para leitura/impressão (Baseado na visualização atual).")

        layout_formato.addWidget(self.radio_docx)
        layout_formato.addWidget(self.radio_pdf)
        grp_formato.setLayout(layout_formato)
        self.layout.addWidget(grp_formato)

        # --- Grupo 2: O que incluir? ---
        grp_opcoes = QGroupBox("Opções de Conteúdo")
        layout_opcoes = QVBoxLayout()

        self.chk_pre_textual = QCheckBox("Incluir Elementos Pré-Textuais")
        self.chk_pre_textual.setChecked(True)
        self.chk_pre_textual.setToolTip("Capa, Folha de Rosto e Resumo")

        self.chk_sumario = QCheckBox("Incluir Sumário Automático")
        self.chk_sumario.setChecked(True)
        
        self.chk_referencias = QCheckBox("Incluir Referências Bibliográficas")
        self.chk_referencias.setChecked(True)

        layout_opcoes.addWidget(self.chk_pre_textual)
        layout_opcoes.addWidget(self.chk_sumario)
        layout_opcoes.addWidget(self.chk_referencias)
        grp_opcoes.setLayout(layout_opcoes)
        self.layout.addWidget(grp_opcoes)

        # --- Grupo 3: Pós-processamento ---
        grp_pos = QGroupBox("Após Exportar")
        layout_pos = QVBoxLayout()
        
        self.chk_abrir_arquivo = QCheckBox("Abrir arquivo automaticamente")
        self.chk_abrir_arquivo.setChecked(True)
        
        layout_pos.addWidget(self.chk_abrir_arquivo)
        grp_pos.setLayout(layout_pos)
        self.layout.addWidget(grp_pos)

        # --- Botões de Ação ---
        btn_layout = QHBoxLayout()
        
        self.btn_cancelar = QPushButton("Cancelar")
        self.btn_cancelar.clicked.connect(self.reject)
        
        self.btn_exportar = QPushButton("Exportar")
        self.btn_exportar.setProperty("cssClass", "primary") # Se usar seu tema
        self.btn_exportar.clicked.connect(self.accept)
        self.btn_exportar.setDefault(True)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancelar)
        btn_layout.addWidget(self.btn_exportar)
        
        self.layout.addLayout(btn_layout)

    def get_opcoes(self):
        """Retorna um dicionário com as escolhas do usuário."""
        return {
            "formato": "docx" if self.radio_docx.isChecked() else "pdf",
            "incluir_pre_textual": self.chk_pre_textual.isChecked(),
            "incluir_sumario": self.chk_sumario.isChecked(),
            "incluir_referencias": self.chk_referencias.isChecked(),
            "abrir_arquivo": self.chk_abrir_arquivo.isChecked()
        }