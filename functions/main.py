# functions/main.py
import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn
from datetime import datetime, timezone
import uuid
import os
import boto3
from packaging import version

# Importa o tipo Timestamp para checagem (embora o SDK geralmente o converta)
from google.protobuf.timestamp_pb2 import Timestamp

# Inicializa o Admin SDK (só é feito uma vez)
firebase_admin.initialize_app()

# Define uma data "fictícia" muito no futuro para planos vitalícios
LIFETIME_EXPIRY = datetime(2099, 12, 31, tzinfo=timezone.utc)

@https_fn.on_call()
def activate_device(req: https_fn.CallableRequest):
    """
    Função principal de ativação e verificação de licença.
    Recebe: { license_key: "...", device_id: "...", hostname: "..." }
    """
    
    data = req.data
    license_key = data.get("license_key")
    device_id = data.get("device_id")
    hostname = data.get("hostname", "Dispositivo Desconhecido")

    if not license_key or not device_id:
        raise https_fn.HttpsError(
            code="invalid-argument",
            message="A chave de licença e o ID do dispositivo são obrigatórios."
        )

    db = firestore.client()
    
    @firestore.transactional
    def update_license_in_transaction(transaction, lic_ref, plan_ref):
        
        lic_snapshot = lic_ref.get(transaction=transaction)
        if not lic_snapshot.exists:
            raise https_fn.HttpsError(code="not-found", message="Chave de licença inválida.")
        
        lic_data = lic_snapshot.to_dict()

        if lic_data.get("status") != "active":
            raise https_fn.HttpsError(code="permission-denied", message="Esta licença não está ativa.")

        expires_at_datetime = lic_data.get("expires_at") 

        if expires_at_datetime:
            hoje = datetime.now(timezone.utc)
            if expires_at_datetime < hoje:
                raise https_fn.HttpsError(code="permission-denied", message="Esta licença expirou.")
        
        if expires_at_datetime:
            real_expiry_date = expires_at_datetime
        else:
            real_expiry_date = LIFETIME_EXPIRY
            
        real_expiry_iso = real_expiry_date.isoformat()

        active_devices = lic_data.get("active_devices", {})
        if device_id in active_devices:
            update_path = f"active_devices.{device_id}.last_seen"
            transaction.update(lic_ref, {
                update_path: firestore.SERVER_TIMESTAMP
            })
            return {
                "status": "success", 
                "message": "Dispositivo já ativado.",
                "real_expiry": real_expiry_iso 
            }

        plan_id = lic_data.get("plan_id")
        if not plan_id:
            raise https_fn.HttpsError(code="internal", message="Licença inválida (sem plano).")
            
        plan_snapshot = plan_ref.document(plan_id).get(transaction=transaction)
        
        if not plan_snapshot.exists:
            raise https_fn.HttpsError(code="internal", message=f"Plano '{plan_id}' não encontrado.")
            
        plan_data = plan_snapshot.to_dict()
        limit = plan_data.get("machine_limit", 1)

        current_count = len(active_devices)
        
        if current_count < limit:
            # --- CENÁRIO A: Vaga disponível ---
            new_device_path = f"active_devices.{device_id}"
            transaction.update(lic_ref, {
                new_device_path: {
                    "hostname": hostname,
                    "activated_at": firestore.SERVER_TIMESTAMP,
                    "last_seen": firestore.SERVER_TIMESTAMP
                }
            })
            return {
                "status": "success", 
                "message": "Dispositivo ativado com sucesso.",
                "real_expiry": real_expiry_iso
            }
        else:
            # --- CENÁRIO B: Limite atingido ---
            device_list = []
            for dev_id, dev_data in active_devices.items():
                device_list.append({
                    "id": dev_id,
                    "hostname": dev_data.get("hostname", "Desconhecido")
                })
                
            return {
                "status": "limit_reached", 
                "message": "Limite de dispositivos atingido.",
                "devices": device_list
            }
    # --- Fim da Transação ---

    try:
        license_ref = db.collection("licenses").document(license_key)
        plans_collection_ref = db.collection("plans")
        
        # --- CORREÇÃO 1 APLICADA (Chamada transacional) ---
        # A função 'update_license_in_transaction' já está decorada,
        # então apenas a chamamos com a transação criada.
        transaction = db.transaction()
        result = update_license_in_transaction(
            transaction, 
            license_ref, 
            plans_collection_ref
        )
        # --- FIM DA CORREÇÃO 1 ---
        
        return result

    except https_fn.HttpsError as e:
        # Erros "esperados" (licença inválida, expirada, etc.)
        return {"status": "error", "message": e.message}
    except Exception as e:
        # Erros "inesperados" (problema no SDK, etc.)
        print(f"ERRO INESPERADO (activate_device): {e}")
        return {"status": "error", "message": "Ocorreu um erro interno no servidor."}


