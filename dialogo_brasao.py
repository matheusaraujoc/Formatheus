# dialogo_brasao.py
# Descrição: Versão atualizada com ferramenta de corte (crop)
# interativa e propriedades QSS para o novo stylesheet.

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox, QMessageBox)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen
from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PIL import Image

# =============================================================================
# --- CLASSE: CropLabel ---
# Esta é a ferramenta de corte interativa.
# =============================================================================

class CropLabel(QLabel):
    """
    Um QLabel personalizado que permite ao usuário desenhar um retângulo
    de seleção (corte) sobre a imagem.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap: QPixmap | None = None
        self.scaled_pixmap: QPixmap | None = None
        self.selection_rect = QRect()
        self.is_selecting = False
        self.start_pos = QPoint()
        
        # Geometria da imagem real dentro do widget
        self.pixmap_rect_in_widget = QRect()
        self.scale_factor = 1.0

        self.setScaledContents(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(250, 250)
        self.setStyleSheet("border: 1px dashed gray; padding: 5px;")
        
    def setOriginalPixmap(self, pixmap: QPixmap):
        """Define o pixmap original e atualiza a visualização."""
        self.original_pixmap = pixmap
        self.selection_rect = QRect() # Reseta a seleção
        self._update_scaled_pixmap()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Atualiza o pixmap escalonado quando o widget muda de tamanho."""
        self._update_scaled_pixmap()
        super().resizeEvent(event)

    def _update_scaled_pixmap(self):
        """Redimensiona o pixmap original para caber no widget (mantendo aspect ratio)"""
        if not self.original_pixmap:
            self.setPixmap(QPixmap()) # Limpa a imagem
            return

        # Escala o pixmap
        self.scaled_pixmap = self.original_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.setPixmap(self.scaled_pixmap)

        # Calcula a geometria exata do pixmap escalonado dentro do QLabel
        pw = self.scaled_pixmap.width()
        ph = self.scaled_pixmap.height()
        lw = self.width()
        lh = self.height()

        x = (lw - pw) / 2
        y = (lh - ph) / 2
        
        self.pixmap_rect_in_widget = QRect(int(x), int(y), int(pw), int(ph))
        
        # Calcula o fator de escala (Original / Escalado)
        if pw > 0:
            self.scale_factor = self.original_pixmap.width() / pw
        else:
            self.scale_factor = 1.0

    def _clamp_pos_to_pixmap(self, pos: QPoint) -> QPoint:
        """Força o cursor a ficar dentro dos limites da imagem visível."""
        x = max(self.pixmap_rect_in_widget.left(), min(pos.x(), self.pixmap_rect_in_widget.right()))
        y = max(self.pixmap_rect_in_widget.top(), min(pos.y(), self.pixmap_rect_in_widget.bottom()))
        return QPoint(x, y)

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """Inicia a seleção do corte."""
        # Só começa a seleção se o clique for dentro da imagem
        if event.button() == Qt.MouseButton.LeftButton and \
           self.pixmap_rect_in_widget.contains(event.pos()):
            
            self.is_selecting = True
            # Força o ponto inicial a estar estritamente dentro da imagem
            self.start_pos = self._clamp_pos_to_pixmap(event.pos())
            self.selection_rect = QRect(self.start_pos, self.start_pos)
            self.update() # Força um repaint

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Atualiza o retângulo de seleção enquanto o mouse é arrastado."""
        if self.is_selecting:
            # Força o ponto final a estar estritamente dentro da imagem
            clamped_pos = self._clamp_pos_to_pixmap(event.pos())
            
            # Atualiza o retângulo de seleção
            self.selection_rect = QRect(self.start_pos, clamped_pos).normalized()
            
            self.update() # Força um repaint

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """Finaliza a seleção do corte."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            self.is_selecting = False
            self.update() # Força um repaint final

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Desenha o pixmap e, em seguida, o overlay de corte por cima."""
        # 1. Desenha o QLabel (que desenha o pixmap centrado)
        super().paintEvent(event)
        
        if not self.original_pixmap:
            return

        painter = QPainter(self)
        
        # 2. Desenha o overlay semi-transparente (a área escurecida)
        overlay_path = QtGui.QPainterPath()
        # Adiciona o retângulo da imagem inteira
        overlay_path.addRect(QRectF(self.pixmap_rect_in_widget))
        
        if self.has_selection():
             # "Esculpe" (corta) o retângulo de seleção do overlay
            overlay_path.addRect(QRectF(self.selection_rect))
            overlay_path.setFillRule(Qt.FillRule.OddEvenFill)
        
        painter.fillPath(overlay_path, QColor(0, 0, 0, 100)) # 100/255 de opacidade

        # 3. Desenha a borda do corte
        if self.has_selection():
            pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.selection_rect)
        
        painter.end()

    def has_selection(self) -> bool:
        """Verifica se o usuário fez uma seleção válida."""
        return self.selection_rect.isValid() and \
               self.selection_rect.width() > 5 and \
               self.selection_rect.height() > 5

    def get_crop_coords(self) -> tuple[int, int, int, int] | None:
        """
        Converte as coordenadas do widget (tela) para as coordenadas
        da imagem original (arquivo).
        Retorna (left, upper, right, lower) para o Pillow.
        """
        if not self.has_selection():
            return None
        
        # 1. Torna o retângulo de seleção relativo ao topo/esquerda da imagem (não do widget)
        relative_rect = self.selection_rect.translated(-self.pixmap_rect_in_widget.topLeft())
        
        # 2. Converte as coordenadas escaladas de volta para o original
        orig_x1 = int(relative_rect.left() * self.scale_factor)
        orig_y1 = int(relative_rect.top() * self.scale_factor)
        orig_x2 = int(relative_rect.right() * self.scale_factor)
        orig_y2 = int(relative_rect.bottom() * self.scale_factor)
        
        # 3. Garante que as coordenadas não saiam dos limites da imagem original
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        
        orig_x1 = max(0, orig_x1)
        orig_y1 = max(0, orig_y1)
        orig_x2 = min(orig_w, orig_x2)
        orig_y2 = min(orig_h, orig_y2)

        return (orig_x1, orig_y1, orig_x2, orig_y2)

# =============================================================================
# --- CLASSE DE DIÁLOGO MODIFICADA ---
# =============================================================================

class DialogoBrasao(QDialog):
    def __init__(self, caminho_original: str = None, tamanho_cm: float = 2.5, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Brasão (Recorte)")
        self.setMinimumSize(700, 500)

        self.caminho_original = caminho_original
        self.tamanho_cm = tamanho_cm
        self.caminho_processado = None
        self._usar_imagem_inteira = False # Flag para o processamento

        main_layout = QHBoxLayout(self)
        
        # Painel Esquerdo (Controles)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        form_layout = QtWidgets.QFormLayout()

        self.caminho_input = QLineEdit(self.caminho_original)
        self.caminho_input.setReadOnly(True)
        
        btn_procurar = QPushButton("Procurar...")
        # --- MUDANÇA (Define classe QSS) ---
        btn_procurar.setProperty("cssClass", "utility")
        # ------------------------------------
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
        form_layout.addRow("Tamanho no Documento:", self.tamanho_combo)
        left_layout.addLayout(form_layout)
        
        info_label = QLabel(
            "<b>Instruções:</b>\n"
            "1. Clique em 'Procurar' para carregar uma imagem.\n"
            "2. Clique e arraste sobre a imagem para \n"
            "   selecionar a área de corte.\n"
            "3. Clique OK para salvar."
        )
        info_label.setWordWrap(True)
        left_layout.addWidget(info_label)
        left_layout.addStretch()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept) # Conecta ao self.accept modificado
        self.buttons.rejected.connect(self.reject)
        
        # --- MUDANÇA (Define classe QSS para o botão Cancelar) ---
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setProperty("cssClass", "utility")
        # --------------------------------------------------------

        left_layout.addWidget(self.buttons)

        # Painel Direito (Pré-visualização com Corte)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # --- MUDANÇA: Usando o novo CropLabel ---
        self.preview_label = CropLabel()
        self.preview_label.setText("A prévia do brasão aparecerá aqui.\nArraste para cortar.")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        right_layout.addWidget(QLabel("<b>Pré-visualização (Arraste para cortar):</b>"))
        right_layout.addWidget(self.preview_label, 1) # O 1 faz ele expandir
        
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
            self.preview_label.setOriginalPixmap(QPixmap()) # Limpa
            return
            
        pixmap = QtGui.QPixmap(caminho_imagem)
        # --- MUDANÇA: Usa o novo método ---
        self.preview_label.setOriginalPixmap(pixmap)

    def accept(self):
        """
        Sobrescreve o 'accept' para verificar o corte antes de fechar.
        """
        if not self.caminho_original:
            QMessageBox.warning(self, "Arquivo Necessário", "Por favor, selecione um arquivo de imagem para o brasão.")
            return

        # Verifica se o usuário fez um corte
        if not self.preview_label.has_selection():
            resposta = QMessageBox.question(self, "Sem Corte",
                                            "Nenhuma área de corte foi selecionada.\n\n"
                                            "Deseja usar a imagem inteira?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resposta == QMessageBox.StandardButton.No:
                return # Não fecha o diálogo
            else:
                self._usar_imagem_inteira = True
        else:
            self._usar_imagem_inteira = False
            
        tamanho_str = self.tamanho_combo.currentText()
        if "Pequeno" in tamanho_str: self.tamanho_cm = 2.0
        elif "Médio" in tamanho_str: self.tamanho_cm = 2.5
        else: self.tamanho_cm = 3.0

        if not self._processar_imagem():
            return # Não fecha o diálogo se o processamento falhar

        super().accept()

    def _processar_imagem(self) -> bool:
        """
        Processa a imagem, aplicando o corte (se houver) antes
        de redimensionar e salvar.
        """
        try:
            pasta_destino = "_brasoes_processados"
            os.makedirs(pasta_destino, exist_ok=True)
            
            nome_arquivo = os.path.basename(self.caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            
            # Garante um nome de arquivo único
            caminho_saida = os.path.join(pasta_destino, f"{nome_base}.png")
            contador = 1
            while os.path.exists(caminho_saida):
                caminho_saida = os.path.join(pasta_destino, f"{nome_base}_{contador}.png")
                contador += 1

            with Image.open(self.caminho_original) as img:
                
                # --- MUDANÇA: Lógica de Corte ---
                crop_coords = self.preview_label.get_crop_coords()
                
                # Se o usuário fez uma seleção E não forçou usar a imagem inteira
                if crop_coords and not self._usar_imagem_inteira:
                    print(f"Aplicando corte: {crop_coords}")
                    img = img.crop(crop_coords)
                else:
                    print("Usando imagem inteira (sem corte).")
                # ---------------------------------
                
                # Converte para RGBA para garantir suporte a transparência
                img = img.convert("RGBA")
                
                # Redimensiona para um tamanho máximo em pixels para otimização
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