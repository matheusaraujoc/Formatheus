# dialogo_figura.py
# Descrição: Janela de diálogo para adicionar e editar figuras,
# COM FERRAMENTAS AVANÇADAS DE CORTE (Retângulo e Polígono).

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox, QMessageBox, QRadioButton,
                               QButtonGroup, QFrame)
from PySide6.QtGui import (QPixmap, QPainter, QColor, QPen, QPolygonF, QPainterPath)
from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PIL import Image, ImageDraw

from documento import Figura

LARGURA_MAXIMA_CM = 16.0 # Largura máxima para uma imagem em uma página A4 com margens
# Converte CM para Pixels (aprox. 37.8 pixels por cm, assumindo 96 DPI)
LARGURA_MAXIMA_PX = LARGURA_MAXIMA_CM * 37.8

# =============================================================================
# --- CLASSE: CropLabel ---
# Esta é a ferramenta de corte interativa.
# (Copiada do dialogo_brasao.py e agora vive aqui)
# =============================================================================

class CropLabel(QLabel):
    """
    Um QLabel personalizado que permite ao usuário desenhar uma seleção
    (retângulo ou polígono) sobre a imagem.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap: QPixmap | None = None
        self.scaled_pixmap: QPixmap | None = None
        
        # --- Geometria da imagem e escala ---
        self.pixmap_rect_in_widget = QRect()
        self.scale_factor = 1.0

        # --- Estados da Ferramenta ---
        self.mode = 'rect' # 'rect' ou 'poly'
        self.is_selecting = False # Apenas para o modo 'rect'
        
        # --- Estado: Modo Retângulo ---
        self.selection_rect = QRect()
        self.start_pos = QPoint()
        
        # --- Estado: Modo Polígono ---
        self.poly_points = [] # Lista de QPoint
        self.poly_closed = False
        self.preview_point = None # Para a linha "elástica"
        self.poly_click_tolerance = 10 # Distância para fechar o polígono

        self.setScaledContents(False)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(250, 250)
        self.setStyleSheet("border: 1px dashed gray; padding: 5px;")
        
        # Habilita o rastreamento do mouse para a linha elástica
        self.setMouseTracking(True) 

    def set_mode(self, mode: str):
        """Alterna o modo da ferramenta ('rect' ou 'poly')."""
        if mode not in ['rect', 'poly']:
            return
        self.mode = mode
        self.reset_selection()

    def reset_selection(self):
        """Limpa a seleção atual para ambos os modos."""
        self.selection_rect = QRect()
        self.poly_points = []
        self.poly_closed = False
        self.preview_point = None
        self.is_selecting = False
        self.update() # Força o repaint para limpar a tela

    def setOriginalPixmap(self, pixmap: QPixmap):
        """Define o pixmap original e atualiza a visualização."""
        self.original_pixmap = pixmap
        self.reset_selection() # Reseta a seleção
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

        self.scaled_pixmap = self.original_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.setPixmap(self.scaled_pixmap)

        pw = self.scaled_pixmap.width()
        ph = self.scaled_pixmap.height()
        lw = self.width()
        lh = self.height()
        x = (lw - pw) / 2
        y = (lh - ph) / 2
        
        self.pixmap_rect_in_widget = QRect(int(x), int(y), int(pw), int(ph))
        
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
        """Inicia a seleção (modo rect) ou adiciona um ponto (modo poly)."""
        if event.button() != Qt.MouseButton.LeftButton or \
           not self.pixmap_rect_in_widget.contains(event.pos()):
            return

        clamped_pos = self._clamp_pos_to_pixmap(event.pos())

        if self.mode == 'rect':
            self.is_selecting = True
            self.start_pos = clamped_pos
            self.selection_rect = QRect(self.start_pos, self.start_pos)
            self.update()
            
        elif self.mode == 'poly':
            if self.poly_closed:
                self.reset_selection()
            
            if len(self.poly_points) > 2:
                dist_ao_inicio = (clamped_pos - self.poly_points[0]).manhattanLength()
                if dist_ao_inicio < self.poly_click_tolerance:
                    self.poly_closed = True
                    self.preview_point = None 
                    self.update()
                    return 

            self.poly_points.append(clamped_pos)
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Atualiza a seleção (modo rect) ou a linha elástica (modo poly)."""
        clamped_pos = self._clamp_pos_to_pixmap(event.pos())
        
        if self.mode == 'rect':
            if self.is_selecting:
                self.selection_rect = QRect(self.start_pos, clamped_pos).normalized()
                self.update()
                
        elif self.mode == 'poly':
            if not self.poly_closed:
                self.preview_point = clamped_pos
                self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        """Finaliza a seleção (modo rect)."""
        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            if self.mode == 'rect':
                self.is_selecting = False
                self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):
        """Desenha o pixmap e o overlay de corte (retângulo ou polígono)."""
        super().paintEvent(event)
        
        if not self.original_pixmap:
            return

        painter = QPainter(self)
        overlay_path = QPainterPath()
        overlay_path.addRect(QRectF(self.pixmap_rect_in_widget))

        if self.has_selection():
            if self.mode == 'rect':
                overlay_path.addRect(QRectF(self.selection_rect))
            elif self.mode == 'poly':
                poly_qpolygon = QPolygonF(self.poly_points)
                overlay_path.addPolygon(poly_qpolygon)
            
            overlay_path.setFillRule(Qt.FillRule.OddEvenFill)
        
        painter.fillPath(overlay_path, QColor(0, 0, 0, 100))

        pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.mode == 'rect' and self.has_selection():
            painter.drawRect(self.selection_rect)
            
        elif self.mode == 'poly' and self.poly_points:
            poly_qpolygon = QPolygonF(self.poly_points)
            painter.drawPolyline(poly_qpolygon)
            
            if self.poly_closed:
                painter.drawLine(self.poly_points[-1], self.poly_points[0])
            elif self.preview_point:
                painter.drawLine(self.poly_points[-1], self.preview_point)

            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QColor("red"))
            for point in self.poly_points:
                painter.drawEllipse(point, 4, 4)
            
            if not self.poly_closed:
                painter.setBrush(QColor("lime"))
                painter.drawEllipse(self.poly_points[0], 5, 5)
        
        painter.end()

    def has_selection(self) -> bool:
        """Verifica se o usuário fez uma seleção válida."""
        if self.mode == 'rect':
            return self.selection_rect.isValid() and \
                   self.selection_rect.width() > 5 and \
                   self.selection_rect.height() > 5
        elif self.mode == 'poly':
            return self.poly_closed and len(self.poly_points) > 2
        return False

    def get_crop_coords(self) -> dict | None:
        """
        Converte as coordenadas do widget (tela) para as coordenadas
        da imagem original (arquivo).
        """
        if not self.has_selection():
            return None
        
        if self.mode == 'rect':
            relative_rect = self.selection_rect.translated(-self.pixmap_rect_in_widget.topLeft())
            
            orig_x1 = int(relative_rect.left() * self.scale_factor)
            orig_y1 = int(relative_rect.top() * self.scale_factor)
            orig_x2 = int(relative_rect.right() * self.scale_factor)
            orig_y2 = int(relative_rect.bottom() * self.scale_factor)
            
            orig_w = self.original_pixmap.width()
            orig_h = self.original_pixmap.height()
            
            orig_x1 = max(0, orig_x1)
            orig_y1 = max(0, orig_y1)
            orig_x2 = min(orig_w, orig_x2)
            orig_y2 = min(orig_h, orig_y2)

            return {"mode": "rect", "coords": (orig_x1, orig_y1, orig_x2, orig_y2)}

        elif self.mode == 'poly':
            orig_points = []
            orig_w = self.original_pixmap.width()
            orig_h = self.original_pixmap.height()

            for point in self.poly_points:
                relative_point = point - self.pixmap_rect_in_widget.topLeft()
                orig_x = int(relative_point.x() * self.scale_factor)
                orig_y = int(relative_point.y() * self.scale_factor)
                orig_x = max(0, min(orig_x, orig_w))
                orig_y = max(0, min(orig_y, orig_h))
                orig_points.append((orig_x, orig_y))
                
            return {"mode": "poly", "coords": orig_points}

        return None

