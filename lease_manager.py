# lease_manager.py
# Descrição: Gerencia a criação, leitura e validação 
# do arquivo de "lease" offline (license.lease).

import json
import os
import sys
from datetime import datetime, timezone, timedelta, date

# --- Importações de Criptografia ---
# (Requer 'pip install pycryptodomex')
try:
    from Crypto.Cipher import AES
    from Crypto.Protocol.KDF import PBKDF2
    from Crypto.Util.Padding import pad, unpad
    from Crypto.Hash import SHA256
    from Crypto.Random import get_random_bytes
except ImportError:
    print("ERRO CRÍTICO: Biblioteca 'pycryptodomex' não encontrada.")
    print("Execute: pip install pycryptodomex")
    sys.exit(1)
# -----------------------------------

# (Copiado do laucher.py)
def resource_path(relative_path):
    """ Retorna o caminho absoluto para o recurso, funcionando em dev e no PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

# --- Constantes ---
LEASE_FILE_NAME = resource_path("license.lease")
LEASE_DURATION_DAYS = 7 # O "lease" offline expira após 7 dias

# IMPORTANTE: Esta é a "pimenta" (segredo) do app.
# Mude para qualquer string aleatória e complexa.
# Ela é compilada no .exe e impede que um 'lease' seja copiado para outra máquina.
PEPPER = b'63YAFUVEWRW4NCR3DF5E4OST3R53Q2' 

# --- Funções de Criptografia ---

def _generate_key(device_id: str, salt: bytes) -> bytes:
    """Gera uma chave de criptografia segura baseada no ID do dispositivo e no Pepper."""
    password = (device_id + PEPPER.decode('utf-8')).encode('utf-8')
    # PBKDF2 é usado para "esticar" a senha e torná-la uma chave forte
    key = PBKDF2(password, salt, dkLen=32, count=100000, hmac_hash_module=SHA256)
    return key

def write_lease(real_expiry_iso: str, device_id: str):
    """
    Cria ou sobrescreve o arquivo license.lease com as datas criptografadas.
    """
    try:
        data = {
            # Data de hoje (para o lease)
            "last_check": datetime.now(timezone.utc).date().isoformat(),
            # Data de expiração real (vinda do servidor)
            "real_expiry": datetime.fromisoformat(real_expiry_iso).date().isoformat()
        }
        
        data_bytes = json.dumps(data).encode('utf-8')
        
        # Gera um 'salt' aleatório. O salt é salvo junto com os dados.
        salt = get_random_bytes(16)
        key = _generate_key(device_id, salt)
        
        cipher = AES.new(key, AES.MODE_CBC)
        # Criptografa os dados
        ct_bytes = cipher.encrypt(pad(data_bytes, AES.block_size))
        
        # Salva tudo no arquivo: salt + iv + dados_criptografados
        with open(LEASE_FILE_NAME, 'wb') as f:
            f.write(salt)
            f.write(cipher.iv)
            f.write(ct_bytes)
            
        print("[LeaseManager] Lease escrito com sucesso.")
        return True
        
    except Exception as e:
        print(f"[LeaseManager] ERRO ao escrever lease: {e}")
        return False

def read_lease(device_id: str):
    """
    Lê, descriptografa e retorna os dados do license.lease.
    Retorna None se o arquivo não existir ou a descriptografia falhar.
    """
    if not os.path.exists(LEASE_FILE_NAME):
        return None # Arquivo não existe

    try:
        with open(LEASE_FILE_NAME, 'rb') as f:
            # Lê os componentes do arquivo
            salt = f.read(16)
            iv = f.read(16)
            ct_bytes = f.read()

        # Recria a mesma chave
        key = _generate_key(device_id, salt)
        
        cipher = AES.new(key, AES.MODE_CBC, iv=iv)
        # Descriptografa e remove o padding
        pt_bytes = unpad(cipher.decrypt(ct_bytes), AES.block_size)
        
        data = json.loads(pt_bytes.decode('utf-8'))
        print("[LeaseManager] Lease lido e descriptografado com sucesso.")
        return data
        
    except (ValueError, KeyError, FileNotFoundError):
        print("[LeaseManager] Lease corrompido ou inválido (ex: device_id mudou).")
        return None # Erro na descriptografia (chave errada, arquivo corrompido)
    except Exception as e:
        print(f"[LeaseManager] ERRO ao ler lease: {e}")
        return None

def check_lease_validity(lease_data: dict):
    """
    Verifica as datas do lease (offline) e decide o que fazer.
    
    Retorna:
    - ("ok", "...") -> Válido, pode abrir o app.
    - ("expired", "...") -> Licença expirou permanentemente.
    - ("stale", "...") -> Lease offline venceu, precisa de verificação online.
    """
    try:
        hoje = datetime.now(timezone.utc).date()
        
        # Converte as datas (string) de volta para objetos 'date'
        last_check_date = date.fromisoformat(lease_data["last_check"])
        real_expiry_date = date.fromisoformat(lease_data["real_expiry"])

        # Verificação 1: A licença REAL expirou?
        if hoje > real_expiry_date:
            return ("expired", f"Sua licença expirou em {real_expiry_date.strftime('%d/%m/%Y')}.")

        # Verificação 2: O "lease" (ingresso) offline ainda é válido?
        lease_expiry_date = last_check_date + timedelta(days=LEASE_DURATION_DAYS)
        
        if hoje <= lease_expiry_date:
            # SUCESSO! Ainda está dentro do período de 7 dias.
            dias_restantes_lease = (lease_expiry_date - hoje).days
            print(f"[LeaseManager] Verificação offline OK. {dias_restantes_lease} dias restantes no lease.")
            return ("ok", "Lease offline válido.")
        
        # Verificação 3: O lease expirou, precisa renovar
        print("[LeaseManager] Lease offline expirou. Verificação online necessária.")
        return ("stale", "Lease offline expirado, necessária verificação online.")

    except Exception as e:
        print(f"[LeaseManager] ERRO ao validar datas do lease: {e}")
        return ("stale", "Lease corrompido, necessária verificação online.")