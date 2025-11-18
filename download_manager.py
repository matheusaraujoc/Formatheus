# download_manager.py
# Descrição: Lida com o download e descompactação do app 
# em uma thread separada para não travar a UI.

import requests
import zipfile
import os
import shutil

# (Importa os módulos do PySide6)
# (O laucher.py garantirá que eles existam antes de usar esta classe)
try:
    from PySide6.QtCore import QObject, Signal, Slot
except ImportError:
    # Define classes "falsas" se o PySide6 não estiver disponível
    # (Isso permite que o arquivo seja importado sem erros)
    class QObject: pass
    class Signal: 
        def __init__(self, *args): pass
        def emit(self, *args): pass
    class Slot:
        def __init__(self, *args):
            def decorator(func):
                return func
            return decorator

class DownloadWorker(QObject):
    """
    Worker que roda em uma QThread para baixar e descompactar o arquivo.
    """
    # Sinal (progresso_atual, progresso_total)
    progress = Signal(int, int)
    # Sinal (sucesso, mensagem_ou_erro)
    finished = Signal(bool, str)

    def __init__(self):
        super().__init__()
        self.temp_zip_path = "app_download.temp.zip"

    @Slot(str, str)
    def run_download_and_unzip(self, download_url: str, unzip_dir: str):
        """
        Tarefa principal: Baixa o arquivo, salva-o temporariamente
        e depois o descompacta.
        """
        try:
            # --- 1. Download ---
            print(f"[DownloadWorker] Iniciando download de: {download_url}")
            with requests.get(download_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                
                # Pega o tamanho total (se disponível)
                total_size = int(r.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(self.temp_zip_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        
                        # Emite o progresso
                        if total_size > 0:
                            self.progress.emit(downloaded_size, total_size)
                            
            print("[DownloadWorker] Download concluído.")
            
            # --- 2. Descompactação ---
            print(f"[DownloadWorker] Descompactando para: {unzip_dir}")
            
            # Garante que o diretório /app exista e esteja vazio
            if os.path.exists(unzip_dir):
                print(f"[DownloadWorker] Limpando diretório antigo: {unzip_dir}")
                shutil.rmtree(unzip_dir)
            os.makedirs(unzip_dir, exist_ok=True)
            
            with zipfile.ZipFile(self.temp_zip_path, 'r') as zip_ref:
                zip_ref.extractall(unzip_dir)
                
            print("[DownloadWorker] Descompactação concluída.")

            # --- 3. Limpeza ---
            if os.path.exists(self.temp_zip_path):
                os.remove(self.temp_zip_path)
                
            self.finished.emit(True, "Instalação concluída com sucesso.")

        except requests.exceptions.RequestException as e:
            print(f"[DownloadWorker] ERRO de Download: {e}")
            self.cleanup_on_fail()
            self.finished.emit(False, f"Erro de rede: {e}")
        except zipfile.BadZipFile:
            print("[DownloadWorker] ERRO: Arquivo baixado está corrompido.")
            self.cleanup_on_fail()
            self.finished.emit(False, "Erro: Arquivo do aplicativo corrompido.")
        except Exception as e:
            print(f"[DownloadWorker] ERRO Inesperado: {e}")
            self.cleanup_on_fail()
            self.finished.emit(False, f"Erro inesperado: {e}")

    def cleanup_on_fail(self):
        """Remove o .zip temporário se o download falhar."""
        try:
            if os.path.exists(self.temp_zip_path):
                os.remove(self.temp_zip_path)
        except Exception as e:
            print(f"[DownloadWorker] Erro ao limpar arquivo temporário: {e}")