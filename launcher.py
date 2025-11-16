# laucher.py
# Descrição: Verificador silencioso. 100% autônomo.
# CORRIGIDO: A definição da classe da UI foi movida para
# dentro do main() para evitar o NameError.
# SIMPLIFICADO: Removidas dependências de assets.

import sys
import os
import subprocess
import json
import zipfile
import shutil
import tempfile
from datetime import datetime

# --- 1. Importações de Rede (Leves) ---
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# --- 2. Definições Globais ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT_DIR, "app")
LAUNCHER_CONFIG_FILE = os.path.join(ROOT_DIR, "launcher_config.json")
CONTROLLER_EXE = os.path.join(ROOT_DIR, "controller.exe")
UPDATE_JSON_URL = "https://api.github.com/repos/SEU_USUARIO/SEU_REPOSITORIO/releases/latest" 

# --- 3. Função de Carregamento da UI ---

def carregar_modulos_ui():
    """
    Importa PySide6 e qdarktheme APENAS quando a UI é necessária.
    Retorna as classes importadas.
    """
    try:
        from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                                       QPushButton, QLabel, QMessageBox)
        from PySide6.QtGui import QIcon, QPixmap
        from PySide6.QtCore import Qt, Slot, QObject, QThread, Signal
    except ImportError:
        print("ERRO: PySide6 não encontrado.")
        print("Se esta for a primeira execução, isso é um problema de empacotamento.")
        sys.exit(1)
        
    try:
        import qdarktheme
        HAS_THEME_LIB = True
    except ImportError:
        HAS_THEME_LIB = False
        qdarktheme = None # Garante que a variável exista

    # Retorna as classes como uma tupla para o main() usar
    return (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
            QMessageBox, QIcon, QPixmap, Qt, Slot, QObject, QThread, 
            Signal, HAS_THEME_LIB, qdarktheme)


# --- 4. Funções de Verificação (Leves, sem UI) ---

