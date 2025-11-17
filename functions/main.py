# functions/main.py
import firebase_admin
from firebase_admin import firestore
from firebase_functions import https_fn
from datetime import datetime, timezone
import uuid

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