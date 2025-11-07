# dialogo_brasao.py
# Descrição: Versão atualizada com ferramenta de corte (crop)
# interativa (Retângulo e Polígono) e propriedades QSS.

import os
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QLineEdit, QComboBox,
                               QPushButton, QVBoxLayout, QHBoxLayout, QFileDialog,
                               QDialogButtonBox, QMessageBox, QRadioButton, 
                               QButtonGroup, QFrame)
from PySide6.QtGui import QPixmap, QPainter, QColor, QPen, QPolygonF, QPainterPath
from PySide6.QtCore import Qt, QRect, QPoint, QRectF
from PIL import Image, ImageDraw # Adicionado ImageDraw para a máscara

# =============================================================================
# --- CLASSE: CropLabel ---
# Esta é a ferramenta de corte interativa.
# AGORA COM SUPORTE AOS MODOS RETÂNGULO E POLÍGONO.
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
        # Só processa se o clique for dentro da imagem
        if event.button() != Qt.MouseButton.LeftButton or \
           not self.pixmap_rect_in_widget.contains(event.pos()):
            return

        clamped_pos = self._clamp_pos_to_pixmap(event.pos())

        # --- LÓGICA MODO RETÂNGULO ---
        if self.mode == 'rect':
            self.is_selecting = True
            self.start_pos = clamped_pos
            self.selection_rect = QRect(self.start_pos, self.start_pos)
            self.update()
            
        # --- LÓGICA MODO POLÍGONO ---
        elif self.mode == 'poly':
            if self.poly_closed:
                # Polígono anterior estava fechado, começa um novo
                self.reset_selection()
            
            # Verificar se o clique foi perto do primeiro ponto (para fechar)
            if len(self.poly_points) > 2:
                dist_ao_inicio = (clamped_pos - self.poly_points[0]).manhattanLength()
                if dist_ao_inicio < self.poly_click_tolerance:
                    self.poly_closed = True
                    self.preview_point = None # Esconde a linha elástica
                    self.update()
                    return # Não adiciona o último ponto, fecha o loop

            # Adiciona o novo ponto
            self.poly_points.append(clamped_pos)
            self.update()

    def mouseMoveEvent(self, event: QtGui.QMouseEvent):
        """Atualiza a seleção (modo rect) ou a linha elástica (modo poly)."""
        clamped_pos = self._clamp_pos_to_pixmap(event.pos())
        
        # --- LÓGICA MODO RETÂNGULO ---
        if self.mode == 'rect':
            if self.is_selecting:
                self.selection_rect = QRect(self.start_pos, clamped_pos).normalized()
                self.update()
                
        # --- LÓGICA MODO POLÍGONO ---
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
        
        # --- 1. Preparar o Overlay Escuro ---
        overlay_path = QPainterPath()
        overlay_path.addRect(QRectF(self.pixmap_rect_in_widget))

        # --- 2. "Cortar" a Seleção do Overlay ---
        if self.has_selection():
            if self.mode == 'rect':
                overlay_path.addRect(QRectF(self.selection_rect))
            elif self.mode == 'poly':
                poly_qpolygon = QPolygonF(self.poly_points)
                overlay_path.addPolygon(poly_qpolygon)
            
            overlay_path.setFillRule(Qt.FillRule.OddEvenFill)
        
        painter.fillPath(overlay_path, QColor(0, 0, 0, 100))

        # --- 3. Desenhar as Linhas da Seleção ---
        pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.mode == 'rect' and self.has_selection():
            painter.drawRect(self.selection_rect)
            
        elif self.mode == 'poly' and self.poly_points:
            # Desenha as linhas do polígono
            poly_qpolygon = QPolygonF(self.poly_points)
            painter.drawPolyline(poly_qpolygon)
            
            if self.poly_closed:
                # Se fechado, desenha a linha final
                painter.drawLine(self.poly_points[-1], self.poly_points[0])
            elif self.preview_point:
                # Senão, desenha a linha elástica
                painter.drawLine(self.poly_points[-1], self.preview_point)

            # --- 4. Desenhar os Pontos (Handles) do Polígono ---
            painter.setPen(QPen(QColor("white"), 1))
            painter.setBrush(QColor("red"))
            for point in self.poly_points:
                painter.drawEllipse(point, 4, 4)
            
            # Destaca o primeiro ponto
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
        Retorna um dicionário: {"mode": "rect", "coords": (l, u, r, b)}
        ou {"mode": "poly", "coords": [(x1, y1), (x2, y2), ...]}
        """
        if not self.has_selection():
            return None
        
        # --- MODO RETÂNGULO (COMO ANTES) ---
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

        # --- MODO POLÍGONO (NOVO) ---
        elif self.mode == 'poly':
            orig_points = []
            orig_w = self.original_pixmap.width()
            orig_h = self.original_pixmap.height()

            for point in self.poly_points:
                # 1. Torna o ponto relativo ao topo/esquerda da imagem
                relative_point = point - self.pixmap_rect_in_widget.topLeft()
                
                # 2. Converte as coordenadas escaladas de volta para o original
                orig_x = int(relative_point.x() * self.scale_factor)
                orig_y = int(relative_point.y() * self.scale_factor)
                
                # 3. Garante que as coordenadas não saiam dos limites
                orig_x = max(0, min(orig_x, orig_w))
                orig_y = max(0, min(orig_y, orig_h))
                
                orig_points.append((orig_x, orig_y)) # Adiciona como tupla (x, y)
                
            return {"mode": "poly", "coords": orig_points}

        return None

# =============================================================================
# --- CLASSE DE DIÁLOGO MODIFICADA ---
# =============================================================================

class DialogoBrasao(QDialog):
    def __init__(self, caminho_original: str = None, tamanho_cm: float = 2.5, parent: QWidget = None):
        super().__init__(parent)
        self.setWindowTitle("Editor de Brasão (Recorte)")
        self.setMinimumSize(700, 600) # Aumentei a altura para as novas opções

        self.caminho_original = caminho_original
        self.tamanho_cm = tamanho_cm
        self.caminho_processado = None
        self._usar_imagem_inteira = False 

        main_layout = QHBoxLayout(self)
        
        # =======================================================
        # --- Painel Esquerdo (Controles) ---
        # =======================================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        form_layout = QtWidgets.QFormLayout()

        # --- Widgets de Caminho e Tamanho ---
        self.caminho_input = QLineEdit(self.caminho_original)
        self.caminho_input.setReadOnly(True)
        
        btn_procurar = QPushButton("Procurar...")
        btn_procurar.setProperty("cssClass", "utility")
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
        
        # --- NOVO: Seletor de Ferramenta ---
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
        self.btn_reset_selecao.setVisible(False) # Visível apenas no modo polígono
        
        tool_layout.addWidget(self.radio_rect)
        tool_layout.addWidget(self.radio_poly)
        tool_layout.addWidget(self.btn_reset_selecao)
        
        left_layout.addWidget(tool_frame)
        
        # --- NOVO: Label de Instruções Dinâmico ---
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
        
        self.preview_label = CropLabel() # Nosso widget customizado
        self.preview_label.setText("A prévia do brasão aparecerá aqui.")
        
        right_layout.addWidget(QLabel("<b>Pré-visualização (Arraste para cortar):</b>"))
        right_layout.addWidget(self.preview_label, 1)
        
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 1)

        # --- Conexões de Sinais ---
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.tool_button_group.buttonClicked.connect(self._mudar_modo_corte)
        self.btn_reset_selecao.clicked.connect(self.preview_label.reset_selection)

        # --- Estado Inicial ---
        self._mudar_modo_corte() # Define o texto de instrução inicial
        if self.caminho_original:
            self._atualizar_preview(self.caminho_original)

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
        caminho, _ = QFileDialog.getOpenFileName(self, "Selecionar Imagem do Brasão", "", 
            "Arquivos de Imagem (*.png *.jpg *.jpeg *.webp *.bmp *.gif)")
        if caminho:
            self.caminho_original = caminho
            self.caminho_input.setText(caminho)
            self._atualizar_preview(caminho)

    def _atualizar_preview(self, caminho_imagem):
        if not caminho_imagem or not os.path.exists(caminho_imagem):
            self.preview_label.setText("Imagem não encontrada.")
            self.preview_label.setOriginalPixmap(QPixmap())
            return
            
        pixmap = QtGui.QPixmap(caminho_imagem)
        self.preview_label.setOriginalPixmap(pixmap)
        # self.preview_label.reset_selection() # setOriginalPixmap já faz isso

    def accept(self):
        """
        Sobrescreve o 'accept' para verificar o corte antes de fechar.
        """
        if not self.caminho_original:
            QMessageBox.warning(self, "Arquivo Necessário", "Por favor, selecione um arquivo de imagem para o brasão.")
            return

        if not self.preview_label.has_selection():
            resposta = QMessageBox.question(self, "Sem Corte",
                                            "Nenhuma área de corte foi selecionada.\n\n"
                                            "Deseja usar a imagem inteira?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if resposta == QMessageBox.StandardButton.No:
                return 
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
        Processa a imagem, aplicando o corte (retangular ou poligonal) 
        antes de redimensionar e salvar.
        """
        try:
            pasta_destino = "_brasoes_processados"
            os.makedirs(pasta_destino, exist_ok=True)
            
            nome_arquivo = os.path.basename(self.caminho_original)
            nome_base, _ = os.path.splitext(nome_arquivo)
            
            caminho_saida = os.path.join(pasta_destino, f"{nome_base}.png")
            contador = 1
            while os.path.exists(caminho_saida):
                caminho_saida = os.path.join(pasta_destino, f"{nome_base}_{contador}.png")
                contador += 1

            with Image.open(self.caminho_original) as img:
                
                # --- LÓGICA DE CORTE ATUALIZADA ---
                
                # Garante que a imagem suporte transparência para o corte poligonal
                img = img.convert("RGBA") 
                
                dados_corte = self.preview_label.get_crop_coords()
                
                # Se o usuário fez uma seleção E não forçou usar a imagem inteira
                if dados_corte and not self._usar_imagem_inteira:
                    
                    # MODO 1: Corte Retangular (Simples)
                    if dados_corte['mode'] == 'rect':
                        print(f"Aplicando corte retangular: {dados_corte['coords']}")
                        img_cortada = img.crop(dados_corte['coords'])
                    
                    # MODO 2: Corte Poligonal (Usando Máscara)
                    elif dados_corte['mode'] == 'poly':
                        print(f"Aplicando corte poligonal.")
                        
                        # 1. Criar uma máscara alfa (preta) do tamanho da imagem
                        mask = Image.new("L", img.size, 0)
                        draw = ImageDraw.Draw(mask)
                        
                        # 2. Desenhar o polígono (branco) na máscara
                        draw.polygon(dados_corte['coords'], fill=255)
                        
                        # 3. Criar uma nova imagem de saída transparente
                        img_cortada = Image.new("RGBA", img.size)
                        
                        # 4. Colar a imagem original na imagem final, usando a máscara
                        # A máscara garante que apenas os pixels dentro do polígono sejam colados
                        img_cortada.paste(img, (0, 0), mask=mask)
                        
                        # 5. Otimização: Recortar (crop) a transparência extra
                        bbox = mask.getbbox() # Pega o bounding box da área branca
                        if bbox:
                            img_cortada = img_cortada.crop(bbox)
                    
                    img = img_cortada # Substitui a imagem original pela processada

                else:
                    print("Usando imagem inteira (sem corte).")
                # ---------------------------------
                
                # Redimensiona a imagem final (já cortada)
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