# --- CORREÇÃO 2 APLICADA (Função de ajuda transacional) ---
@firestore.transactional
def _replace_device_transactional(transaction, lic_ref, old_device_id, new_device_id, new_hostname):
    """Função interna que executa a substituição de forma atômica."""
    
    lic_doc = lic_ref.get(transaction=transaction)
    if not lic_doc.exists:
        raise https_fn.HttpsError(code="not-found", message="Chave de licença inválida.")
    
    lic_data = lic_doc.to_dict()
    active_devices = lic_data.get("active_devices", {})
    
    if old_device_id not in active_devices:
        raise https_fn.HttpsError(code="not-found", message="O dispositivo a ser removido não foi encontrado.")

    expires_at_datetime = lic_data.get("expires_at")
    real_expiry_date = expires_at_datetime if expires_at_datetime else LIFETIME_EXPIRY
    real_expiry_iso = real_expiry_date.isoformat()

    update_data = {
        f"active_devices.{new_device_id}": {
            "hostname": new_hostname,
            "activated_at": firestore.SERVER_TIMESTAMP,
            "last_seen": firestore.SERVER_TIMESTAMP
        },
        f"active_devices.{old_device_id}": firestore.DELETE_FIELD
    }
    
    transaction.update(lic_ref, update_data)
    
    return {
        "status": "success", 
        "message": "Dispositivo substituído com sucesso.",
        "real_expiry": real_expiry_iso
    }
# --- FIM DA CORREÇÃO 2 ---


@https_fn.on_call()
def replace_device(req: https_fn.CallableRequest):
    """
    Remove um dispositivo antigo e adiciona um novo (agora transacional).
    Recebe: { license_key: "...", old_device_id: "...", new_device_id: "...", new_hostname: "..." }
    """
    
    data = req.data
    license_key = data.get("license_key")
    old_device_id = data.get("old_device_id")
    new_device_id = data.get("new_device_id")
    new_hostname = data.get("new_hostname", "Dispositivo Desconhecido")

    if not all([license_key, old_device_id, new_device_id]):
        raise https_fn.HttpsError(
            code="invalid-argument",
            message="Faltam argumentos (chave, id_antigo, id_novo)."
        )

    db = firestore.client()
    lic_ref = db.collection("licenses").document(license_key)

    # --- CORREÇÃO 2 APLICADA (Chamada transacional) ---
    try:
        # Chama a função de ajuda transacional que criamos
        transaction = db.transaction()
        result = _replace_device_transactional(
            transaction,
            lic_ref,
            old_device_id,
            new_device_id,
            new_hostname
        )
        return result

    except https_fn.HttpsError as e:
        return {"status": "error", "message": e.message}
    except Exception as e:
        print(f"Erro inesperado em replace_device: {e}")
        return {"status": "error", "message": "Ocorreu um erro interno ao substituir o dispositivo."}
    # --- FIM DA CORREÇÃO 2 ---


# DOWNLOAD DE VERSÕES DO R2

