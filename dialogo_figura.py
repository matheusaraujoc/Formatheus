# dialogo_figura.py
# Descrição: Janela de diálogo para adicionar e editar figuras.

import os
from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox)
from PIL import Image

from documento import Figura

LARGURA_MAXIMA_CM = 16.0 # Largura máxima para uma imagem em uma página A4 com margens

class DialogoFigura(QDialog):
    def __init__(self, figura: Figura = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Figura ABNT")
        self.setMinimumSize(500, 250)

        self.figura = figura if figura else Figura()

        self.layout = QVBoxLayout(self)
        form_layout = QtWidgets.QFormLayout()

        # Campos de Título, Fonte, Arquivo e Largura
        self.titulo_input = QLineEdit(self.figura.titulo)
        self.fonte_input = QLineEdit(self.figura.fonte)
        self.caminho_input = QLineEdit(self.figura.caminho_original)
        self.caminho_input.setReadOnly(True)
        self.largura_combo = QComboBox()
        self.largura_combo.addItems(["Pequena (8 cm)", "Média (12 cm)", "Grande (Largura Máxima)"])
        
        # Seleciona a largura correta no ComboBox
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
        self.layout.addLayout(form_layout)

        # Botões OK / Cancelar
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def procurar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem", "", 
            "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_input.setText(caminho)

    def get_dados_figura(self) -> Figura | None:
        self.figura.titulo = self.titulo_input.text()
        self.figura.fonte = self.fonte_input.text()
        self.figura.caminho_original = self.caminho_input.text()

        largura_str = self.largura_combo.currentText()
        if "Pequena" in largura_str: self.figura.largura_cm = 8.0
        elif "Média" in largura_str: self.figura.largura_cm = 12.0
        else: self.figura.largura_cm = LARGURA_MAXIMA_CM
        
        # Processamento da imagem (conversão e redimensionamento)
        if not self.figura.caminho_original:
            return self.figura

        try:
            # Garante que a pasta de imagens processadas exista
            pasta_imagens = "_imagens_processadas"
            os.makedirs(pasta_imagens, exist_ok=True)
            
            nome_arquivo = os.path.basename(self.figura.caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            # Salva sempre como PNG para máxima compatibilidade com python-docx
            caminho_saida = os.path.join(pasta_imagens, f"{nome_base}.png")

            with Image.open(self.figura.caminho_original) as img:
                # Converte para RGB para evitar problemas com paletas de cores (ex: GIF)
                img = img.convert("RGB")
                
                # Redimensiona se for maior que a largura máxima permitida
                # Converte CM para Pixels (aprox. 37.8 pixels por cm)
                largura_maxima_px = LARGURA_MAXIMA_CM * 37.8
                if img.width > largura_maxima_px:
                    ratio = largura_maxima_px / img.width
                    nova_altura = int(img.height * ratio)
                    img = img.resize((int(largura_maxima_px), nova_altura), Image.Resampling.LANCZOS)
                
                img.save(caminho_saida, "PNG")
                self.figura.caminho_processado = caminho_saida
                return self.figura
        except Exception as e:
            print(f"Erro ao processar imagem: {e}")
            # Retorna None em caso de erro para a UI poder tratar
            return None