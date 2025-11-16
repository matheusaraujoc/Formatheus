# dialogo_figura.py
# Descrição: Janela de diálogo para adicionar e editar figuras.
# MODIFICAÇÃO: Corrigida a lógica de "pan" (mover) para
# renderizar (desenhar) a imagem na posição correta.
# ATUALIZAÇÃO: Adicionada verificação de título duplicado
# no método accept() para evitar bugs de referência.

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox, QMessageBox, QRadioButton,
                               QButtonGroup, QFrame)
from PySide6.QtGui import (QPixmap, QPainter, QColor, QPen, QPolygonF, QPainterPath,
                           QKeyEvent)
from PySide6.QtCore import Qt, QRect, QPoint, QRectF, QSize
from PIL import Image, ImageDraw

from documento import Figura

LARGURA_MAXIMA_CM = 16.0 
LARGURA_MAXIMA_PX = LARGURA_MAXIMA_CM * 37.8

# =============================================================================
# --- CLASSE: CropLabel ---
# =============================================================================

class CropLabel(QLabel):
    """
    QLabel personalizado com zoom (scroll), pan (botão direito),
    e corte (botão esquerdo).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_pixmap: QPixmap | None = None
        self.scaled_pixmap: QPixmap | None = None
        
        self.pixmap_rect_in_widget = QRect()
        self.scale_factor = 1.0

        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0) 
        self.is_panning = False
        self.last_pan_pos = QPoint()

        self.mode = 'rect' 
        self.is_selecting = False 
        
        # --- INÍCIO DA CORREÇÃO (Coordenadas Originais) ---
        # A seleção agora é armazenada em relação à imagem original (0,0)
        self.selection_rect_orig = QRect()
        self.start_pos_orig = QPoint()
        self.poly_points_orig = [] 
        self.preview_point_orig = None
        # --- FIM DA CORREÇÃO ---
        
        self.poly_closed = False
        self.poly_click_tolerance = 10 

        self.setScaledContents(False)
        self.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft) 
        self.setMinimumSize(250, 250)
        self.setStyleSheet("border: 1px dashed gray; padding: 5px;")
        
        self.setMouseTracking(True) 
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def set_mode(self, mode: str):
        if mode not in ['rect', 'poly']:
            return
        self.mode = mode
        self.reset_selection()

    def reset_selection(self):
        self.selection_rect_orig = QRect()
        self.poly_points_orig = []
        self.poly_closed = False
        self.preview_point_orig = None
        self.is_selecting = False
        self.update() 

    def setOriginalPixmap(self, pixmap: QPixmap):
        self.original_pixmap = pixmap
        self.zoom_factor = 1.0
        self.pan_offset = QPoint(0, 0)
        self.reset_selection()
        self._update_scaled_pixmap()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        self._update_scaled_pixmap()
        super().resizeEvent(event)

    def _update_scaled_pixmap(self):
        """Redimensiona e calcula a posição do pixmap com base no zoom e pan."""
        
        self.setPixmap(QPixmap()) 
        
        if not self.original_pixmap:
            self.scaled_pixmap = None
            self.update()
            return

        fit_size = self.original_pixmap.size().scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatio
        )
        
        zoomed_size = QSize(
            int(fit_size.width() * self.zoom_factor),
            int(fit_size.height() * self.zoom_factor)
        )
        
        if self.scaled_pixmap is None or self.scaled_pixmap.size() != zoomed_size:
            self.scaled_pixmap = self.original_pixmap.scaled(
                zoomed_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
        
        pw = self.scaled_pixmap.width()
        ph = self.scaled_pixmap.height()
        lw = self.width() 
        lh = self.height() 
        
        x_base = (lw - pw) / 2
        y_base = (lh - ph) / 2
        
        if pw > lw:
            max_pan_x = (pw - lw) / 2
            clamped_pan_x = max(-max_pan_x, min(self.pan_offset.x(), max_pan_x))
            self.pan_offset.setX(int(clamped_pan_x))
        else:
            self.pan_offset.setX(0)
            
        if ph > lh:
            max_pan_y = (ph - lh) / 2
            clamped_pan_y = max(-max_pan_y, min(self.pan_offset.y(), max_pan_y))
            self.pan_offset.setY(int(clamped_pan_y))
        else:
            self.pan_offset.setY(0)

        x = x_base + self.pan_offset.x()
        y = y_base + self.pan_offset.y()
        
        self.pixmap_rect_in_widget = QRect(int(x), int(y), int(pw), int(ph))
        
        if pw > 0:
            self.scale_factor = self.original_pixmap.width() / pw
        else:
            self.scale_factor = 1.0
        
        self.update() 

    # --- INÍCIO DA CORREÇÃO (ZOOM) ---
    def wheelEvent(self, event: QtGui.QWheelEvent):
        if not self.original_pixmap:
            event.ignore()
            return

        if event.angleDelta().y() > 0:
            self.zoom_factor *= 1.20
        else:
            self.zoom_factor /= 1.20
        
        self.zoom_factor = max(1.0, self.zoom_factor) 
        
        self._update_scaled_pixmap()
        
        # self.reset_selection() # <--- REMOVIDO! A seleção não some mais.
        
        event.accept()
    # --- FIM DA CORREÇÃO ---

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        if event.key() == Qt.Key.Key_Z and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self._undo_last_poly_point()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _undo_last_poly_point(self):
        if self.mode == 'poly' and self.poly_points_orig:
            self.poly_points_orig.pop()
            self.poly_closed = False
            self.update()
            print("Ponto do polígono desfeito.")

    def _clamp_pos_to_pixmap(self, pos: QPoint) -> QPoint:
        x = max(self.pixmap_rect_in_widget.left(), min(pos.x(), self.pixmap_rect_in_widget.right()))
        y = max(self.pixmap_rect_in_widget.top(), min(pos.y(), self.pixmap_rect_in_widget.bottom()))
        return QPoint(x, y)

    # --- INÍCIO DA CORREÇÃO (Coordenadas) ---
    def _widget_to_orig_coords(self, widget_pos: QPoint) -> QPoint:
        """Converte coordenadas do widget para as coordenadas da imagem original."""
        if not self.original_pixmap or self.scale_factor == 0:
            return QPoint()
        
        relative_point = widget_pos - self.pixmap_rect_in_widget.topLeft()
        
        orig_x = int(relative_point.x() * self.scale_factor)
        orig_y = int(relative_point.y() * self.scale_factor)
        
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        orig_x = max(0, min(orig_x, orig_w))
        orig_y = max(0, min(orig_y, orig_h))
        
        return QPoint(orig_x, orig_y)

    def _orig_rect_to_widget_rect(self, orig_rect: QRect) -> QRect:
        """Converte um QRect da imagem original para coordenadas do widget."""
        if not self.original_pixmap or self.scale_factor == 0:
            return QRect()

        scaled_x1 = int(orig_rect.left() / self.scale_factor)
        scaled_y1 = int(orig_rect.top() / self.scale_factor)
        scaled_x2 = int(orig_rect.right() / self.scale_factor)
        scaled_y2 = int(orig_rect.bottom() / self.scale_factor)
        
        scaled_rect = QRect(QPoint(scaled_x1, scaled_y1), QPoint(scaled_x2, scaled_y2))
        
        return scaled_rect.translated(self.pixmap_rect_in_widget.topLeft())

    def _orig_poly_to_widget_poly(self, orig_points: list[QPoint]) -> list[QPoint]:
        """Converte uma lista de QPoints originais para coordenadas do widget."""
        if not self.original_pixmap or self.scale_factor == 0:
            return []
            
        widget_points = []
        for p in orig_points:
            scaled_x = int(p.x() / self.scale_factor)
            scaled_y = int(p.y() / self.scale_factor)
            widget_point = QPoint(scaled_x, scaled_y) + self.pixmap_rect_in_widget.topLeft()
            widget_points.append(widget_point)
        return widget_points
    # --- FIM DA CORREÇÃO ---

    def mousePressEvent(self, event: QtGui.QMouseEvent):
        
        if event.button() == Qt.MouseButton.RightButton and self.zoom_factor > 1.0:
            self.is_panning = True
            self.last_pan_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        
        if event.button() != Qt.MouseButton.LeftButton or \
           not self.pixmap_rect_in_widget.contains(event.pos()):
            return

        clamped_pos = self._clamp_pos_to_pixmap(event.pos())
        orig_pos = self._widget_to_orig_coords(clamped_pos)

        if self.mode == 'rect':
            self.is_selecting = True
            self.start_pos_orig = orig_pos
            self.selection_rect_orig = QRect(orig_pos, orig_pos)
            self.update()
            
        elif self.mode == 'poly':
            if self.poly_closed:
                self.reset_selection()
            
            if len(self.poly_points_orig) > 2:
                # O clique para fechar também deve ser em coordenadas originais
                dist_ao_inicio = (orig_pos - self.poly_points_orig[0]).manhattanLength()
                # A tolerância deve ser dimensionada
                scaled_tolerance = self.poly_click_tolerance / (1/self.scale_factor)
                
                if dist_ao_inicio < scaled_tolerance:
                    self.poly_closed = True
                    self.preview_point_orig = None 
                    self.update()
                    return 

            self.poly_points_orig.append(orig_pos)
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        
        if self.is_panning:
            delta = event.pos() - self.last_pan_pos
            self.pan_offset += delta
            self.last_pan_pos = event.pos()
            self._update_scaled_pixmap()
            event.accept()
            return

        clamped_pos = self._clamp_pos_to_pixmap(event.pos())
        orig_pos = self._widget_to_orig_coords(clamped_pos)
        
        if self.mode == 'rect':
            if self.is_selecting:
                self.selection_rect_orig = QRect(self.start_pos_orig, orig_pos).normalized()
                self.update()
                
        elif self.mode == 'poly':
            if not self.poly_closed:
                self.preview_point_orig = orig_pos
                self.update()

    def mouseReleaseEvent(self, event: QtGui.QMouseEvent):
        
        if event.button() == Qt.MouseButton.RightButton and self.is_panning:
            self.is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton and self.is_selecting:
            if self.mode == 'rect':
                self.is_selecting = False
                self.update()

    def paintEvent(self, event: QtGui.QPaintEvent):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        if self.scaled_pixmap:
            painter.drawPixmap(self.pixmap_rect_in_widget.topLeft(), self.scaled_pixmap)
        
        if not self.original_pixmap:
             painter.end()
             return

        overlay_path = QPainterPath()
        overlay_path.addRect(QRectF(self.pixmap_rect_in_widget))

        if self.has_selection():
            if self.mode == 'rect':
                # Converte o rect original para o widget rect
                widget_selection_rect = self._orig_rect_to_widget_rect(self.selection_rect_orig)
                overlay_path.addRect(QRectF(widget_selection_rect))
                
            elif self.mode == 'poly':
                # Converte os pontos originais para pontos do widget
                widget_poly_points = self._orig_poly_to_widget_poly(self.poly_points_orig)
                poly_qpolygon = QPolygonF(widget_poly_points)
                overlay_path.addPolygon(poly_qpolygon)
                
            overlay_path.setFillRule(Qt.FillRule.OddEvenFill)
        
        painter.fillPath(overlay_path, QColor(0, 0, 0, 100))

        pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.mode == 'rect' and self.has_selection():
            widget_selection_rect = self._orig_rect_to_widget_rect(self.selection_rect_orig)
            painter.drawRect(widget_selection_rect)
            
        elif self.mode == 'poly' and self.poly_points_orig:
            widget_poly_points = self._orig_poly_to_widget_poly(self.poly_points_orig)
            poly_qpolygon = QPolygonF(widget_poly_points)
            painter.drawPolyline(poly_qpolygon)
            
            if self.poly_closed:
                painter.drawLine(widget_poly_points[-1], widget_poly_points[0])
            elif self.preview_point_orig:
                widget_preview_point = self._orig_poly_to_widget_poly([self.preview_point_orig])[0]
                painter.drawLine(widget_poly_points[-1], widget_preview_point)

            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QColor("red"))
            for point in widget_poly_points:
                painter.drawEllipse(point, 4, 4)
            
            if not self.poly_closed:
                painter.setBrush(QColor("lime"))
                painter.drawEllipse(widget_poly_points[0], 5, 5)
        
        painter.end()

    def has_selection(self) -> bool:
        if self.mode == 'rect':
            return self.selection_rect_orig.isValid() and \
                   self.selection_rect_orig.width() > 5 and \
                   self.selection_rect_orig.height() > 5
        elif self.mode == 'poly':
            return self.poly_closed and len(self.poly_points_orig) > 2
        return False

    def get_crop_coords(self) -> dict | None:
        """
        Retorna as coordenadas da imagem original (agora muito mais simples).
        """
        if not self.has_selection():
            return None
        
        if self.mode == 'rect':
            # Retorna as coordenadas originais diretamente
            coords = (
                self.selection_rect_orig.left(),
                self.selection_rect_orig.top(),
                self.selection_rect_orig.right(),
                self.selection_rect_orig.bottom()
            )
            return {"mode": "rect", "coords": coords}

        elif self.mode == 'poly':
            # Retorna os pontos originais diretamente
            orig_points = [(p.x(), p.y()) for p in self.poly_points_orig]
            return {"mode": "poly", "coords": orig_points}

        return None

# =============================================================================
# --- CLASSE DE DIÁLOGO ---
# =============================================================================

class DialogoFigura(QDialog):
    
    # --- INÍCIO DA MODIFICAÇÃO (Adiciona banco_figuras) ---
    def __init__(self, figura: Figura = None, banco_figuras: list[Figura] = None, parent: QWidget = None):
    # --- FIM DA MODIFICAÇÃO ---
        
        super().__init__(parent)
        self.setWindowTitle("Editor de Figura ABNT (com Recorte)")
        self.setMinimumSize(700, 600)

        # --- INÍCIO DA MODIFICAÇÃO (Armazena dependências) ---
        self.figura_original_para_edicao = figura
        self.figura = figura if figura else Figura()
        self.banco_figuras = banco_figuras if banco_figuras else []
        # --- FIM DA MODIFICAÇÃO ---

        main_layout = QHBoxLayout(self)
        
        # =======================================================
        # --- Painel Esquerdo (Controles) ---
        # =======================================================
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
        
        right_layout.addWidget(QLabel("<b>Pré-visualização (Role=Zoom | Botão-Dir=Mover):</b>"))
        right_layout.addWidget(self.preview_label, 1)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

        self.buttons.accepted.connect(self.accept) 
        self.buttons.rejected.connect(self.reject)
        self.tool_button_group.buttonClicked.connect(self._mudar_modo_corte)
        self.btn_reset_selecao.clicked.connect(self.preview_label.reset_selection)

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
                "1. Clique e arraste (botão esquerdo) sobre a imagem para "
                "selecionar a área de corte."
            )
            self.btn_reset_selecao.setVisible(False)
        else:
            self.preview_label.set_mode('poly')
            self.info_label.setText(
                "<b>Modo Poligonal:</b>\n"
                "1. Clique (botão esquerdo) para adicionar pontos.\n"
                "2. Clique próximo ao <b>primeiro ponto</b> (verde) "
                "para fechar a seleção.\n"
                "3. Pressione <b>Ctrl+Z</b> para desfazer o último ponto.\n"
                "4. Use 'Limpar Seleção' para recomeçar."
            )
            self.btn_reset_selecao.setVisible(True)

    def procurar_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem", "", 
            "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_input.setText(caminho)
            self._atualizar_preview(caminho) 

    def _atualizar_preview(self, caminho_imagem):
        """Carrega a imagem no CropLabel."""
        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self.preview_label.setText("Imagem não encontrada.")
            self.preview_label.setOriginalPixmap(QPixmap())
            return
            
        pixmap = QtGui.QPixmap(caminho_imagem)
        self.preview_label.setOriginalPixmap(pixmap)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)

    def accept(self):
        
        # --- INÍCIO DA MODIFICAÇÃO (Verificação de Duplicidade) ---
        novo_titulo = self.titulo_input.text().strip()
        
        if not novo_titulo:
            QMessageBox.warning(self, "Campo Obrigatório", "O campo 'Título' não pode estar vazio.")
            return

        # Compara com todas as figuras no banco
        for fig_existente in self.banco_figuras:
            # 1. Compara o título (ignorando maiúsculas/minúsculas e espaços)
            if fig_existente.titulo.strip().lower() == novo_titulo.lower():
                
                # 2. Verifica se a figura encontrada é A MESMA que estamos editando.
                # Se for a mesma (mesmo objeto), permite salvar (ignora a checagem).
                if self.figura_original_para_edicao is fig_existente:
                    continue 

                # 3. Se for uma figura DIFERENTE com o mesmo nome, bloqueia.
                QMessageBox.warning(self, "Título Duplicado", 
                                    f"Já existe uma figura com o título '{novo_titulo}'.\n"
                                    "O título da figura deve ser único.")
                return # Não fecha o diálogo
        # --- FIM DA MODIFICAÇÃO ---
        
        if not self.caminho_input.text():
            QMessageBox.warning(self, "Campo Obrigatório", "Por favor, selecione um 'Arquivo da Imagem'.")
            return
            
        # Salva o título já tratado
        self.figura.titulo = novo_titulo
        self.figura.fonte = self.fonte_input.text()
        self.figura.caminho_original = self.caminho_input.text()

        largura_str = self.largura_combo.currentText()
        if "Pequena" in largura_str: self.figura.largura_cm = 8.0
        elif "Média" in largura_str: self.figura.largura_cm = 12.0
        else: self.figura.largura_cm = LARGURA_MAXIMA_CM

        if not self._processar_imagem():
            return 

        super().accept()

    def _processar_imagem(self) -> bool:
        caminho_original = self.caminho_input.text()
        dados_corte = self.preview_label.get_crop_coords()

        if (self.figura.caminho_original == caminho_original and
            self.figura.caminho_processado and
            os.path.exists(self.figura.caminho_processado) and
            not dados_corte):
            print("Nenhuma mudança na imagem, mantendo processado anterior.")
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
                img = img.convert("RGBA") 
                img_processada = img 

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
                        
                        bbox = mask.getbbox() 
                        if bbox:
                            img_processada = img_cortada.crop(bbox)
                        else:
                            img_processada = img_cortada
                
                else:
                    print("Usando imagem inteira (sem corte).")

                img_final = img_processada 
                
                if img_processada.width > LARGURA_MAXIMA_PX:
                    print("Redimensionando imagem (maior que o máximo permitido).")
                    ratio = LARGURA_MAXIMA_PX / img_processada.width
                    nova_altura = int(img_processada.height * ratio)
                    img_final = img_processada.resize((int(LARGURA_MAXIMA_PX), nova_altura), Image.Resampling.LANCZOS)
                
                if dados_corte and dados_corte['mode'] == 'poly':
                    img_final.save(caminho_saida, "PNG") 
                else:
                    img_final.convert("RGB").save(caminho_saida, "PNG") 
                
                self.figura.caminho_processado = caminho_saida
                return True
                
        except Exception as e:
            QMessageBox.critical(self, "Erro ao Processar Imagem", f"Não foi possível processar a imagem:\n{e}")
            return False

    def get_dados_figura(self) -> Figura | None:
        return self.figura