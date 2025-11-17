# firebase_client.py
# Descrição: Um cliente HTTP dedicado para se comunicar com
# as Cloud Functions do Firebase. Este é o único arquivo
# no launcher do cliente que sabe os endereços do servidor.

import requests
import json

# --- COLOQUE AS URLs COMPLETAS DAS SUAS FUNÇÕES AQUI ---

# 1. Esta você já forneceu:
ACTIVATE_DEVICE_URL = "https://activate-device-6hk3tx32wa-uc.a.run.app"

# 2. Você precisa pegar esta URL no seu Console do Firebase (aba Functions):
REPLACE_DEVICE_URL = "https://replace-device-URL-DA-SUA-FUNCAO-AQUI.a.run.app" 

# ----------------------------------------------------


def call_firebase_function(function_name: str, data: dict):
    """
    Chama uma Cloud Function 'onCall' (Callable) usando a biblioteca requests.
    
    Args:
        function_name: O nome da função (ex: "activate_device").
        data: O payload (dicionário) a ser enviado.
    """
    
    url_map = {
        "activate_device": ACTIVATE_DEVICE_URL,
        "replace_device": REPLACE_DEVICE_URL
    }
    
    url = url_map.get(function_name)
    
    # Verifica se a URL foi configurada
    if not url or "URL-DA-SUA-FUNCAO-AQUI" in url:
        if function_name == "replace_device":
             print(f"ERRO: A URL da função '{function_name}' não foi configurada no 'firebase_client.py'.")
             return {"status": "error", "message": "Erro de configuração do cliente: URL de substituição não definida."}
        return {"status": "error", "message": f"URL da função '{function_name}' não encontrada no cliente."}

    # Funções 'onCall' esperam um payload JSON dentro de uma chave 'data'
    payload = {"data": data}
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        # Define um timeout (ex: 15 segundos)
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=15)
        
        # Verifica se a chamada foi bem-sucedida (ex: 200 OK)
        response.raise_for_status() 
        
        # Funções 'onCall' retornam o resultado dentro de uma chave 'result'
        response_json = response.json()
        if "result" in response_json:
            return response_json["result"] # Este é o nosso payload de sucesso (ex: {"status": "success", ...})
        else:
            # Se 'result' não estiver lá, algo deu errado
            return {"status": "error", "message": f"Resposta inesperada do servidor: {response_json}"}

    except requests.exceptions.HTTPError as http_err:
        # Erro de HTTP (ex: 404, 500)
        print(f"Erro HTTP: {http_err}")
        try:
            # Tenta pegar a mensagem de erro específica do Firebase
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