@https_fn.on_call(
    secrets=["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"] # <-- Diz ao Firebase para carregar nossos segredos
)
def get_download_url(req: https_fn.CallableRequest):
    """
    Verifica a licença (novamente) e, se for válida, gera uma URL
    de download segura e temporária do Cloudflare R2.
    
    Recebe: { license_key: "...", device_id: "...", file_version: "1.0.0" }
    """
    
    # 1. PEGAR OS DADOS DA REQUISIÇÃO
    data = req.data
    license_key = data.get("license_key")
    device_id = data.get("device_id")
    file_version = data.get("file_version") # Versão que o cliente quer baixar

    if not all([license_key, device_id, file_version]):
        raise https_fn.HttpsError(
            code="invalid-argument",
            message="Chave, ID do dispositivo e versão do arquivo são obrigatórios."
        )

    db = firestore.client()
    lic_ref = db.collection("licenses").document(license_key)

    # 2. VERIFICAR A LICENÇA (VERIFICAÇÃO RÁPIDA)
    # (Não precisamos de uma transação completa aqui, apenas uma leitura)
    try:
        lic_doc = lic_ref.get()
        if not lic_doc.exists:
            raise https_fn.HttpsError(code="not-found", message="Chave de licença inválida.")
        
        lic_data = lic_doc.to_dict()
        
        if lic_data.get("status") != "active":
            raise https_fn.HttpsError(code="permission-denied", message="Esta licença não está ativa.")
        
        expires_at = lic_data.get("expires_at")
        if expires_at and expires_at < datetime.now(timezone.utc):
            raise https_fn.HttpsError(code="permission-denied", message="Esta licença expirou.")
            
        # Verifica se este dispositivo está realmente na licença
        if device_id not in lic_data.get("active_devices", {}):
            raise https_fn.HttpsError(code="permission-denied", message="Este dispositivo não está ativado para esta licença.")

    except https_fn.HttpsError as e:
        return {"status": "error", "message": e.message}
    except Exception as e:
        print(f"Erro ao verificar licença para download: {e}")
        return {"status": "error", "message": "Erro ao verificar licença."}

    # 3. GERAR A URL SEGURA DO R2
    try:
        # --- PREENCHA SEUS DADOS DO R2 AQUI ---
        # (Você encontra isso no painel do R2)
        R2_ENDPOINT_URL = "https://09ac22087797a74aa1e2fb28d354c5f8.r2.cloudflarestorage.com"
        R2_BUCKET_NAME = "formatheus-releases"
        # ----------------------------------------
        
        # Constrói o nome do arquivo de teste
        # (No futuro, você pode pegar isso do Firestore)
        file_name = f"app_v{file_version}.zip" 

        # Pega as chaves secretas que o Firebase injetou
        access_key_id = os.environ.get("R2_ACCESS_KEY_ID")
        secret_access_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        
        if not all([access_key_id, secret_access_key, R2_ENDPOINT_URL, R2_BUCKET_NAME]):
            raise https_fn.HttpsError(code="internal", message="Configuração do servidor de download incompleta.")

        # Inicializa o cliente Boto3 (o "telefone" para o R2)
        s3_client = boto3.client(
            's3',
            endpoint_url=R2_ENDPOINT_URL,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto" # R2 usa 'auto'
        )

        # Gera a URL assinada (link temporário)
        # Válido por 300 segundos (5 minutos)
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': R2_BUCKET_NAME, 'Key': file_name},
            ExpiresIn=300 
        )

        # 4. ENVIA A URL DE VOLTA PARA O LAUNCHER
        return {
            "status": "success",
            "download_url": presigned_url,
            "file_name": file_name
        }

    except Exception as e:
        print(f"Erro ao gerar URL do R2: {e}")
        # (Se o erro for 'ClientError: Not Found', o arquivo .zip não existe no bucket)
        if "Not Found" in str(e):
             return {"status": "error", "message": f"A versão do arquivo '{file_version}' não foi encontrada no servidor."}
        
        return {"status": "error", "message": "Não foi possível obter o link de download."}
    

@https_fn.on_call()
def check_for_update(req: https_fn.CallableRequest):
    """
    Verifica a versão mais recente no Firestore e compara com a do cliente.
    
    Recebe: { "current_version": "1.0.0" }
    Retorna: { "status": "...", "latest_info": { ... } }
    """
    
    data = req.data
    current_version_str = data.get("current_version", "0.0.0")
    
    try:
        db = firestore.client()
        
        # 1. Pega o documento 'latest_release' que você criou no Firestore
        release_ref = db.collection("app_meta").document("latest_release")
        release_doc = release_ref.get()
        
        if not release_doc.exists:
            raise https_fn.HttpsError(code="not-found", message="Documento de 'latest_release' não encontrado.")
            
        latest_info = release_doc.to_dict()
        # latest_info agora é algo como:
        # { "version": "1.0.1", "release_notes": "...", "is_mandatory": false }
        
        latest_version_str = latest_info.get("version", "0.0.0")

        # 2. Compara as versões usando a biblioteca 'packaging'
        # Ela entende que "1.0.1" > "1.0.0" e "1.10.0" > "1.9.0"
        update_available = version.parse(latest_version_str) > version.parse(current_version_str)
        
        return {
            "status": "success",
            "update_available": update_available,
            "latest_info": latest_info 
        }

    except Exception as e:
        print(f"Erro ao checar atualização: {e}")
        return {"status": "error", "message": str(e)}