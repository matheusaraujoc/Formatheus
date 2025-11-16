import sys
import os
import json

ADMIN_CONFIG_FILE = 'admin_app_config.json'

def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando em dev e no PyInstaller """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Se não estiver compilado, usa o caminho normal do script
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)

def load_admin_config():
    """Lê o e-mail e o estado do checkbox do config local."""
    try:
        with open(ADMIN_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            return config.get('admin_email', ''), config.get('remember_me', False)
    except (FileNotFoundError, json.JSONDecodeError):
        return "", False # Retorna padrões se o arquivo não existir ou estiver corrompido

def save_admin_config(email, remember):
    """Salva o e-mail e o estado do checkbox no config local."""
    config = {
        'admin_email': email if remember else '',
        'remember_me': remember
    }
    try:
        with open(ADMIN_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Erro ao salvar config do admin: {e}")