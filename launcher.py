# launcher.py
# v3.2 - Arquitetura Side-Loading (.bin externo + Extração segura) + Debug Button
# Correção WinError 5 e Detecção de Binário Versionado

import sys
import os
import subprocess
import json
import zipfile
import shutil
import tempfile
import time
from datetime import datetime
import uuid 
import platform 
import re 
import stat # Necessário para corrigir o erro de permissão

# Imports para a checagem de segurança HMAC
import hmac 
import hashlib
from datetime import datetime, timezone

# --- VARIÁVEIS DE SEGURANÇA ---
# IMPORTANTE: Deve ser IDÊNTICO ao que está no main_app.py
DYNAMIC_SECRET_SALT = b"OWIYVQUXJ64IJETQPXT1UZZ16YBNI8" 
# ------------------------------

# --- NOVA IMPORTAÇÃO ---
try:
    from packaging import version
except ImportError:
    # Fallback simples se packaging não existir
    class version:
        @staticmethod
        def parse(v): return v
    print("Aviso: 'packaging' não encontrado. Usando comparação simples.")
# --------------------

# --- Importações do Projeto ---
try:
    import firebase_client
    import lease_manager
    import download_manager 
except ImportError as e:
    print(f"ERRO CRÍTICO: Não foi possível importar os módulos de licença: {e}")
    sys.exit(1)
# -----------------------------

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# --- 1. Importações de Rede (Leves) ---
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ============================================================================
# --- DEFINIÇÕES GLOBAIS E CAMINHOS (ARQUITETURA SIDE-LOADING) ---
# ============================================================================

# Se estiver compilado (exe), usa sys.argv[0] para pegar a pasta real onde o arquivo está.
if "__compiled__" in globals():
    # NUITKA: sys.argv[0] é o caminho do executável .exe original clicado
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
elif getattr(sys, 'frozen', False):
    # PyInstaller: sys.executable é o caminho do .exe
    ROOT_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    # VS Code / Python Script
    ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Pastas de Destino (Cofre)
# Ex: C:\Users\Nome\AppData\Local\Formatheus\Core
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
BASE_EXTRACT_DIR = os.path.join(LOCAL_APP_DATA, "Formatheus")
EXTRACT_DIR = os.path.join(BASE_EXTRACT_DIR, "Core")

# --- EDIÇÃO 1: FORÇAR CRIAÇÃO DA PASTA AGORA ---
# Isso garante que o launcher_config.json possa ser salvo imediatamente
try:
    os.makedirs(BASE_EXTRACT_DIR, exist_ok=True)
except Exception as e:
    print(f"[Launcher] Erro ao criar pasta de dados: {e}")
# -----------------------------------------------

# Onde está o executável real após a extração
MAIN_APP_EXE = os.path.join(EXTRACT_DIR, "main_app.exe")

LAUNCHER_CONFIG_FILE = os.path.join(BASE_EXTRACT_DIR, "launcher_config.json")
CONTROLLER_EXE = os.path.join(ROOT_DIR, "controller.exe")

# ============================================================================
# --- FUNÇÕES AUXILIARES DE ARQUIVO ---
# ============================================================================

