# firebase_client.py
import requests
import json

# --- COLOQUE AS URLs COMPLETAS DAS SUAS FUNÇÕES AQUI ---

# 1. Esta você já forneceu:
ACTIVATE_DEVICE_URL = "https://activate-device-6hk3tx32wa-uc.a.run.app"

# 2. COLE A URL DA SUA FUNÇÃO 'replace_device' AQUI:
REPLACE_DEVICE_URL = "hhttps://replace-device-6hk3tx32wa-uc.a.run.app" 

# 3. (NOVO) URL da função de download
# (Eu deduzi esta URL. Se for diferente, ajuste)
GET_DOWNLOAD_URL = "https://get-download-url-6hk3tx32wa-uc.a.run.app"



# ----------------------------------------------------

# 1. Esta você já forneceu:
#ACTIVATE_DEVICE_URL = "https://activate-device-6hk3tx32wa-uc.a.run.app"

# 2. Você precisa pegar esta URL no seu Console do Firebase (aba Functions):
#REPLACE_DEVICE_URL = "https://replace-device-6hk3tx32wa-uc.a.run.app" 

# ----------------------------------------------------


def call_firebase_function(function_name: str, data: dict):
    """
    Chama uma Cloud Function 'onCall' (Callable) usando a biblioteca requests.
    """
    
    url_map = {
        "activate_device": ACTIVATE_DEVICE_URL,
        "replace_device": REPLACE_DEVICE_URL,
        "get_download_url": GET_DOWNLOAD_URL  # <-- ADICIONADO
    }
    
    url = url_map.get(function_name)
    
    if not url or "URL-DA-SUA-FUNCAO-AQUI" in url:
        print(f"ERRO: A URL da função '{function_name}' não foi configurada no 'firebase_client.py'.")
        return {"status": "error", "message": f"Erro de configuração do cliente: URL da função '{function_name}' não definida."}

    # Funções 'onCall' esperam um payload JSON dentro de uma chave 'data'
    payload = {"data": data}
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        response.raise_for_status() 
        
        response_json = response.json()
        if "result" in response_json:
            return response_json["result"] 
        else:
            return {"status": "error", "message": f"Resposta inesperada do servidor: {response_json}"}

    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP: {http_err}")
        try:
            error_data = http_err.response.json().get("error", {})
            message = error_data.get("message", str(http_err))
            return {"status": "error", "message": message}
        except:
             return {"status": "error", "message": str(http_err)}
             
    except requests.exceptions.ConnectionError as conn_err:
        print(f"Erro de Conexão: {conn_err}")
        return {"status": "error", "message": "Erro de conexão. Verifique sua internet."}
        
    except requests.exceptions.Timeout as timeout_err:
        print(f"Erro de Timeout: {timeout_err}")
        return {"status": "error", "message": "O servidor demorou para responder. Tente novamente."}
        
    except Exception as e:
        print(f"Erro inesperado no cliente: {e}")
        return {"status": "error", "message": f"Erro inesperado: {e}"}