# gerenciador_config.py
# Descrição: Lida com o salvamento e carregamento de configurações da aplicação,
# como a lista de projetos recentes, e as configurações de backup e recuperação.

import os
import json
from datetime import datetime

CONFIG_FILE = "abnf_helper_config.json"
MAX_RECENT_PROJECTS = 10

def get_default_config():
    """Retorna a estrutura de configuração padrão da aplicação."""
    return {
        "recent_projects": [],
        "recovery": {
            "autosave_enabled": True,
            #AQUI ESTÁ ESTABELECIDO O INTERVALO DE AUTOSAVE PARA 10 MINUTOS
            "autosave_periodic_interval_min": 10
        },
        "backup": {
            "backup_on_save_enabled": True,
            "max_backups_per_project": 10
        }
    }

def carregar_config():
    """
    Carrega o arquivo de configuração JSON, garantindo que seja compatível
    com a versão mais recente do programa.
    """
    if not os.path.exists(CONFIG_FILE):
        return get_default_config()
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        defaults = get_default_config()
        config.setdefault('recovery', defaults['recovery'])
        if 'autosave_interval_min' in config['recovery']:
            del config['recovery']['autosave_interval_min']
        config['recovery'].setdefault('autosave_periodic_interval_min', defaults['recovery']['autosave_periodic_interval_min'])
        
        config.setdefault('backup', defaults['backup'])
        
        return config
    except (json.JSONDecodeError, IOError):
        return get_default_config()

def salvar_config(data):
    """Salva os dados no arquivo de configuração JSON."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except IOError as e:
        print(f"Erro ao salvar configuração: {e}")

def get_projetos_recentes():
    """
    Retorna a lista de projetos recentes, FILTRANDO quaisquer arquivos
    de recuperação que possam ter sido adicionados por engano.
    """
    config = carregar_config()
    projetos = config.get("recent_projects", [])

    # BLINDAGEM (PARTE 1): Filtra a lista ao ser lida.
    projetos_filtrados = [
        p for p in projetos if p.get("path") and not p["path"].endswith(".abnf.recovery")
    ]

    projetos_filtrados.sort(key=lambda p: p.get("timestamp", 0), reverse=True)
    return projetos_filtrados

def add_projeto_recente(caminho_arquivo):
    """Adiciona ou atualiza um projeto na lista de recentes."""
    if not caminho_arquivo:
        return

    # BLINDAGEM (PARTE 2): Recusa-se a adicionar arquivos de recuperação.
    if caminho_arquivo.endswith(".abnf.recovery"):
        print(f"Tentativa de adicionar arquivo de recuperação '{os.path.basename(caminho_arquivo)}' aos recentes foi bloqueada.")
        return
        
    config = carregar_config()
    # Usa a função get_projetos_recentes para começar com uma lista já limpa
    projetos = get_projetos_recentes()
    
    caminho_abs = os.path.abspath(caminho_arquivo)
    
    # Remove qualquer entrada existente com o mesmo caminho para evitar duplicatas
    projetos = [p for p in projetos if p.get("path") != caminho_abs]

    # Adiciona a nova entrada no início da lista
    novo_projeto = {
        "path": caminho_abs,
        "name": os.path.basename(caminho_abs),
        "timestamp": datetime.now().timestamp()
    }
    projetos.insert(0, novo_projeto)

    # Limita o número de projetos recentes
    config["recent_projects"] = projetos[:MAX_RECENT_PROJECTS]
    salvar_config(config)

def remover_projeto_recente(caminho_arquivo):
    """Remove um projeto da lista de recentes (ex: se o arquivo foi deletado)."""
    config = carregar_config()
    projetos = config.get("recent_projects", [])
    caminho_abs = os.path.abspath(caminho_arquivo)
    
    projetos_atualizados = [p for p in projetos if p.get("path") != caminho_abs]
    
    if len(projetos_atualizados) < len(projetos):
        config["recent_projects"] = projetos_atualizados
        salvar_config(config)