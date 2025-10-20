# gerenciador_recuperacao.py
# Descrição: Centraliza a lógica de backup e recuperação de falhas.

import os
import shutil
import json
import time
from datetime import datetime
from pathlib import Path

# Usa o diretório de dados da aplicação para arquivos de recuperação.
# Isso evita poluir o diretório do usuário.
# Ex: C:\Users\SeuUsuario\AppData\Local\ABNTHelper\recovery
RECOVERY_DIR = Path(os.getenv('LOCALAPPDATA', Path.home())) / 'ABNTHelper' / 'recovery'
BACKUP_SUBDIR = ".abnf_backups"

def setup_diretorios():
    """Garante que os diretórios de recuperação existam."""
    os.makedirs(RECOVERY_DIR, exist_ok=True)

# --- LÓGICA DE RECUPERAÇÃO DE FALHAS (AUTO-SAVE) ---

def get_caminho_recuperacao(caminho_projeto_original: str | None) -> Path:
    """
    Gera um nome de arquivo único e consistente para o arquivo de recuperação.
    """
    if caminho_projeto_original:
        # Cria um nome de arquivo baseado no hash do caminho original para ser consistente.
        nome_base = str(hash(os.path.abspath(caminho_projeto_original)))
    else:
        # Para projetos novos, não salvos, o nome é baseado no timestamp da criação do processo.
        # Isso é intencionalmente difícil de recriar, por isso a limpeza direta é necessária.
        nome_base = f"novo_projeto_{int(time.time())}"
    
    return RECOVERY_DIR / f"{nome_base}.abnf.recovery"

def salvar_recuperacao(gerenciador_projeto, documento, caminho_projeto_original: str | None):
    """
    Salva o estado atual do documento em um arquivo de recuperação.
    Reutiliza a lógica de salvamento do GerenciadorProjetos.
    """
    caminho_recuperacao = get_caminho_recuperacao(caminho_projeto_original)
    
    metadata_path = caminho_recuperacao.with_suffix('.json')
    metadata = {
        'original_path': caminho_projeto_original,
        'original_name': os.path.basename(caminho_projeto_original) if caminho_projeto_original else "Novo Projeto",
        'recovery_save_time': datetime.now().isoformat(),
        'recovery_file_path': str(caminho_recuperacao) # Armazena o caminho exato para limpeza confiável
    }

    try:
        # Salva o projeto sem adicioná-lo à lista de recentes
        gerenciador_projeto.salvar_projeto(documento, str(caminho_recuperacao), add_to_recents=False)
        
        # Salva os metadados com o caminho exato
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=4)
            
        print(f"[{datetime.now():%H:%M:%S}] Auto-save realizado para: {caminho_recuperacao.name}")

    except Exception as e:
        print(f"ERRO CRÍTICO no auto-save: {e!r}")

def verificar_arquivos_recuperaveis() -> list[dict]:
    """Verifica na inicialização se existem arquivos de recuperação válidos."""
    arquivos_encontrados = []
    if not os.path.exists(RECOVERY_DIR):
        return []
        
    for item in os.listdir(RECOVERY_DIR):
        if item.endswith(".abnf.recovery"):
            caminho_recuperacao = RECOVERY_DIR / item
            metadata_path = caminho_recuperacao.with_suffix('.json')
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                    # Garante que o caminho no metadado está correto e atualizado
                    metadata['recovery_file_path'] = str(caminho_recuperacao)
                    arquivos_encontrados.append(metadata)
                except (json.JSONDecodeError, IOError):
                    continue # Metadados corrompidos ou erro de leitura, ignora
    return arquivos_encontrados

# --- LÓGICA DE BACKUP (A CADA SALVAMENTO) ---

def criar_backup(caminho_projeto: str, max_backups: int):
    """Cria uma cópia de backup do arquivo de projeto atual antes de salvá-lo."""
    if not caminho_projeto or not os.path.exists(caminho_projeto):
        return

    diretorio_pai = Path(caminho_projeto).parent
    backup_dir = diretorio_pai / BACKUP_SUBDIR
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    nome_arquivo_original = Path(caminho_projeto).stem
    caminho_backup = backup_dir / f"{nome_arquivo_original}_{timestamp}.abnf.bak"

    try:
        shutil.copy2(caminho_projeto, caminho_backup)
        print(f"Backup criado em: {caminho_backup}")
        _limpar_backups_antigos(backup_dir, max_backups)
    except Exception as e:
        print(f"ERRO ao criar backup: {e}")

def _limpar_backups_antigos(backup_dir: Path, max_backups: int):
    """Mantém apenas o número máximo de backups, removendo os mais antigos."""
    try:
        backups = sorted(
            [f for f in backup_dir.iterdir() if f.is_file() and f.name.endswith(".abnf.bak")],
            key=os.path.getmtime,
            reverse=True
        )
        
        if len(backups) > max_backups:
            backups_para_remover = backups[max_backups:]
            for backup in backups_para_remover:
                os.remove(backup)
                print(f"Backup antigo removido: {backup.name}")
    except FileNotFoundError:
        # Isso pode acontecer se o diretório for removido entre a listagem e a exclusão. É seguro ignorar.
        pass

# --- LÓGICA DE LIMPEZA DE ARQUIVOS DE RECUPERAÇÃO ---

def limpar_recuperacao(caminho_projeto_original: str | None):
    """
    Remove o arquivo de recuperação tentando recriar seu nome.
    Usado para limpeza em eventos normais (salvar, fechar) em projetos já salvos.
    """
    if caminho_projeto_original is None:
        return

    caminho_recuperacao = get_caminho_recuperacao(caminho_projeto_original)
    metadata_path = caminho_recuperacao.with_suffix('.json')

    try:
        if os.path.exists(caminho_recuperacao):
            os.remove(caminho_recuperacao)
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
        print(f"Arquivo de recuperação limpo para: {caminho_projeto_original}")
    except Exception as e:
        print(f"Erro ao tentar limpar arquivo de recuperação para {caminho_projeto_original}: {e}")

def limpar_recuperacao_pelo_caminho_direto(caminho_arquivo_recuperacao: str):
    """
    Remove um arquivo de recuperação específico usando seu caminho exato.
    Esta é a forma 100% confiável de garantir a exclusão, especialmente
    após o usuário descartar uma recuperação de um projeto nunca salvo.
    """
    if not caminho_arquivo_recuperacao or not isinstance(caminho_arquivo_recuperacao, str):
        return
        
    caminho_recuperacao = Path(caminho_arquivo_recuperacao)
    metadata_path = caminho_recuperacao.with_suffix('.json')
    
    try:
        if os.path.exists(caminho_recuperacao):
            os.remove(caminho_recuperacao)
            print(f"Arquivo de recuperação removido DIRETAMENTE: {caminho_recuperacao.name}")
        if os.path.exists(metadata_path):
            os.remove(metadata_path)
    except Exception as e:
        print(f"Erro ao remover arquivo de recuperação diretamente ({caminho_recuperacao.name}): {e}")