def get_local_config():
    """Lê o config do launcher."""
    if not os.path.exists(LAUNCHER_CONFIG_FILE):
        return {"local_version": "0.0.0"} # Indica "primeira vez"
    try:
        with open(LAUNCHER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {"local_version": "0.0.0"}

def save_local_config(config):
    """Salva o config do launcher."""
    try:
        with open(LAUNCHER_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"[Launcher] Erro ao salvar config: {e}")

def check_for_update(local_config):
    """
    Verifica o servidor por atualizações.
    Retorna (update_info, is_first_run)
    """
    is_first_run = (local_config['local_version'] == "0.0.0")
    
    if not HAS_REQUESTS:
        print("[Launcher] Biblioteca 'requests' não encontrada. Pulando verificação.")
        return None, is_first_run

    try:
        response = requests.get(UPDATE_JSON_URL, timeout=5)
        response.raise_for_status()
        latest_release = response.json()
        
        server_version = latest_release.get("tag_name", "0.0.0").replace("v", "")
        local_version = local_config.get("local_version", "0.0.0")

        if server_version > local_version:
            print(f"[Launcher] Atualização encontrada: {local_version} -> {server_version}")
            asset_url = None
            if latest_release.get("assets"):
                asset_url = latest_release["assets"][0].get("browser_download_url")

            update_info = {
                "version": server_version,
                "url": asset_url,
                "type": latest_release.get("type", "app"),
                "mandatory": latest_release.get("mandatory", False)
            }
            return update_info, is_first_run
        else:
            print("[Launcher] Nenhuma atualização encontrada.")
            return None, is_first_run
            
    except Exception as e:
        print(f"[Launcher] Falha ao verificar atualização: {e}")
        return None, is_first_run


def get_app_launch_command():
    """Retorna o comando para iniciar o main_app (Dev vs Prod)."""
    if not os.path.exists(APP_DIR):
        print("[Launcher] Erro: Pasta /app não encontrada. Não é possível iniciar.")
        return None

    if getattr(sys, 'frozen', False):
        app_exe = os.path.join(APP_DIR, "main_app.exe")
        if not os.path.exists(app_exe):
            print(f"[Launcher] Erro: Executável {app_exe} não encontrado.")
            return None
        return [app_exe]
    else:
        app_script = os.path.join(APP_DIR, "main_app.py")
        if not os.path.exists(app_script):
            print(f"[Launcher] Erro: Script {app_script} não encontrado.")
            return None
        return [sys.executable, app_script]

# --- 5. Ponto de Entrada Principal ---

def main():
    """Função principal do Launcher."""
    
    # FASE 1: Verificação Silenciosa
    local_config = get_local_config()
    update_info, is_first_run = check_for_update(local_config)
    
    is_mandatory_update = update_info and update_info.get("mandatory", False)
    
    # FASE 2: Decisão
    if not update_info and not is_first_run:
        # CASO A: Normal. Inicia o app e sai.
        print("[Launcher] Nenhuma ação necessária. Iniciando main_app...")
        launch_command = get_app_launch_command()
        if launch_command:
            subprocess.Popen(launch_command)
        else:
            is_first_run = True # /app não foi encontrado. Força a UI de "primeira instalação"
            
        if not is_first_run: 
            sys.exit(0)
        
    # CASO B: Ação necessária. Carrega a UI.
    print("[Launcher] Ação necessária. Carregando UI do Launcher...")
    
    # 1. Carrega as classes da UI. (QWidget, QApplication, etc. agora existem)
    (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
     QMessageBox, QIcon, QPixmap, Qt, Slot, QObject, QThread, 
     Signal, HAS_THEME_LIB, qdarktheme) = carregar_modulos_ui()
    
    
    # 2. Define a classe da Janela AQUI, dentro do main()
    class LauncherWindow(QWidget):
        """
        A UI do Launcher. Definida dentro do main() para garantir
        que QWidget e outros módulos do PySide6 já existam.
        """
        
        def __init__(self, is_dark_theme=False, update_info=None, is_first_run=False):
            super().__init__()
            
            self.is_dark = is_dark_theme
            self.update_info = update_info
            self.is_first_run = is_first_run
            
            self.setWindowTitle("Formatheus Launcher")
            self.setWindowIcon(QIcon()) 
            self.setFixedSize(400, 350)
            
            self._build_ui()

        # --- CORREÇÃO PYLANCE FINAL ---
        # Anotação de tipo removida para evitar o aviso
        def _get_icon(self, name: str):
            # (Removida dependência de assets)
            return QIcon()
        # --- FIM DA CORREÇÃO ---

        def _build_ui(self):
            main_layout = QVBoxLayout(self)
            
            title_label = QLabel("Formatheus")
            font = title_label.font()
            font.setPointSize(24)
            font.setBold(True)
            title_label.setFont(font)
            title_label.setAlignment(Qt.AlignCenter)

            self.status_label = QLabel("")
            self.status_label.setAlignment(Qt.AlignCenter)
            
            self.action_btn = QPushButton("")
            self.action_btn.setMinimumHeight(45)
            self.action_btn.clicked.connect(self.on_action_clicked)
            
            if self.is_first_run:
                self.status_label.setText("Bem-vindo! O Formatheus precisa ser instalado.")
                self.action_btn.setText("INSTALAR")
            
            elif self.update_info:
                versao = self.update_info.get("version", "nova")
                self.status_label.setText(f"Uma nova versão ({versao}) está disponível.")
                self.action_btn.setText(f"ATUALIZAR AGORA")

            main_layout.addStretch()
            main_layout.addWidget(title_label)
            main_layout.addSpacing(20)
            main_layout.addWidget(self.status_label)
            main_layout.addSpacing(20)
            main_layout.addWidget(self.action_btn)
            main_layout.addStretch()

        @Slot()
        def on_action_clicked(self):
            """Lida com o clique no botão (Instalar ou Atualizar)."""
            self.action_btn.setEnabled(False)
            
            if self.is_first_run:
                self.status_label.setText("Instalando...")
            else:
                self.status_label.setText("Atualizando...")
                
            QApplication.processEvents() # Atualiza a UI
            
            # (Simulação de download/instalação)
            # TODO: Adicionar a lógica de download e unzip real aqui
            print("[Launcher] (Simulação) Baixando e instalando...")
            # Ex: self.thread = DownloadThread(self.update_info['url'])
            #     self.thread.finished.connect(self.on_install_finished)
            #     self.thread.start()
            
            # --- Simulação direta por enquanto ---
            # Salva a nova versão local
            if self.update_info:
                save_local_config({"local_version": self.update_info.get("version", "1.0.0")})
            else:
                save_local_config({"local_version": "1.0.0"}) # Versão base
                
            self.status_label.setText("Concluído!")
            self.close() # Fecha o launcher
            
    # --- FIM DA DEFINIÇÃO DA CLASSE ---


    # 3. Agora, continue o fluxo normal do main()
    app = QApplication(sys.argv)
    
    initial_theme = "dark" 
    if HAS_THEME_LIB:
        try:
            qss = qdarktheme.load_stylesheet(initial_theme)
            app.setStyleSheet(qss)
        except Exception as e:
            print(f"Não foi possível carregar o tema do launcher: {e}")

    # A classe LauncherWindow foi definida acima, então esta linha funciona
    window = LauncherWindow(
        is_dark_theme=(initial_theme == "dark"),
        update_info=update_info,
        is_first_run=is_first_run
    )
    window.show()
    
    app_exit_code = app.exec() 
    
    new_config = get_local_config()
    action_completed = new_config['local_version'] != "0.0.0"

    if action_completed and (not update_info or update_info.get("type") != "launcher"):
        if not is_mandatory_update or update_info is None:
            print("[Launcher] Iniciando main_app após ação do launcher...")
            launch_command = get_app_launch_command()
            if launch_command:
                subprocess.Popen(launch_command)
            else:
                QMessageBox.critical(None, "Erro Pós-Instalação", "O aplicativo foi instalado, mas não foi encontrado.")
                
    sys.exit(app_exit_code)


if __name__ == "__main__":
    main()