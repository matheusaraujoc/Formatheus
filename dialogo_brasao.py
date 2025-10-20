# dialogo_brasao.py
# Descrição: Nova janela de diálogo para adicionar e processar imagens de brasão.

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox, QMessageBox)
from PIL import Image

class DialogoBrasao(QDialog):
    def __init__(self, caminho_original: str = None, tamanho_cm: float = 2.5, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Brasão")
        self.setMinimumSize(700, 400)

        self.caminho_original = caminho_original
        self.tamanho_cm = tamanho_cm
        self.caminho_processado = None

        main_layout = QHBoxLayout(self)
        
        # Painel Esquerdo (Controles)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        form_layout = QtWidgets.QFormLayout()

        self.caminho_input = QLineEdit(self.caminho_original)
        self.caminho_input.setReadOnly(True)
        
        btn_procurar = QPushButton("Procurar...")
        btn_procurar.clicked.connect(self.procurar_arquivo)

        caminho_layout = QHBoxLayout()
        caminho_layout.addWidget(self.caminho_input)
        caminho_layout.addWidget(btn_procurar)
        
        self.tamanho_combo = QComboBox()
        self.tamanho_combo.addItems(["Pequeno (2.0 cm)", "Médio (2.5 cm)", "Grande (3.0 cm)"])
        if self.tamanho_cm == 2.0: self.tamanho_combo.setCurrentIndex(0)
        elif self.tamanho_cm == 2.5: self.tamanho_combo.setCurrentIndex(1)
        else: self.tamanho_combo.setCurrentIndex(2)

        form_layout.addRow("Arquivo do Brasão:", caminho_layout)
        form_layout.addRow("Tamanho do Brasão:", self.tamanho_combo)
        left_layout.addLayout(form_layout)
        left_layout.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        left_layout.addWidget(self.buttons)

        # Painel Direito (Pré-visualização)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.preview_label = QLabel("A prévia do brasão aparecerá aqui.")
        self.preview_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px dashed gray; padding: 5px;")
        self.preview_label.setMinimumSize(250, 250)
        right_layout.addWidget(QLabel("<b>Pré-visualização:</b>"))
        right_layout.addWidget(self.preview_label)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

        if self.caminho_original:
            self._atualizar_preview(self.caminho_original)

    def procurar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem do Brasão", "", 
            "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_original = caminho
            self.caminho_input.setText(caminho)
            self._atualizar_preview(caminho)

    def _atualizar_preview(self, caminho_imagem):
        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self.preview_label.setText("Imagem não encontrada.")
            self.preview_label.setPixmap(QtGui.QPixmap())
            return
        pixmap = QtGui.QPixmap(caminho_imagem)
        scaled_pixmap = pixmap.scaled(self.preview_label.size(),
                                      QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                      QtCore.Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)

    def accept(self):
        if not self.caminho_original:
            QMessageBox.warning(self, "Arquivo Necessário", "Por favor, selecione um arquivo de imagem para o brasão.")
            return
        
        tamanho_str = self.tamanho_combo.currentText()
        if "Pequeno" in tamanho_str: self.tamanho_cm = 2.0
        elif "Médio" in tamanho_str: self.tamanho_cm = 2.5
        else: self.tamanho_cm = 3.0

        if not self._processar_imagem():
            return # Não fecha o diálogo se o processamento falhar

        super().accept()

    def _processar_imagem(self) -> bool:
        try:
            pasta_destino = "_brasoes_processados"
            os.makedirs(pasta_destino, exist_ok=True)
            
            nome_arquivo = os.path.basename(self.caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            
            # Garante um nome de arquivo único para evitar sobreposições
            caminho_saida = os.path.join(pasta_destino, f"{nome_base}.png")
            contador = 1
            while os.path.exists(caminho_saida):
                caminho_saida = os.path.join(pasta_destino, f"{nome_base}_{contador}.png")
                contador += 1

            with Image.open(self.caminho_original) as img:
                # Converte para RGBA para garantir suporte a transparência
                img = img.convert("RGBA")
                
                # Redimensiona para um tamanho máximo em pixels para otimização
                # (3cm a ~96 DPI é ~113 pixels)
                tamanho_max_px = 150 
                img.thumbnail((tamanho_max_px, tamanho_max_px), Image.Resampling.LANCZOS)
                
                img.save(caminho_saida, "PNG")
                self.caminho_processado = caminho_saida
                return True
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Processar Imagem", f"Não foi possível processar a imagem do brasão:\n{e}")
            return False

    def get_dados_brasao(self) -> dict:
        """Retorna os dados do brasão para serem salvos."""
        if self.caminho_processado:
            return {
                "original": self.caminho_original,
                "processado": self.caminho_processado,
                "tamanho_cm": self.tamanho_cm
            }
        return None