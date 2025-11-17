# laucher.py
# v2.0 - Implementado sistema de licença offline ("lease")
# e fluxo de ativação online.

import sys
import os
import subprocess
import json
import zipfile
import shutil
import tempfile
from datetime import datetime
import uuid # <-- Adicionado para gerar o Device ID
import platform # <-- Adicionado para pegar o hostname

# --- Importações do Projeto ---
try:
    import firebase_client
    import lease_manager
except ImportError as e:
    print(f"ERRO CRÍTICO: Não foi possível importar os módulos de licença: {e}")
    print("Certifique-se que 'firebase_client.py' e 'lease_manager.py' estão na mesma pasta.")
    sys.exit(1)
# -----------------------------

#IDENTIFICA SE ESTÁ RODANDO NO PYINSTALLER
def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando em dev e no PyInstaller """
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

# --- 2. Definições Globais ---
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(ROOT_DIR, "app")
# Este config agora armazena device_id, license_key e app_version
LAUNCHER_CONFIG_FILE = resource_path("launcher_config.json") 
CONTROLLER_EXE = os.path.join(ROOT_DIR, "controller.exe")
UPDATE_JSON_URL = "https://api.github.com/repos/SEU_USUARIO/SEU_REPOSITORIO/releases/latest" 

# --- 3. Função de Carregamento da UI ---
def carregar_modulos_ui():
    """
    Importa PySide6 e qdarktheme APENAS quando a UI é necessária.
    """
    try:
        from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, 
                                       QPushButton, QLabel, QMessageBox,
                                       QLineEdit, QDialog, QListWidget, 
                                       QDialogButtonBox, QListWidgetItem) 
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
            QListWidget, QDialogButtonBox, QListWidgetItem, QFont, QDate)


# --- 4. Funções de Configuração e Verificação ---

def get_launcher_config():
    """Lê o config completo do launcher (device_id, license_key, etc)."""
    if not os.path.exists(LAUNCHER_CONFIG_FILE):
        return {} # Vazio se não existir
    try:
        with open(LAUNCHER_CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return {} # Vazio se corrompido

def save_launcher_config(config_data):
    """Salva o config completo do launcher."""
    try:
        with open(LAUNCHER_CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
    except Exception as e:
        print(f"[Launcher] Erro ao salvar config: {e}")

def get_or_create_device_id(config):
    """
    Lê o device_id do config. Se não existir, cria um, salva e retorna.
    """
    if "device_id" in config and config["device_id"]:
        return config["device_id"]
        
    # Não existe, vamos criar um
    device_id = str(uuid.uuid4())
    config["device_id"] = device_id
    save_launcher_config(config)
    print(f"[Launcher] Novo Device ID gerado: {device_id}")
    return device_id

def get_local_license_key(config):
    """Lê a license_key do config, se existir."""
    return config.get("license_key")

def get_hostname():
    """Pega o nome da máquina do usuário (para o log de dispositivos)."""
    return platform.node()

def check_for_update(app_version: str):
    """
    Verifica o servidor por atualizações.
    Retorna (update_info, is_first_run)
    """
    is_first_run = (app_version == "0.0.0")
    
    if not HAS_REQUESTS:
        print("[Launcher] Biblioteca 'requests' não encontrada. Pulando verificação.")
        return None, is_first_run

    try:
        response = requests.get(UPDATE_JSON_URL, timeout=5)
        response.raise_for_status()
        latest_release = response.json()
        
        server_version = latest_release.get("tag_name", "0.0.0").replace("v", "")
        local_version = app_version

        # (Lógica de comparação de versão simples)
        if server_version > local_version:
            print(f"[Launcher] Atualização do APP encontrada: {local_version} -> {server_version}")
            update_info = {
                "version": server_version,
                "url": latest_release.get("assets", [{}])[0].get("browser_download_url"),
                "type": "app", # (Assumindo que o launcher só atualiza o app)
                "mandatory": latest_release.get("mandatory", False)
            }
            return update_info, is_first_run
        else:
            print("[Launcher] Nenhuma atualização do APP encontrada.")
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
    
    # --- FASE 1: Verificação de Licença (Offline e Online) ---
    
    print("[Launcher] Iniciando...")
    launcher_config = get_launcher_config()
    device_id = get_or_create_device_id(launcher_config)
    
    # Variáveis de estado
    is_activated = False       # A licença é válida?
    ui_mode = "activate"       # O que a UI deve mostrar? (activate, install, update, replace_device)
    initial_response = None    # Resposta do servidor (para 'limit_reached')
    error_message = ""         # Mensagem de erro fatal
    
    # Tenta ler o lease (ingresso) offline
    lease_data = lease_manager.read_lease(device_id)

    if lease_data:
        # --- CENÁRIO B: Lease Encontrado (Verificação Offline) ---
        print("[Launcher] Lease local encontrado. Verificando validade...")
        lease_status, message = lease_manager.check_lease_validity(lease_data)
        
        if lease_status == "ok":
            # SUCESSO OFFLINE!
            print("[Launcher] Lease offline VÁLIDO.")
            is_activated = True
            ui_mode = "update" # Próximo passo: checar atualizações
            
        elif lease_status == "expired":
            # Licença expirou permanentemente
            print(f"[Launcher] Lease expirado. {message}")
            is_activated = False
            ui_mode = "show_error"
            error_message = f"Sua licença expirou em {lease_data.get('real_expiry')}.\nPor favor, renove seu plano para continuar."
            
        elif lease_status == "stale":
            # Lease de 7 dias venceu. Precisa verificar online
            print("[Launcher] Lease offline venceu. Verificação online necessária.")
            ui_mode = "verify_online"

    else:
        # --- CENÁRIO A/C: Lease NÃO Encontrado ---
        print("[Launcher] Nenhum lease local encontrado.")
        license_key = get_local_license_key(launcher_config)
        
        if license_key:
            # Lease foi apagado, mas temos a chave. Força verificação online.
            print("[Launcher] Chave local encontrada. Verificação online necessária.")
            ui_mode = "verify_online"
        else:
            # Primeira vez do usuário. Força ativação.
            print("[Launcher] Nenhuma chave local. Aguardando ativação do usuário.")
            ui_mode = "activate"

    # --- FASE 2: Verificação Online (Se necessário) ---
    
    if ui_mode == "verify_online":
        print("[Launcher] Contatando servidor de licenças...")
        license_key = get_local_license_key(launcher_config)
        
        if not license_key: 
             ui_mode = "activate"
        else:
            payload = {
                "license_key": license_key,
                "device_id": device_id,
                "hostname": get_hostname()
            }
            response = firebase_client.call_firebase_function("activate_device", payload)
            status = response.get("status")

            if status == "success":
                print("[Launcher] Verificação online OK.")
                lease_manager.write_lease(response['real_expiry'], device_id)
                is_activated = True
                ui_mode = "update" 
            
            elif status == "limit_reached":
                print("[Launcher] Limite de dispositivos atingido.")
                is_activated = False
                ui_mode = "replace_device" 
                initial_response = response 
            
            else:
                print(f"[Launcher] Falha na verificação da licença: {response.get('message')}")
                is_activated = False
                ui_mode = "show_error"
                error_message = f"Sua licença não pôde ser validada:\n\n{response.get('message')}"

    # --- FASE 3: Verificação de Atualização (Apenas se ativado) ---
    
    update_info = None
    is_first_run = False
    app_version = launcher_config.get("app_version", "0.0.0")

    if ui_mode == "update":
        print("[Launcher] Verificando atualizações do app...")
        update_info, is_first_run = check_for_update(app_version)
        
        if not update_info and not is_first_run:
            print("[Launcher] Licença OK. Nenhuma atualização. Iniciando main_app...")
            launch_command = get_app_launch_command()
            if launch_command:
                subprocess.Popen(launch_command)
            else:
                ui_mode = "install" 
                is_first_run = True
            
            if ui_mode == "update": 
                sys.exit(0) 

    # --- INÍCIO DA CORREÇÃO ---
    # Define a variável 'is_mandatory_update' AQUI
    # (Após 'update_info' ter sido definido)
    is_mandatory_update = update_info and update_info.get("mandatory", False)
    # --- FIM DA CORREÇÃO ---
    
    # --- FASE 4: Carregar a UI (Se necessário) ---
    
    print(f"[Launcher] Ação de UI necessária: {ui_mode}")

    # 1. Carrega os módulos pesados (PySide6)
    (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, 
     QMessageBox, QIcon, QPixmap, Qt, Slot, QObject, QThread, 
     Signal, HAS_THEME_LIB, qdarktheme, QLineEdit, QDialog, 
     QListWidget, QDialogButtonBox, QListWidgetItem, QFont, QDate) = carregar_modulos_ui()

    # 2. Se o modo for apenas mostrar um erro fatal, faça isso e saia.
    if ui_mode == "show_error":
        temp_app = QApplication(sys.argv)
        QMessageBox.critical(None, "Erro de Licença", error_message)
        sys.exit(1) # Fecha o app
        
    
    # 3. Define as classes de UI que dependem dos módulos
    
    class DialogoDispositivos(QDialog):
        """Pop-up para o usuário substituir um dispositivo."""
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
    

    class LauncherWindow(QWidget):
        """A UI principal do Launcher (Ativação, Instalação, Update)"""
        
        def __init__(self, is_dark_theme=False, ui_mode="activate", 
                     update_info=None, is_first_run=False, initial_response=None):
            super().__init__()
            
            self.is_dark = is_dark_theme
            self.ui_mode = ui_mode 
            self.update_info = update_info
            self.is_first_run = is_first_run
            self.initial_response = initial_response 
            
            self.config = get_launcher_config()
            self.device_id = self.config.get("device_id")
            self.license_key = self.config.get("license_key")
            
            self.setWindowTitle("Formatheus Launcher")

            try:
                icon_path = resource_path(os.path.join("launcher_assets", "icons", "formatheus.ico"))
                self.setWindowIcon(QIcon(icon_path)) 
            except Exception as e:
                print(f"Aviso: Ícone de admin não encontrado: {e}")
                self.setWindowIcon(QIcon()) 
            
            self.setFixedSize(400, 350)
            self._build_ui()
            
            if self.ui_mode == "replace_device":
                self.show_replacement_dialog() 

        def _build_ui(self):
            # Limpa a UI antiga, se houver
            layout = self.layout()
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    widget = item.widget()
                    if widget is not None:
                        widget.deleteLater()
            else:
                layout = QVBoxLayout(self)
            
            title_label = QLabel("Formatheus")
            font = QFont("Segoe UI", 24)
            font.setBold(True)
            title_label.setFont(font)
            title_label.setAlignment(Qt.AlignCenter)

            self.status_label = QLabel("")
            self.status_label.setAlignment(Qt.AlignCenter)
            
            self.key_input = QLineEdit()
            self.key_input.setPlaceholderText("Cole sua chave de licença (FMT-...)")
            self.key_input.setAlignment(Qt.AlignCenter)
            
            self.action_btn = QPushButton("")
            self.action_btn.setMinimumHeight(45)
            self.action_btn.setProperty("cssClass", "primary") 
            
            try:
                self.action_btn.clicked.disconnect()
            except RuntimeError:
                pass 
            self.action_btn.clicked.connect(self.on_action_clicked)
            
            # Lógica de exibição
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

            elif self.is_first_run or self.ui_mode == "install":
                self.status_label.setText("Bem-vindo! O Formatheus precisa ser instalado.")
                self.action_btn.setText("INSTALAR")
                self.key_input.setVisible(False) 
            
            elif self.update_info:
                versao = self.update_info.get("version", "nova")
                self.status_label.setText(f"Uma nova versão ({versao}) está disponível.")
                self.action_btn.setText(f"ATUALIZAR AGORA")
                self.key_input.setVisible(False)

            layout.addStretch()
            layout.addWidget(title_label)
            layout.addSpacing(20)
            layout.addWidget(self.status_label)
            layout.addSpacing(10)
            layout.addWidget(self.key_input)
            layout.addSpacing(20)
            layout.addWidget(self.action_btn)
            layout.addStretch()

        @Slot()
        def on_action_clicked(self):
            """Lida com o clique no botão (Ativar, Instalar ou Atualizar)."""
            
            if self.ui_mode == "activate":
                self.handle_activation()
            elif self.ui_mode == "replace_device":
                self.show_replacement_dialog()
            elif self.is_first_run or self.ui_mode == "install" or self.update_info:
                self.handle_install_update()
            else:
                self.close() 

        def handle_activation(self):
            """Chama a Cloud Function 'activate_device'."""
            chave = self.key_input.text().strip().upper()
            if not chave:
                QMessageBox.warning(self, "Erro", "Por favor, insira uma chave de licença.")
                return

            self.action_btn.setEnabled(False)
            self.action_btn.setText("Ativando...")
            QApplication.processEvents()
            
            payload = {
                "license_key": chave,
                "device_id": self.device_id,
                "hostname": get_hostname()
            }
            response = firebase_client.call_firebase_function("activate_device", payload)
            status = response.get("status")

            if status == "success":
                QMessageBox.information(self, "Sucesso", "Licença ativada! O programa será baixado agora.")
                self.config["license_key"] = chave
                save_launcher_config(self.config)
                lease_manager.write_lease(response['real_expiry'], self.device_id)
                
                self.is_activated = True
                self.is_first_run = True 
                self.ui_mode = "install" 
                self._build_ui() 
                self.action_btn.setEnabled(True)

            elif status == "limit_reached":
                self.license_key = chave 
                self.initial_response = response 
                self.ui_mode = "replace_device"
                self._build_ui() 
                self.action_btn.setEnabled(True)
                self.show_replacement_dialog() 
            
            else:
                QMessageBox.critical(self, "Erro de Ativação", 
                                     f"Não foi possível ativar sua licença:\n\n{response.get('message')}")
                self.action_btn.setEnabled(True)
                self.action_btn.setText("ATIVAR LICENÇA")
        
        def show_replacement_dialog(self):
            """Mostra o pop-up para substituir dispositivo."""
            if not self.initial_response: return
            dialog = DialogoDispositivos(self.initial_response.get("devices", []), self)
            if dialog.exec():
                old_id = dialog.selected_device_id
                if old_id:
                    self.handle_replacement(old_id) 

        def handle_replacement(self, old_device_id):
            """Chama a Cloud Function 'replace_device'."""
            self.action_btn.setEnabled(False)
            self.action_btn.setText("Substituindo...")
            QApplication.processEvents()

            payload = {
                "license_key": self.license_key, 
                "old_device_id": old_device_id,
                "new_device_id": self.device_id,
                "new_hostname": get_hostname()
            }
            response = firebase_client.call_firebase_function("replace_device", payload)
            
            if response.get("status") == "success":
                QMessageBox.information(self, "Sucesso", "Dispositivo substituído! O programa será baixado agora.")
                self.config["license_key"] = self.license_key
                save_launcher_config(self.config)
                lease_manager.write_lease(response['real_expiry'], self.device_id)

                self.is_activated = True
                self.is_first_run = True
                self.ui_mode = "install"
                self._build_ui() 
                self.action_btn.setEnabled(True)
            else:
                QMessageBox.critical(self, "Erro na Substituição", 
                                     f"Não foi possível substituir o dispositivo:\n\n{response.get('message')}")
                self.action_btn.setEnabled(True)
                self.action_btn.setText("GERENCIAR DISPOSITIVOS")

        def handle_install_update(self):
            """Lida com o clique no botão (Instalar ou Atualizar)."""
            self.action_btn.setEnabled(False)
            
            if self.is_first_run or self.ui_mode == "install":
                self.status_label.setText("Instalando...")
            else:
                self.status_label.setText("Atualizando...")
                
            QApplication.processEvents()
            
            print("[Launcher] (Simulação) Baixando e instalando...")
            # TODO: Adicionar a lógica de download e unzip real aqui
            
            if self.update_info:
                self.config["app_version"] = self.update_info.get("version", "1.0.0")
            else:
                self.config["app_version"] = "1.0.0" 
            
            save_launcher_config(self.config)
                
            self.status_label.setText("Concluído!")
            self.close() 
            
    # --- FIM DA CLASSE DA JANELA ---


    # 5. Inicia o aplicativo
    app = QApplication(sys.argv)
    
    # Tenta ler o tema do usuário
    initial_theme = "light" 
    if ui_mode != "activate" and ui_mode != "replace_device" and not is_first_run: 
        try:
            sys.path.insert(0, APP_DIR)
            import gerenciador_config
            config_app = gerenciador_config.carregar_config()
            initial_theme = config_app.get('ui_settings', {}).get('theme', 'light') 
            print(f"[Launcher] Tema do usuário detectado: {initial_theme}")
        except Exception as e:
            print(f"[Launcher] Não foi possível ler config do app: {e}. Usando tema padrão.")

    # Aplica o tema
    if HAS_THEME_LIB:
        try:
            qss = qdarktheme.load_stylesheet(initial_theme)
            if ui_mode != "activate" and not is_first_run:
                try:
                    import stylesheet
                    qss += stylesheet.get_style_sheet()
                except ImportError:
                    pass 
            app.setStyleSheet(qss)
        except Exception as e:
            print(f"Não foi possível carregar o tema do launcher: {e}")

    app_version = launcher_config.get("app_version", "0.0.0")
    is_first_run_real = (app_version == "0.0.0")
    
    if ui_mode == "install":
        is_first_run_real = True
    
    window = LauncherWindow(
        is_dark_theme=(initial_theme == "dark"),
        ui_mode=ui_mode,
        update_info=update_info,
        is_first_run=is_first_run_real,
        initial_response=initial_response 
    )
    window.show()
    
    app_exit_code = app.exec() 
    
    final_config = get_launcher_config()
    final_license_key = final_config.get("license_key")
    final_app_version = final_config.get("app_version") 

    # --- CORREÇÃO NO IF FINAL ---
    # Esta linha agora usa a variável 'is_mandatory_update'
    # que foi definida corretamente na FASE 3
    if (not window.isVisible()) and final_license_key and final_app_version:
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