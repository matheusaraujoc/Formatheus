# firebase_admin_manager.py

import firebase_admin
from firebase_admin import credentials, auth, firestore
import uuid
from datetime import datetime
import sys
import os
import requests  # Necessário para o login com senha
import json      # Necessário para o login com senha

def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando em dev e no PyInstaller """
    try:
        # PyInstaller cria uma pasta temporária e armazena o caminho em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Se não estiver compilado, usa o caminho normal do script
        # __file__ aqui se refere a 'firebase_admin_manager.py'
        base_path = os.path.abspath(os.path.dirname(__file__))

    return os.path.join(base_path, relative_path)


class FirebaseManager:
    """
    Gerencia a conexão e as operações do Firebase Admin SDK.
    """
    def __init__(self):
        try:
            # Tenta inicializar o app. Se já foi inicializado,
            # o get_app() evita o crash.
            firebase_admin.get_app()
        except ValueError:
            
            # Usa a função resource_path para procurar o .json
            # na mesma pasta deste script (admin_painel)
            cred_path = resource_path("admin_service_account.json")

            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
            except FileNotFoundError:
                print("="*50)
                print("ERRO CRÍTICO: 'admin_service_account.json' NÃO ENCONTRADO.")
                print(f"O script procurou em: {cred_path}")
                print("Por favor, baixe o arquivo da sua conta de serviço")
                print("do Firebase e coloque-o na pasta 'admin_painel'.")
                print("="*50)
                sys.exit(1) # Fecha o app
            except Exception as e:
                print(f"Erro desconhecido ao inicializar Firebase: {e}")
                sys.exit(1)

        self.db = firestore.client()

    def admin_login(self, email, password):
        """
        Verifica o email e a SENHA de um admin usando a API REST.
        """
        
        # Carrega a API Key do arquivo .json em vez de tê-la no código
        API_KEY = None
        try:
            api_config_path = resource_path("admin_api_config.json")
            with open(api_config_path, 'r') as f:
                API_KEY = json.load(f).get('apiKey')
        except FileNotFoundError:
            print("ERRO CRÍTICO: 'admin_api_config.json' NÃO ENCONTRADO.")
            return False, "Erro de configuração: Chave de API não encontrada."
        except Exception as e:
            print(f"Erro ao ler 'admin_api_config.json': {e}")
            return False, "Erro de configuração: Não foi possível ler a chave."

        if not API_KEY or "SUA_CHAVE" in API_KEY:
            print("ERRO: 'apiKey' não foi configurada no 'admin_api_config.json'")
            return False, "Erro de configuração do painel."

        rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={API_KEY}"
        
        payload = {
            "email": email,
            "password": password,
            "returnSecureToken": True
        }
        
        try:
            # Faz a requisição para a API de login
            response = requests.post(rest_api_url, data=json.dumps(payload), headers={"Content-Type": "application/json"})
            
            response_data = response.json()

            if not response.ok:
                # Se o Firebase retornar um erro (ex: "INVALID_PASSWORD")
                error_message = response_data.get("error", {}).get("message", "Erro desconhecido")
                print(f"Falha no login: {error_message}")
                if error_message == "INVALID_PASSWORD" or error_message == "EMAIL_NOT_FOUND":
                    return False, "E-mail ou senha inválidos."
                return False, "Erro ao tentar logar."

            # Login OK!
            # Agora, verificamos se esse usuário é um admin "real" no Admin SDK
            try:
                user = auth.get_user_by_email(email)
                print(f"Admin '{user.email}' autenticado com sucesso.")
                return True, "Login bem-sucedido."
            except auth.UserNotFoundError:
                return False, "Usuário autenticado não encontrado no Admin SDK."

        except requests.exceptions.RequestException as e:
            # Erro de rede, DNS, etc.
            print(f"Erro de conexão na API de login: {e}")
            return False, "Erro de rede. Verifique sua conexão."
        except Exception as e:
            print(f"Erro inesperado no login: {e}")
            return False, f"Erro inesperado: {e}"

    def get_all_plans(self):
        """Busca os planos (limite de máquinas) do Firestore."""
        try:
            plans_ref = self.db.collection("plans").stream()
            plans = []
            for plan in plans_ref:
                plan_data = plan.to_dict()
                plan_data['id'] = plan.id # Ex: 'annual', 'lifetime_3'
                plans.append(plan_data)
            return plans
        except Exception as e:
            print(f"Erro ao buscar planos: {e}")
            return [] # Retorna lista vazia em caso de erro

    def create_license(self, email: str, plan_id: str, expiration_date=None):
        """
        Cria uma nova licença no Firestore.
        AGORA INCLUI UMA DATA DE EXPIRAÇÃO OPCIONAL.
        """
        try:
            # 1. Gerar a chave (ex: FMT-A1B2C3D4-E5F6G7H8)
            key_parts = str(uuid.uuid4()).split('-')[:3]
            license_key = f"FMT-{key_parts[0]}-{key_parts[1]}-{key_parts[2]}".upper()

            # 2. Preparar os dados
            data = {
                "email": email,
                "plan_id": plan_id,
                "status": "active",
                "created_at": firestore.SERVER_TIMESTAMP,
                "active_devices": {} # Inicia vazio
            }
            
            # --- INÍCIO DA ADIÇÃO ---
            # Adiciona a data de expiração SOMENTE se ela for fornecida
            if expiration_date:
                # Converte o objeto 'date' do Python para um 'datetime' do Firebase
                data["expires_at"] = datetime(
                    expiration_date.year, 
                    expiration_date.month, 
                    expiration_date.day
                )
            # --- FIM DA ADIÇÃO ---

            # 3. Salvar no Firestore usando a chave como ID
            self.db.collection("licenses").document(license_key).set(data)
            
            return True, license_key
        
        except Exception as e:
            return False, f"Erro ao criar licença: {e}"

    def get_all_licenses(self):
        """Busca todas as licenças para exibir na tabela."""
        try:
            licenses_ref = self.db.collection("licenses").stream()
            licenses = []
            for lic in licenses_ref:
                lic_data = lic.to_dict()
                lic_data['key'] = lic.id # A própria chave
                licenses.append(lic_data)
            return licenses
        except Exception as e:
            print(f"Erro ao buscar licenças: {e}")
            return []

    def toggle_license_status(self, license_key: str, current_status: str):
        """Inverte o status de uma licença (active/inactive)."""
        try:
            new_status = "inactive" if current_status == "active" else "active"
            doc_ref = self.db.collection("licenses").document(license_key)
            doc_ref.update({"status": new_status})
            return True, f"Status alterado para {new_status}"
        except Exception as e:
            return False, f"Erro ao atualizar status: {e}"