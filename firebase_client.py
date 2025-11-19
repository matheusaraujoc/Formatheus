# firebase_client.py
import requests
import json

# --- CONFIGURAÇÃO DE URLS DAS CLOUD FUNCTIONS (Cloud Run) ---
# Se a sua URL base for diferente, ajuste a parte 'uc.a.run.app'
FUNCTION_URLS = {
    # URLs de Transação/Licença
    "activate_device": "https://activate-device-6hk3tx32wa-uc.a.run.app",
    
    "replace_device": "https://replace-device-6hk3tx32wa-uc.a.run.app", # <-- 'hhttps' CORRIGIDO
    
    # URL de Download
    "get_download_url": "https://get-download-url-6hk3tx32wa-uc.a.run.app",
    
    # URL de Controle de Versão (Função NOVA)
    "check_for_update": "https://check-for-update-6hk3tx32wa-uc.a.run.app" 
}
# -----------------------------------------------------------


def call_firebase_function(function_name: str, data: dict):
    """
    Chama uma Cloud Function 'onCall' (Callable) usando a biblioteca requests.
    """
    
    url = FUNCTION_URLS.get(function_name)
    
    if not url:
        print(f"ERRO: A URL da função '{function_name}' não foi configurada no 'firebase_client.py'.")
        return {"status": "error", "message": f"Erro de configuração do cliente: URL da função '{function_name}' não definida."}

    # Funções 'onCall' esperam um payload JSON dentro de uma chave 'data'
    payload = {"data": data}
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    try:
        # Serializa o payload para JSON e envia
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        response.raise_for_status() 
        
        response_json = response.json()
        
        # O Firebase 'onCall' sempre retorna a resposta dentro da chave 'result'
        if "result" in response_json:
            return response_json["result"] 
        else:
            # Resposta JSON inesperada (pode ser o formato de erro do Google Cloud)
            return {"status": "error", "message": f"Resposta inesperada do servidor: {response_json}"}

    except requests.exceptions.HTTPError as http_err:
        print(f"Erro HTTP: {http_err}")
        try:
            # Tenta extrair a mensagem de erro detalhada do Firebase/GCP
            error_data = http_err.response.json().get("error", {})
            message = error_data.get("message", str(http_err))
            return {"status": "error", "message": message}
        except:
            # Se a resposta não for JSON, retorna o erro HTTP genérico
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