# =============================================================================
# --- CLASSE DE DIÁLOGO MODIFICADA ---
# =============================================================================

class DialogoFigura(QDialog):
    def __init__(self, figura: Figura = None, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Figura ABNT (com Recorte)")
        self.setMinimumSize(700, 600)

        self.figura = figura if figura else Figura()

        main_layout = QHBoxLayout(self)
        
        # =======================================================
        # --- Painel Esquerdo (Controles) ---
        # =======================================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        form_layout = QtWidgets.QFormLayout()

        # --- Widgets de Título, Fonte, Arquivo e Largura ---
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
        btn_procurar.setProperty("cssClass", "utility")
        btn_procurar.clicked.connect(self.procurar_arquivo)
        
        caminho_layout = QHBoxLayout()
        caminho_layout.addWidget(self.caminho_input)
        caminho_layout.addWidget(btn_procurar)

        form_layout.addRow("Título (sem a palavra 'Figura X'):", self.titulo_input)
        form_layout.addRow("Fonte:", self.fonte_input)
        form_layout.addRow("Arquivo da Imagem:", caminho_layout)
        form_layout.addRow("Largura no Documento:", self.largura_combo)
        left_layout.addLayout(form_layout)

        # --- Seletor de Ferramenta (Copiado do Brasão) ---
        tool_frame = QFrame()
        tool_frame.setFrameShape(QFrame.Shape.StyledPanel)
        tool_layout = QVBoxLayout(tool_frame)
        tool_layout.addWidget(QLabel("<b>Ferramenta de Corte:</b>"))
        
        self.radio_rect = QRadioButton("Corte Retangular (Rápido)")
        self.radio_poly = QRadioButton("Corte Poligonal (Preciso)")
        self.radio_rect.setChecked(True)
        
        self.tool_button_group = QButtonGroup(self)
        self.tool_button_group.addButton(self.radio_rect)
        self.tool_button_group.addButton(self.radio_poly)
        
        self.btn_reset_selecao = QPushButton("Limpar Seleção")
        self.btn_reset_selecao.setProperty("cssClass", "utility")
        self.btn_reset_selecao.setVisible(False) 
        
        tool_layout.addWidget(self.radio_rect)
        tool_layout.addWidget(self.radio_poly)
        tool_layout.addWidget(self.btn_reset_selecao)
        
        left_layout.addWidget(tool_frame)
        
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        left_layout.addWidget(self.info_label)
        
        left_layout.addStretch()

        # --- Botões OK/Cancelar ---
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_button:
            cancel_button.setProperty("cssClass", "utility")
            
        left_layout.addWidget(self.buttons)

        # =======================================================
        # --- Painel Direito (Preview) ---
        # =======================================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.preview_label = CropLabel() 
        self.preview_label.setText("A prévia da figura aparecerá aqui.")
        
        right_layout.addWidget(QLabel("<b>Pré-visualização (Arraste para cortar):</b>"))
        right_layout.addWidget(self.preview_label, 1)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

        # --- Conexões de Sinais ---
        self.buttons.accepted.connect(self.accept) # Modificado
        self.buttons.rejected.connect(self.reject)
        self.tool_button_group.buttonClicked.connect(self._mudar_modo_corte)
        self.btn_reset_selecao.clicked.connect(self.preview_label.reset_selection)

        # --- Estado Inicial ---
        self._mudar_modo_corte() 
        caminho_inicial = self.figura.caminho_original or self.figura.caminho_processado
        if caminho_inicial:
            self._atualizar_preview(caminho_inicial)

    @QtCore.Slot()
    def _mudar_modo_corte(self):
        """Atualiza o modo do CropLabel e o texto de instruções."""
        if self.radio_rect.isChecked():
            self.preview_label.set_mode('rect')
            self.info_label.setText(
                "<b>Modo Retangular:</b>\n"
                "1. Clique e arraste sobre a imagem para "
                "selecionar a área de corte."
            )
            self.btn_reset_selecao.setVisible(False)
        else:
            self.preview_label.set_mode('poly')
            self.info_label.setText(
                "<b>Modo Poligonal:</b>\n"
                "1. Clique para adicionar pontos de seleção.\n"
                "2. Clique próximo ao <b>primeiro ponto</b> (verde) "
                "para fechar a seleção.\n"
                "3. Use 'Limpar Seleção' para recomeçar."
            )
            self.btn_reset_selecao.setVisible(True)

    def procurar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem", "", 
            "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_input.setText(caminho)
            self._atualizar_preview(caminho) # Adicionado

    def _atualizar_preview(self, caminho_imagem):
        """Carrega a imagem no CropLabel."""
        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self.preview_label.setText("Imagem não encontrada.")
            self.preview_label.setOriginalPixmap(QPixmap())
            return
            
        pixmap = QtGui.QPixmap(caminho_imagem)
        self.preview_label.setOriginalPixmap(pixmap)
        
    def resizeEvent(self, event):
        """Garante que o preview seja redimensionado corretamente."""
        super().resizeEvent(event)
        # O CropLabel agora lida com seu próprio resize event,
        # então não precisamos mais chamar o _atualizar_preview aqui.

    def accept(self):
        """
        Sobrescreve o 'accept' para validar e processar a imagem 
        antes de fechar.
        """
        if not self.titulo_input.text():
            QMessageBox.warning(self, "Campo Obrigatório", "O campo 'Título' não pode estar vazio.")
            return
        
        if not self.caminho_input.text():
            QMessageBox.warning(self, "Campo Obrigatório", "Por favor, selecione um 'Arquivo da Imagem'.")
            return
            
        # Atualiza o objeto self.figura com os dados do formulário
        self.figura.titulo = self.titulo_input.text()
        self.figura.fonte = self.fonte_input.text()
        self.figura.caminho_original = self.caminho_input.text()

        largura_str = self.largura_combo.currentText()
        if "Pequena" in largura_str: self.figura.largura_cm = 8.0
        elif "Média" in largura_str: self.figura.largura_cm = 12.0
        else: self.figura.largura_cm = LARGURA_MAXIMA_CM

        # Chama o processamento da imagem
        if not self._processar_imagem():
            return # Não fecha o diálogo se o processamento falhar

        super().accept()

    def _processar_imagem(self) -> bool:
        """
        Aplica o corte (se houver) e depois redimensiona e salva a imagem.
        """
        caminho_original = self.caminho_input.text()
        dados_corte = self.preview_label.get_crop_coords()

        # Otimização: Se a imagem não mudou E não há corte, não reprocessa
        if (self.figura.caminho_original == caminho_original and
            self.figura.caminho_processado and
            os.path.exists(self.figura.caminho_processado) and
            not dados_corte):
            print("Nenhuma mudança na imagem, mantendo processado anterior.")
            return True # Já está processado
        
        try:
            pasta_imagens = "_imagens_processadas"
            os.makedirs(pasta_imagens, exist_ok=True)
            
            nome_arquivo = os.path.basename(caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            # Salva sempre como PNG
            caminho_saida = os.path.join(pasta_imagens, f"{nome_base}.png")
            
            # Garante nome único
            contador = 1
            while os.path.exists(caminho_saida):
                caminho_saida = os.path.join(pasta_imagens, f"{nome_base}_{contador}.png")
                contador += 1

            with Image.open(caminho_original) as img:
                
                # Garante que a imagem suporte transparência
                img = img.convert("RGBA") 
                
                img_processada = img # Começa com a imagem original

                # 1. APLICAR O CORTE (se o usuário selecionou algo)
                if dados_corte:
                    if dados_corte['mode'] == 'rect':
                        print(f"Aplicando corte retangular: {dados_corte['coords']}")
                        img_processada = img.crop(dados_corte['coords'])
                    
                    elif dados_corte['mode'] == 'poly':
                        print(f"Aplicando corte poligonal.")
                        mask = Image.new("L", img.size, 0)
                        draw = ImageDraw.Draw(mask)
                        draw.polygon(dados_corte['coords'], fill=255)
                        
                        img_cortada = Image.new("RGBA", img.size)
                        img_cortada.paste(img, (0, 0), mask=mask)
                        
                        bbox = mask.getbbox() # Pega o bounding box da área cortada
                        if bbox:
                            img_processada = img_cortada.crop(bbox)
                        else:
                            img_processada = img_cortada # Fallback
                
                else:
                    print("Usando imagem inteira (sem corte).")

                # 2. APLICAR REDIMENSIONAMENTO (lógica antiga do DialogoFigura)
                img_final = img_processada # Inicia com a imagem (potencialmente cortada)
                
                if img_processada.width > LARGURA_MAXIMA_PX:
                    print("Redimensionando imagem (maior que o máximo permitido).")
                    ratio = LARGURA_MAXIMA_PX / img_processada.width
                    nova_altura = int(img_processada.height * ratio)
                    img_final = img_processada.resize((int(LARGURA_MAXIMA_PX), nova_altura), Image.Resampling.LANCZOS)
                
                # 3. SALVAR
                # Converte para RGB antes de salvar como PNG (remove canal Alfa se não for usado)
                # ou mantém RGBA se o corte poligonal foi usado.
                if dados_corte and dados_corte['mode'] == 'poly':
                    img_final.save(caminho_saida, "PNG") # Salva com transparência
                else:
                    img_final.convert("RGB").save(caminho_saida, "PNG") # Salva sem transparência
                
                self.figura.caminho_processado = caminho_saida
                return True
                
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Processar Imagem", f"Não foi possível processar a imagem:\n{e}")
            return False

    def get_dados_figura(self) -> Figura | None:
        """
        Retorna o objeto Figura, que foi preenchido e processado 
        durante o accept().
        """
        return self.figura