def remove_readonly(func, path, excinfo):
    """
    Callback para shutil.rmtree que força a remoção de arquivos Read-Only.
    Isso corrige o [WinError 5] Acesso Negado.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def delete_folder_robust(path, retries=5, delay=0.5):
    """
    Tenta deletar uma pasta repetidamente para evitar WinError 5 / Access Denied
    causado por antivírus ou indexadores do Windows segurando o arquivo.
    """
    if not os.path.exists(path):
        return True
        
    for i in range(retries):
        try:
            shutil.rmtree(path, onerror=remove_readonly)
            return True
        except OSError:
            if i < retries - 1:
                time.sleep(delay)
            else:
                print(f"[Launcher] Falha ao deletar {path} após {retries} tentativas.")
                return False
    return False

def find_local_bin_and_version():
    """Procura arquivos .bin na pasta do executável (ROOT_DIR)."""
    melhor_arquivo = None
    melhor_versao = "0.0.0"

    if not os.path.exists(ROOT_DIR): return None, None

    try:
        arquivos = os.listdir(ROOT_DIR)
    except Exception: return None, None

    # Regex Flexível: Aceita 'app_v1.0.0.bin', 'app_v1.2.bin', etc.
    padrao = re.compile(r"^app_v(.+)\.bin$", re.IGNORECASE)

    candidatos = []
    for arquivo in arquivos:
        match = padrao.match(arquivo)
        if match:
            ver_str = match.group(1)
            full_path = os.path.join(ROOT_DIR, arquivo)
            candidatos.append((full_path, ver_str))
            print(f"[Launcher] Encontrado candidato: {arquivo}")

    # Pega a maior versão encontrada
    for caminho, ver_str in candidatos:
        try:
            if version.parse(ver_str) > version.parse(melhor_versao):
                melhor_versao = ver_str
                melhor_arquivo = caminho
        except:
            pass # Ignora versões inválidas

    return melhor_arquivo, melhor_versao

# ============================================================================
# --- LÓGICA DE EXTRAÇÃO INTELIGENTE ---
# ============================================================================

def ensure_core_is_ready():
    """
    Gerencia a extração. Prioriza o arquivo local app_vX.bin.
    Retorna uma tupla: (is_ready: bool, was_just_extracted: bool)
    """
    local_bin_path, local_bin_version = find_local_bin_and_version()
    
    # Config atual
    config = get_launcher_config()
    installed_version = config.get("app_version", "0.0.0")
    
    needs_extraction = False

    # 1. Verifica se deve extrair
    if local_bin_path:
        # Se não tem nada instalado
        if not os.path.exists(EXTRACT_DIR):
            print(f"[Launcher] Instalação limpa detectada via local bin (v{local_bin_version}).")
            needs_extraction = True
        
        # Se o bin local é mais novo que o instalado
        elif version.parse(local_bin_version) > version.parse(installed_version):
            print(f"[Launcher] Atualização Local: Binário (v{local_bin_version}) > Instalado (v{installed_version}).")
            needs_extraction = True
            
        # Opcional: Se arquivo foi modificado (re-build dev), descomente abaixo
        # elif os.path.getmtime(local_bin_path) > os.path.getmtime(EXTRACT_DIR):
        #    needs_extraction = True

    if needs_extraction and local_bin_path:
        try:
            print(f"[Launcher] Iniciando extração de '{os.path.basename(local_bin_path)}'...")
            
            # Limpeza Robusta (Resolve WinError 5)
            temp_trash = EXTRACT_DIR + "_trash_" + str(uuid.uuid4())[:8]
            
            # Tenta mover a pasta atual para o lixo primeiro (Atomic move é mais seguro que delete)
            if os.path.exists(EXTRACT_DIR):
                try:
                    os.rename(EXTRACT_DIR, temp_trash)
                except OSError:
                    # Se não der pra mover, tenta deletar direto
                    pass

            # Limpa o lixo antigo se existir
            if os.path.exists(temp_trash):
                delete_folder_robust(temp_trash)
            
            # Garante que o local de destino está limpo
            delete_folder_robust(EXTRACT_DIR)
            
            time.sleep(0.2) # Breve pausa para o OS liberar handles
            os.makedirs(EXTRACT_DIR, exist_ok=True)
            
            with zipfile.ZipFile(local_bin_path, 'r') as z:
                z.extractall(EXTRACT_DIR)
            
            os.utime(EXTRACT_DIR, None)
            
            # Atualiza config
            config["app_version"] = local_bin_version
            save_launcher_config(config)
            
            print("[Launcher] Extração local concluída com sucesso.")
            
            # Tenta limpar o lixo restante em background (não falha se não conseguir)
            if os.path.exists(temp_trash):
                try:
                    shutil.rmtree(temp_trash, onerror=remove_readonly)
                except: pass

            return True, True # (Pronto, Acabou de Extrair)

        except Exception as e:
            print(f"[Launcher] FALHA FATAL na extração: {e}")
            # Se falhou, verifica se o app antigo ainda funciona
            return os.path.exists(MAIN_APP_EXE), False

    # Se não precisou extrair (ou não achou bin), verifica se o app já existe
    if os.path.exists(MAIN_APP_EXE):
        return True, False
    
    # Não existe app e não existe bin local
    return False, False


def get_app_launch_command():
    """Retorna o comando para iniciar o app extraído no AppData."""
    if os.path.exists(MAIN_APP_EXE):
        return [MAIN_APP_EXE]
    
    print(f"[Launcher] Erro: Executável principal não encontrado em: {MAIN_APP_EXE}")
    return None


# --- 3. Função de Carregamento da UI ---
def carregar_modulos_ui():
    try:
        from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                                     QPushButton, QLabel, QMessageBox,
                                     QLineEdit, QDialog, QListWidget, 
                                     QDialogButtonBox, QListWidgetItem,
                                     QProgressBar, QPlainTextEdit, QSpacerItem,
                                     QSizePolicy) 
        from PySide6.QtGui import QIcon, QPixmap, QFont
        from PySide6.QtCore import Qt, Slot, QObject, QThread, Signal, QDate 
    except ImportError:
        print("ERRO: PySide6 não encontrado.")
        sys.exit(1)
        
    try:
        import qdarktheme
        HAS_THEME_LIB = True
    except ImportError:
        HAS_THEME_LIB = False
        qdarktheme = None 

    return (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
            QMessageBox, QIcon, QPixmap, Qt, Slot, QObject, QThread, 
            Signal, HAS_THEME_LIB, qdarktheme, QLineEdit, QDialog, 
            QListWidget, QDialogButtonBox, QListWidgetItem, QFont, QDate,
            QProgressBar, QHBoxLayout, QPlainTextEdit, QSpacerItem, QSizePolicy)


# --- 4. Funções de Configuração e Verificação ---

def get_launcher_config():
    if not os.path.exists(LAUNCHER_CONFIG_FILE):
        return {} 
    try:
        with open(LAUNCHER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {} 

def save_launcher_config(config_data):
    try:
        with open(LAUNCHER_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"[Launcher] Erro ao salvar config: {e}")

def get_or_create_device_id(config):
    if "device_id" in config and config["device_id"]:
        return config["device_id"]
    device_id = str(uuid.uuid4())
    config["device_id"] = device_id
    save_launcher_config(config)
    print(f"[Launcher] Novo Device ID gerado: {device_id}")
    return device_id

def get_local_license_key(config):
    return config.get("license_key")

def get_hostname():
    return platform.node()

def check_for_update_firebase(current_app_version: str):
    """
    Chama a função 'check_for_update' do Firebase.
    """
    print(f"[Launcher] Verificando servidor com versão local: {current_app_version}")
    try:
        payload = {"current_version": current_app_version}
        response = firebase_client.call_firebase_function("check_for_update", payload)
        
        if response.get("status") == "success":
            # Retorna (update_disponivel, infos_da_versao)
            return response.get("update_available", False), response.get("latest_info")
        else:
            print(f"[Launcher] Erro ao verificar atualização: {response.get('message')}")
            return False, None
            
    except Exception as e:
        print(f"[Launcher] Falha crítica ao verificar atualização: {e}")
        return False, None

# --- 5. Ponto de Entrada Principal ---

def main():
    """Função principal do Launcher."""
    print("[Launcher] Iniciando...")

    # --- PASSO 0: PREPARAR O CORE (SIDE-LOADING) ---
    # Verifica e extrai o binário ANTES de qualquer coisa
    core_is_ready, extracted_locally = ensure_core_is_ready()

    launcher_config = get_launcher_config()
    device_id = get_or_create_device_id(launcher_config)
    
    is_activated = False
    ui_mode = "activate"
    initial_response = None
    error_message = ""

    # Se o core não estiver pronto e não houver binário, erro fatal (a menos que vá instalar)
    if not core_is_ready:
        # Se não tem core, assumimos que pode ser uma instalação limpa que precisa baixar
        pass 
    
    # --- FASE 1: Verificação de Licença (Offline e Online) ---
    lease_data = lease_manager.read_lease(device_id)

    if lease_data:
        print("[Launcher] Lease local encontrado. Verificando validade...")
        lease_status, message = lease_manager.check_lease_validity(lease_data)
        
        if lease_status == "ok":
            print("[Launcher] Lease offline VÁLIDO.")
            is_activated = True
            ui_mode = "check_update"
            
        elif lease_status == "expired":
            error_message = f"Sua licença expirou em {lease_data.get('real_expiry')}.\nPor favor, renove seu plano para continuar."
            ui_mode = "show_error"
            
        elif lease_status == "stale":
            print("[Launcher] Lease offline venceu. Verificação online necessária.")
            ui_mode = "verify_online"
    else:
        print("[Launcher] Nenhum lease local encontrado.")
        license_key = get_local_license_key(launcher_config)
        
        if license_key:
            ui_mode = "verify_online"
        else:
            ui_mode = "activate"

    # --- FASE 2: Verificação Online (Se necessário) ---
    if ui_mode == "verify_online":
        print("[Launcher] Contatando servidor de licenças...")
        license_key = get_local_license_key(launcher_config)
        
        if not license_key: 
             ui_mode = "activate"
        else:
            payload = { "license_key": license_key, "device_id": device_id, "hostname": get_hostname() }
            response = firebase_client.call_firebase_function("activate_device", payload)
            status = response.get("status")

            if status == "success":
                print("[Launcher] Verificação online OK.")
                lease_manager.write_lease(response['real_expiry'], device_id)
                is_activated = True
                ui_mode = "check_update"
            
            elif status == "limit_reached":
                is_activated = False
                ui_mode = "replace_device" 
                initial_response = response 
            
            else:
                is_activated = False
                ui_mode = "show_error"
                error_message = f"Sua licença não pôde ser validada:\n\n{response.get('message')}"

    # --- FASE 3: Verificação de Atualização ---
    
    update_info = None 
    
    if ui_mode == "check_update":
        
        # --- MODIFICAÇÃO: Se extraiu localmente, PULA o Firebase ---
        if extracted_locally:
            print("[Launcher] Instalação local detectada. Iniciando direto sem verificar online.")
            
            # Gera o token necessário para o app abrir
            now_utc = datetime.now(timezone.utc).replace(microsecond=0)
            timestamp_str = now_utc.isoformat()
            token = hmac.new(DYNAMIC_SECRET_SALT, timestamp_str.encode('utf-8'), hashlib.sha256).hexdigest()
            
            env_dict = os.environ.copy()
            env_dict["FORMATHEUS_TOKEN"] = token
            env_dict["FORMATHEUS_TIMESTAMP"] = timestamp_str
            
            launch_command = get_app_launch_command()
            if launch_command:
                subprocess.Popen(launch_command, env=env_dict)
                sys.exit(0)
            else:
                # Erro estranho: Extraiu mas não achou o exe
                print("[Launcher] Erro: Binário extraído, mas main_app.exe não encontrado.")
                ui_mode = "show_error"
                error_message = "A instalação local falhou: Executável não encontrado após extração."

        else:
            # --- CAMINHO PADRÃO: Verifica Firebase ---
            app_version = launcher_config.get("app_version", "0.0.0")
            
            update_available, latest_info = check_for_update_firebase(app_version)
            
            # --- PREPARAÇÃO DO TOKEN DE SEGURANÇA ---
            # Geramos o token aqui também para caso o app esteja atualizado e vá iniciar
            now_utc = datetime.now(timezone.utc).replace(microsecond=0)
            timestamp_str = now_utc.isoformat()
            token = hmac.new(DYNAMIC_SECRET_SALT, timestamp_str.encode('utf-8'), hashlib.sha256).hexdigest()
            
            env_dict = os.environ.copy()
            env_dict["FORMATHEUS_TOKEN"] = token
            env_dict["FORMATHEUS_TIMESTAMP"] = timestamp_str
            # ----------------------------------------
            
            # Fallback para falha de conexão (Servidor offline ou sem internet)
            if not latest_info:
                launch_command = get_app_launch_command()
                # Se temos o app instalado (core_is_ready), iniciamos ele mesmo sem checar update
                if launch_command and core_is_ready:
                    print("[Launcher] Falha ao checar servidor. Iniciando versão instalada...")
                    subprocess.Popen(launch_command, env=env_dict)
                    sys.exit(0)
                else:
                    ui_mode = "show_error"
                    error_message = "Não foi possível contatar o servidor e o aplicativo não está instalado."
            
            else:
                # Servidor respondeu com sucesso
                update_info = latest_info
                
                launch_command = get_app_launch_command()
                app_exists_locally = launch_command is not None and core_is_ready
                
                remote_version = update_info.get("version", "0.0.0")
                
                # 1. App não existe (instalação limpa via internet)
                if not app_exists_locally:
                    print("[Launcher] App não encontrado. Forçando instalação via download.")
                    ui_mode = "install"
                
                # 2. Atualização disponível (Servidor > Local)
                elif app_exists_locally and version.parse(app_version) < version.parse(remote_version):
                    print(f"[Launcher] Atualização encontrada: {app_version} -> {remote_version}")
                    ui_mode = "update"
                
                # 3. Primeira execução pós-instalação manual antiga (fix de versão 0.0.0)
                elif app_exists_locally and app_version == "0.0.0":
                    print(f"[Launcher] Registrando versão inicial {remote_version} e iniciando.")
                    launcher_config["app_version"] = remote_version
                    save_launcher_config(launcher_config)
                    subprocess.Popen(launch_command, env=env_dict)
                    sys.exit(0)
                    
                # 4. Tudo atualizado
                else:
                    print("[Launcher] App atualizado. Iniciando...")
                    subprocess.Popen(launch_command, env=env_dict)
                    sys.exit(0)
                    
                # Guarda as infos para usar na UI (notas da versão, etc)
                update_info = latest_info

    # --- FASE 4: Carregar a UI ---
    print(f"[Launcher] Ação de UI necessária: {ui_mode}")

    (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
     QMessageBox, QIcon, QPixmap, Qt, Slot, QObject, QThread, 
     Signal, HAS_THEME_LIB, qdarktheme, QLineEdit, QDialog, 
     QListWidget, QDialogButtonBox, QListWidgetItem, QFont, QDate,
     QProgressBar, QHBoxLayout, QPlainTextEdit, QSpacerItem, 
     QSizePolicy) = carregar_modulos_ui() 
    
    from download_manager import DownloadWorker

    if ui_mode == "show_error":
        temp_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erro do Launcher", error_message)
        sys.exit(1)
        
    
    class DialogoDispositivos(QDialog):
        def __init__(self, device_list, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Limite de Dispositivos Atingido")
            try: 
                icon_path = resource_path(os.path.join("launcher_assets", "icons", "formatheus.ico"))
                self.setWindowIcon(QIcon(icon_path))
            except Exception: pass
            self.setMinimumWidth(450)
            self.selected_device_id = None
            layout = QVBoxLayout(self)
            label = QLabel("Sua licença atingiu o limite de máquinas ativas.\n"
                           "Selecione um dispositivo antigo para desativar:")
            layout.addWidget(label)
            self.list_widget = QListWidget()
            for device in device_list:
                item_text = f"{device.get('hostname')} (ID: ...{device.get('id')[-12:]})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, device.get('id')) 
                self.list_widget.addItem(item)
            layout.addWidget(self.list_widget)
            self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Substituir Dispositivo")
            self.button_box.button(QDialogButtonBox.StandardButton.Ok).setProperty("cssClass", "primary")
            self.button_box.accepted.connect(self.handle_accept)
            self.button_box.rejected.connect(self.reject)
            layout.addWidget(self.button_box)
        def handle_accept(self):
            selected_item = self.list_widget.currentItem()
            if not selected_item:
                QMessageBox.warning(self, "Seleção Necessária", "Você deve selecionar um dispositivo para substituir.")
                return
            self.selected_device_id = selected_item.data(Qt.ItemDataRole.UserRole)
            self.accept()
    
    # --- JANELA DO LAUNCHER ---
    class LauncherWindow(QWidget):
        def __init__(self, is_dark_theme=False, ui_mode="activate", 
                     update_info=None, initial_response=None):
            super().__init__()

            self.launch_pending = False
            
            self.is_dark = is_dark_theme
            self.ui_mode = ui_mode 
            self.update_info = update_info
            self.initial_response = initial_response 
            
            self.config = get_launcher_config()
            self.device_id = self.config.get("device_id")
            self.license_key = self.config.get("license_key")
            
            self.download_thread = None 
            self.download_worker = None 
            
            self.setWindowTitle("Formatheus Launcher")

            try:
                icon_path = resource_path(os.path.join("launcher_assets", "icons", "formatheus.ico"))
                self.setWindowIcon(QIcon(icon_path)) 
            except Exception: pass
            
            self.setMinimumSize(450, 400)
            self._build_ui()
            
            if self.ui_mode == "replace_device":
                self.show_replacement_dialog() 

        def _build_ui(self):
            layout = self.layout()
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
            else:
                layout = QVBoxLayout(self)
                self.setLayout(layout)
            
            # --- CABEÇALHO COM BOTÃO DE DEBUG ---
            header_layout = QHBoxLayout()
            
            title_label = QLabel("Formatheus")
            font = QFont("Segoe UI", 24)
            font.setBold(True)
            title_label.setFont(font)
            
            # Botão de Debug (Pasta) - Abre o local onde o .exe foi extraído
            self.btn_debug = QPushButton("📂")
            self.btn_debug.setToolTip("Abrir pasta de instalação (Debug)")
            self.btn_debug.setFixedSize(30, 30)
            self.btn_debug.setCursor(Qt.PointingHandCursor)
            self.btn_debug.setStyleSheet("background: transparent; border: none; font-size: 16px;")
            self.btn_debug.clicked.connect(self.open_debug_folder)
            
            # Só mostra se a pasta existe
            if not os.path.exists(EXTRACT_DIR): 
                self.btn_debug.setVisible(False)

            header_layout.addStretch() 
            header_layout.addWidget(title_label)
            header_layout.addStretch() 
            header_layout.addWidget(self.btn_debug)
            # ------------------------------------

            self.status_label = QLabel("")
            self.status_label.setAlignment(Qt.AlignCenter)
            
            self.key_input = QLineEdit()
            self.key_input.setPlaceholderText("Cole sua chave de licença (FMT-...)")
            self.key_input.setAlignment(Qt.AlignCenter)
            
            self.release_notes_label = QLabel("Notas da Versão:")
            self.release_notes_label.setVisible(False)
            self.release_notes_area = QPlainTextEdit()
            self.release_notes_area.setReadOnly(True)
            self.release_notes_area.setVisible(False)
            
            self.progress_bar = QProgressBar()
            self.progress_bar.setVisible(False) 
            self.progress_bar.setTextVisible(True)
            self.progress_bar.setFormat("%p% - Baixando...")

            self.button_layout = QHBoxLayout()
            
            self.skip_btn = QPushButton("Pular e Iniciar")
            self.skip_btn.setProperty("cssClass", "secondary")
            self.skip_btn.clicked.connect(self.launch_anyway)
            
            self.action_btn = QPushButton("")
            self.action_btn.setMinimumHeight(45)
            self.action_btn.setProperty("cssClass", "primary")
            self.action_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            
            self.button_layout.addWidget(self.skip_btn)
            self.button_layout.addWidget(self.action_btn)
            
            try:
                self.action_btn.clicked.disconnect()
            except RuntimeError: pass
            self.action_btn.clicked.connect(self.on_action_clicked)
            
            self.update_ui_for_mode() 

            layout.addLayout(header_layout) # Usa o header modificado
            layout.addSpacing(10)
            layout.addWidget(self.status_label)
            layout.addSpacing(10)
            layout.addWidget(self.key_input)
            layout.addWidget(self.release_notes_label)
            layout.addWidget(self.release_notes_area)
            layout.addWidget(self.progress_bar) 
            layout.addStretch(1)
            layout.addLayout(self.button_layout)

        def open_debug_folder(self):
            """Abre a pasta de instalação (AppData) no Explorer."""
            try:
                if os.path.exists(EXTRACT_DIR):
                    os.startfile(EXTRACT_DIR)
                else:
                    QMessageBox.warning(self, "Aviso", "A pasta de instalação ainda não foi criada.")
            except Exception as e:
                print(f"Erro ao abrir pasta: {e}")

        def update_ui_for_mode(self):
            self.key_input.setVisible(False)
            self.progress_bar.setVisible(False)
            self.release_notes_label.setVisible(False)
            self.release_notes_area.setVisible(False)
            self.skip_btn.setVisible(False)
            self.action_btn.setVisible(True)

            if self.ui_mode == "activate":
                self.status_label.setText("Por favor, ative seu produto para continuar.")
                self.action_btn.setText("ATIVAR LICENÇA")
                self.key_input.setVisible(True)
            
            elif self.ui_mode == "replace_device":
                self.status_label.setText("Limite de dispositivos atingido.")
                self.action_btn.setText("GERENCIAR DISPOSITIVOS")
                self.key_input.setText(self.license_key) 
                self.key_input.setReadOnly(True) 
                self.key_input.setVisible(True)

            elif self.ui_mode == "install":
                v = self.update_info.get("version", "...")
                self.status_label.setText(f"Bem-vindo! Versão {v} pronta para instalar.")
                self.action_btn.setText(f"INSTALAR (v{v})")
                self.show_release_notes()
            
            elif self.ui_mode == "update":
                v = self.update_info.get("version", "nova")
                is_mandatory = self.update_info.get("is_mandatory", False)
                
                if is_mandatory:
                    self.status_label.setText(f"Atualização obrigatória (v{v}) disponível.")
                    self.action_btn.setText(f"ATUALIZAR AGORA (v{v})")
                    self.skip_btn.setVisible(False)
                else:
                    self.status_label.setText(f"Atualização opcional (v{v}) disponível.")
                    self.action_btn.setText(f"ATUALIZAR (v{v})")
                    self.skip_btn.setVisible(True)
                
                self.show_release_notes()
            
            elif self.ui_mode == "downloading":
                self.status_label.setText("Iniciando download...")
                self.action_btn.setVisible(False) 
                self.skip_btn.setVisible(False)
                self.progress_bar.setVisible(True) 
                self.progress_bar.setValue(0)
                self.show_release_notes()

        def show_release_notes(self):
            if self.update_info:
                notes = self.update_info.get("release_notes", "Nenhuma nota disponível.")
                if notes:
                    self.release_notes_label.setVisible(True)
                    self.release_notes_area.setPlainText(notes)
                    self.release_notes_area.setVisible(True)

        @Slot()
        def launch_anyway(self):
            print("[Launcher] Usuário optou por pular a atualização.")
            self.close()
                
        @Slot()
        def on_action_clicked(self):
            if self.ui_mode == "activate":
                self.handle_activation()
            elif self.ui_mode == "replace_device":
                self.show_replacement_dialog()
            elif self.ui_mode == "install" or self.ui_mode == "update":
                self.handle_install_update()
            else:
                self.close() 

        def handle_activation(self):
            chave = self.key_input.text().strip().upper()
            if not chave:
                QMessageBox.warning(self, "Erro", "Insira a chave.")
                return

            self.action_btn.setEnabled(False)
            self.action_btn.setText("Ativando...")
            QApplication.processEvents()
            
            payload = {
                "license_key": chave,
                "device_id": self.device_id,
                "hostname": platform.node()
            }
            
            # 1. Ativa no servidor
            response = firebase_client.call_firebase_function("activate_device", payload)
            
            if response.get("status") == "success":
                # Salva licença e lease
                self.license_key = chave
                self.config["license_key"] = chave
                lease_manager.write_lease(response['real_expiry'], self.device_id)
                
                # --- CORREÇÃO DE VERSÃO AQUI ---
                
                # 1. Recarrega a config do disco. 
                # Motivo: O ensure_core_is_ready() rodou no início e salvou a versão do .bin no JSON.
                # Precisamos ler esse valor atualizado.
                self.config = get_launcher_config() 
                versao_atual = self.config.get("app_version", "0.0.0")
                
                print(f"[Launcher] Versão local detectada pós-ativação: {versao_atual}")
                
                # 2. Verifica se o binário existe fisicamente (dupla checagem)
                launch_cmd = get_app_launch_command()
                is_installed = launch_cmd is not None
                
                if is_installed and versao_atual != "0.0.0":
                    # CENÁRIO PERFEITO: Já extraímos o .bin no boot.
                    # Não precisamos perguntar nada ao servidor agora.
                    # Assumimos que o .bin local é o que o usuário quer usar.
                    QMessageBox.information(self, "Sucesso", "Ativado! Iniciando versão local...")
                    self.launch_pending = True
                    self.close()
                    return

                # 3. Se NÃO estiver instalado ou for realmente 0.0.0 (sem bin local), 
                # aí sim perguntamos ao servidor usando a versão atual (e não hardcoded)
                save_launcher_config(self.config)
                
                # Aqui enviamos 'versao_atual' (ex: 1.0.0) em vez de "0.0.0"
                update_avail, latest_info = check_for_update_firebase(versao_atual)
                
                if latest_info:
                    rem_ver = latest_info.get("version")
                    # Só oferece download se a remota for MAIOR que a local
                    if version.parse(rem_ver) > version.parse(versao_atual):
                        self.update_info = latest_info
                        self.ui_mode = "update" # Ou install
                        self.update_ui_for_mode()
                        self.action_btn.setEnabled(True)
                    else:
                        # Servidor tem versão igual ou inferior. Iniciamos o local.
                        QMessageBox.information(self, "Pronto", "Tudo atualizado. Iniciando...")
                        self.close()
                else:
                    # Falha ao checar update, mas se já ativou, tenta fechar pra abrir o app
                    self.close()

            elif response.get("status") == "limit_reached":
                self.license_key = chave
                self.initial_response = response
                self.ui_mode = "replace_device"
                self.update_ui_for_mode()
                self.action_btn.setEnabled(True)
                self.show_replacement_dialog()
            else:
                msg = response.get("message", "Erro desconhecido")
                QMessageBox.critical(self, "Erro", f"Falha na ativação:\n{msg}")
                self.action_btn.setEnabled(True)
                self.action_btn.setText("ATIVAR LICENÇA")
        
        def show_replacement_dialog(self):
            if not self.initial_response: return
            dialog = DialogoDispositivos(self.initial_response.get("devices", []), self)
            if dialog.exec():
                old_id = dialog.selected_device_id
                if old_id:
                    self.handle_replacement(old_id) 

        def handle_replacement(self, old_device_id):
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Substituindo...")
            QApplication.processEvents()

            payload = { "license_key": self.license_key, "old_device_id": old_device_id,
                        "new_device_id": self.device_id, "new_hostname": get_hostname() }
            response = firebase_client.call_firebase_function("replace_device", payload)
            
            if response.get("status") == "success":
                self.config["license_key"] = self.license_key
                save_launcher_config(self.config)
                lease_manager.write_lease(response['real_expiry'], self.device_id)

                update_avail, latest_info = check_for_update_firebase("0.0.0")
                if latest_info:
                    self.update_info = latest_info
                    self.ui_mode = "install"
                    self.update_ui_for_mode()
                    self.action_btn.setEnabled(True)
                else:
                    QMessageBox.critical(self, "Erro Pós-Ativação", "Dispositivo substituído, mas não foi possível obter dados da versão.")
                    self.close()
            else:
                QMessageBox.critical(self, "Erro na Substituição", 
                                     f"Não foi possível substituir o dispositivo:\n\n{response.get('message')}")
                self.action_btn.setEnabled(True)
                self.action_btn.setText("GERENCIAR DISPOSITIVOS")

        def handle_install_update(self):
            self.action_btn.setEnabled(False)
            
            version_to_download = self.update_info.get("version")
            if not version_to_download:
                QMessageBox.critical(self, "Erro", "Versão de download não definida.")
                self.action_btn.setEnabled(True)
                return

            self.status_label.setText("Contatando servidor de download...")
            QApplication.processEvents()
            
            payload = {
                "license_key": self.license_key,
                "device_id": self.device_id,
                "file_version": version_to_download
            }
            response = firebase_client.call_firebase_function("get_download_url", payload)
            
            if response.get("status") != "success":
                QMessageBox.critical(self, "Erro de Download", 
                                     f"Não foi possível obter o link de download:\n\n{response.get('message')}")
                self.action_btn.setEnabled(True)
                return

            download_url = response.get("download_url")
            
            self.ui_mode = "downloading"
            self.update_ui_for_mode()
            
            self.download_thread = QThread()
            self.download_worker = DownloadWorker()
            self.download_worker.moveToThread(self.download_thread)

            self.download_worker.progress.connect(self.on_download_progress)
            self.download_worker.finished.connect(self.on_download_finished)
            
            self.thread_running = True 
            self.download_thread.started.connect(
                lambda: self.download_worker.run_download_and_unzip(
                    download_url, 
                    ROOT_DIR  # <--- Baixa para a raiz para sobrescrever o app_vX.bin
                )
            )
            self.download_thread.start()

        @Slot(int, int)
        def on_download_progress(self, current, total):
            if total > 0:
                percent = (current * 100) / total
                self.progress_bar.setValue(int(percent))
                self.status_label.setText(f"Baixando... ({int(percent)}%)")

        @Slot(bool, str)
        def on_download_finished(self, success, message):
            self.thread_running = False
            self.download_thread.quit()
            self.download_thread.wait()

            if success:
                self.status_label.setText("Concluído!")
                
                version_installed = self.update_info.get("version", "0.0.0")
                self.config["app_version"] = version_installed
                save_launcher_config(self.config)
                
                # A atualização baixou um novo app_core.bin
                # Precisamos extraí-lo novamente para atualizar a pasta segura
                print("[Launcher] Download concluído. Iniciando extração do update...")
                extraction_ok = ensure_core_is_ready()

                if extraction_ok:
                    self.launch_pending = True
                    self.close() 
                else:
                    QMessageBox.critical(self, "Erro de Extração", "O download terminou, mas falhou ao extrair o núcleo do sistema.")
            else:
                QMessageBox.critical(self, "Erro na Instalação", 
                                     f"A instalação falhou:\n\n{message}")
                
                self.ui_mode = "install" if self.config.get("app_version", "0.0.0") == "0.0.0" else "update"
                self.update_ui_for_mode()
                self.action_btn.setEnabled(True)

        def closeEvent(self, event):
            if hasattr(self, 'thread_running') and self.thread_running:
                QMessageBox.warning(self, "Download em Progresso", "Por favor, aguarde o fim do download.")
                event.ignore() 
            else:
                event.accept()
            
    # --- FIM DA CLASSE DA JANELA ---

    # 5. Inicia o aplicativo
    app = QApplication(sys.argv)
    
    initial_theme = "light" 
    if ui_mode != "activate" and ui_mode != "replace_device": 
        try:
            # Tenta ler a config do APP extraído, se existir
            # Ajuste de caminho para o LOCALAPPDATA
            sys.path.insert(0, EXTRACT_DIR) 
            import gerenciador_config
            config_app = gerenciador_config.carregar_config()
            initial_theme = config_app.get('ui_settings', {}).get('theme', 'light') 
            print(f"[Launcher] Tema do usuário detectado: {initial_theme}")
        except Exception as e:
            print(f"[Launcher] Não foi possível ler config do app: {e}. Usando tema padrão.")

    if HAS_THEME_LIB:
        try:
            qss = qdarktheme.load_stylesheet(initial_theme)
            try:
                import stylesheet_launcher 
                qss += stylesheet_launcher.get_style_sheet()
            except ImportError:
                pass 
            
            app.setStyleSheet(qss)
        except Exception as e:
            print(f"Não foi possível carregar o tema do launcher: {e}")

    is_mandatory_update = update_info and update_info.get("is_mandatory", False)

    window = LauncherWindow(
        is_dark_theme=(initial_theme == "dark"),
        ui_mode=ui_mode,
        update_info=update_info,
        initial_response=initial_response 
    )
    window.show()
    
    app.exec() 
    
    # 2. O código só chega aqui depois que a janela fechou.
    # Agora perguntamos para a janela (que ainda está na memória): 
    # "A operação foi um sucesso e devo lançar o app?"
    if window.launch_pending:
        print("[Launcher] Sucesso confirmado. Iniciando processo principal...")
        
        # Gera Token Novo (Para garantir que o timestamp seja atual)
        now_utc = datetime.now(timezone.utc).replace(microsecond=0)
        timestamp_str = now_utc.isoformat()
        token = hmac.new(DYNAMIC_SECRET_SALT, timestamp_str.encode('utf-8'), hashlib.sha256).hexdigest()
        
        env_dict = os.environ.copy()
        env_dict["FORMATHEUS_TOKEN"] = token
        env_dict["FORMATHEUS_TIMESTAMP"] = timestamp_str

        launch_command = get_app_launch_command()
        
        if launch_command:
            # close_fds=True é o SEGREDO. 
            # Ele diz ao Windows: "Não mate este novo processo se o processo pai (Launcher) morrer".
            subprocess.Popen(launch_command, env=env_dict, close_fds=True)
        else:
            print("[Launcher] Erro: Comando não encontrado.")
    
    else:
        print("[Launcher] Encerrado sem lançar (usuário fechou ou erro).")

    sys.exit(0)


if __name__ == "__main__":
    main()