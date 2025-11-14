# gerenciador_projeto.py
# Descrição: Versão corrigida para salvar brasões e fórmulas corretamente.
#
# ATUALIZAÇÃO (v47 - Gráficos 3D):
# 1. Adicionada lógica para salvar e carregar os ativos
#    associados ao Grafico3D (imagem PNG e dados JSON).
# 2. Importado 'Grafico3D' do documento.py.
#

import os
import json
import zipfile
import tempfile
import shutil
import copy
from PIL import Image

# --- INÍCIO DA MODIFICAÇÃO (v47) ---
from documento import (DocumentoABNT, Capitulo, Figura, Formula, Configuracoes,
                       Autor, Tabela, Grafico, Grafico3D) # <--- ADICIONADO Grafico3D
# --- FIM DA MODIFICAÇÃO ---
from referencia import Referencia, Livro, Artigo, Site
import gerenciador_config

# Tamanho padrão para os brasões processados (em pixels)
TAMANHO_PADRAO_BRASAO_PX = 128

class GerenciadorProjetos:
    def __init__(self):
        self.diretorio_temporario_atual = None

    def _limpar_diretorio_temporario(self):
        """Limpa o diretório temporário usado para carregar o projeto atual."""
        if self.diretorio_temporario_atual and os.path.exists(self.diretorio_temporario_atual):
            try:
                shutil.rmtree(self.diretorio_temporario_atual)
            except OSError as e:
                print(f"Erro ao limpar diretório temporário {self.diretorio_temporario_atual}: {e}")
        self.diretorio_temporario_atual = None

    def _processar_imagem_brasao(self, caminho_original: str, pasta_destino: str) -> str | None:
        """
        Processa uma imagem de brasão: converte para PNG, redimensiona para um
        tamanho padrão e a salva na pasta de destino. Retorna o nome do novo arquivo.
        """
        if not caminho_original or not os.path.exists(caminho_original):
            return None
        try:
            with Image.open(caminho_original) as img:
                img = img.convert("RGBA")
                
                img.thumbnail((TAMANHO_PADRAO_BRASAO_PX, TAMANHO_PADRAO_BRASAO_PX), Image.Resampling.LANCZOS)
                
                nome_arquivo = os.path.basename(caminho_original)
                nome_base, _ = os.path.splitext(nome_arquivo)
                novo_nome = f"{nome_base}_proc.png"
                caminho_saida = os.path.join(pasta_destino, novo_nome)
                
                img.save(caminho_saida, "PNG")
                return novo_nome
        except Exception as e:
            print(f"Erro ao processar imagem do brasão '{caminho_original}': {e}")
            return None

    def salvar_projeto(self, documento: DocumentoABNT, caminho_arquivo: str, add_to_recents: bool = True):
        """
        Salva o estado atual do documento, processando e incluindo todas as imagens.
        """
        with tempfile.TemporaryDirectory(prefix="abnf_save_") as temp_dir:
            # Cria subdiretórios
            imagens_dir = os.path.join(temp_dir, 'imagens')
            os.makedirs(imagens_dir)
            formulas_svg_dir = os.path.join(temp_dir, 'formulas_svg')
            os.makedirs(formulas_svg_dir)
            formulas_png_dir = os.path.join(temp_dir, 'formulas_png')
            os.makedirs(formulas_png_dir)
            brasoes_dir = os.path.join(temp_dir, 'brasoes')
            os.makedirs(brasoes_dir)
            charts_data_dir = os.path.join(temp_dir, 'charts_data_json')
            os.makedirs(charts_data_dir)

            doc_para_salvar = copy.deepcopy(documento)

            # --- LÓGICA DE PROCESSAMENTO DO BRASÃO ---
            cfg = doc_para_salvar.configuracoes
            
            # Processa o brasão esquerdo
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                try:
                    nome_arquivo_processado = os.path.basename(cfg.caminho_brasao_esquerdo_processado)
                    caminho_destino = os.path.join(brasoes_dir, nome_arquivo_processado)
                    
                    shutil.copy2(cfg.caminho_brasao_esquerdo_processado, caminho_destino)
                    
                    cfg.caminho_brasao_esquerdo_processado = os.path.join('brasoes', nome_arquivo_processado).replace('\\', '/')
                    
                except Exception as e:
                    print(f"Erro ao copiar brasão esquerdo processado: {e}")
                    cfg.caminho_brasao_esquerdo_processado = None
            else:
                 cfg.caminho_brasao_esquerdo_processado = None

            # Processa o brasão direito (mesma lógica)
            if cfg.caminho_brasao_direito_processado and os.path.exists(cfg.caminho_brasao_direito_processado):
                try:
                    nome_arquivo_processado = os.path.basename(cfg.caminho_brasao_direito_processado)
                    caminho_destino = os.path.join(brasoes_dir, nome_arquivo_processado)
                    
                    shutil.copy2(cfg.caminho_brasao_direito_processado, caminho_destino)
                    
                    cfg.caminho_brasao_direito_processado = os.path.join('brasoes', nome_arquivo_processado).replace('\\', '/')
                    
                except Exception as e:
                    print(f"Erro ao copiar brasão direito processado: {e}")
                    cfg.caminho_brasao_direito_processado = None
            else:
                cfg.caminho_brasao_direito_processado = None

            # Processa as figuras
            for figura in doc_para_salvar.banco_figuras:
                if figura.caminho_processado and os.path.exists(figura.caminho_processado):
                    nome_arquivo = os.path.basename(figura.caminho_processado)
                    caminho_destino = os.path.join(imagens_dir, nome_arquivo)
                    shutil.copy2(figura.caminho_processado, caminho_destino)
                    figura.caminho_processado = os.path.join('imagens', nome_arquivo).replace('\\', '/')
            
            # Processa os Gráficos (2D)
            for grafico in doc_para_salvar.banco_graficos:
                # 1. Copia a imagem PNG (para a pasta 'imagens', como uma figura)
                if grafico.caminho_imagem_processada and os.path.exists(grafico.caminho_imagem_processada):
                    nome_imagem = os.path.basename(grafico.caminho_imagem_processada)
                    caminho_destino_img = os.path.join(imagens_dir, nome_imagem)
                    shutil.copy2(grafico.caminho_imagem_processada, caminho_destino_img)
                    grafico.caminho_imagem_processada = os.path.join('imagens', nome_imagem).replace('\\', '/')
                
                # 2. Copia os dados JSON (para a pasta 'charts_data_json')
                if grafico.caminho_dados_json and os.path.exists(grafico.caminho_dados_json):
                    nome_json = os.path.basename(grafico.caminho_dados_json)
                    caminho_destino_json = os.path.join(charts_data_dir, nome_json)
                    shutil.copy2(grafico.caminho_dados_json, caminho_destino_json)
                    grafico.caminho_dados_json = os.path.join('charts_data_json', nome_json).replace('\\', '/')

            # --- INÍCIO: Processar Gráficos 3D (v47) ---
            for grafico_3d in doc_para_salvar.banco_graficos_3d:
                # 1. Copia a imagem PNG (para a pasta 'imagens')
                if grafico_3d.caminho_imagem_processada and os.path.exists(grafico_3d.caminho_imagem_processada):
                    nome_imagem = os.path.basename(grafico_3d.caminho_imagem_processada)
                    caminho_destino_img = os.path.join(imagens_dir, nome_imagem)
                    shutil.copy2(grafico_3d.caminho_imagem_processada, caminho_destino_img)
                    grafico_3d.caminho_imagem_processada = os.path.join('imagens', nome_imagem).replace('\\', '/')
                
                # 2. Copia os dados JSON (para a pasta 'charts_data_json')
                if grafico_3d.caminho_dados_json and os.path.exists(grafico_3d.caminho_dados_json):
                    nome_json = os.path.basename(grafico_3d.caminho_dados_json)
                    caminho_destino_json = os.path.join(charts_data_dir, nome_json)
                    shutil.copy2(grafico_3d.caminho_dados_json, caminho_destino_json)
                    grafico_3d.caminho_dados_json = os.path.join('charts_data_json', nome_json).replace('\\', '/')
            # --- FIM: Processar Gráficos 3D (v47) ---

            # Processa as fórmulas (SVG e PNG)
            for formula in doc_para_salvar.banco_formulas:
                if formula.caminho_svg and os.path.exists(formula.caminho_svg):
                    shutil.copy2(formula.caminho_svg, formulas_svg_dir)
                    formula.caminho_svg = os.path.join('formulas_svg', os.path.basename(formula.caminho_svg)).replace('\\', '/')
                
                if formula.caminho_processado_png and os.path.exists(formula.caminho_processado_png):
                    shutil.copy2(formula.caminho_processado_png, formulas_png_dir)
                    formula.caminho_processado_png = os.path.join('formulas_png', os.path.basename(formula.caminho_processado_png)).replace('\\', '/')
            
            # Serializa e salva o projeto
            dados_dict = doc_para_salvar.to_dict()
            caminho_json = os.path.join(temp_dir, 'documento.json')
            with open(caminho_json, 'w', encoding='utf-8') as f:
                json.dump(dados_dict, f, ensure_ascii=False, indent=4)
            
            base_name = os.path.splitext(caminho_arquivo)[0]
            shutil.make_archive(base_name, 'zip', temp_dir)
            
            if os.path.exists(caminho_arquivo):
                os.remove(caminho_arquivo)
            os.rename(base_name + '.zip', caminho_arquivo)

        if add_to_recents:
            gerenciador_config.add_projeto_recente(caminho_arquivo)

    def carregar_projeto(self, caminho_arquivo: str) -> DocumentoABNT:
        """Carrega um projeto e atualiza os caminhos para a pasta temporária."""
        self._limpar_diretorio_temporario()
        self.diretorio_temporario_atual = tempfile.mkdtemp(prefix="abnf_load_")

        with zipfile.ZipFile(caminho_arquivo, 'r') as zip_ref:
            zip_ref.extractall(self.diretorio_temporario_atual)
        
        caminho_json = os.path.join(self.diretorio_temporario_atual, 'documento.json')
        if not os.path.exists(caminho_json):
            raise FileNotFoundError("Arquivo 'documento.json' não encontrado no projeto.")
            
        with open(caminho_json, 'r', encoding='utf-8') as f:
            dados_dict = json.load(f)
            
        documento_carregado = DocumentoABNT.from_dict(dados_dict)

        # Atualiza o caminho dos brasões
        cfg = documento_carregado.configuracoes
        
        if cfg.caminho_brasao_esquerdo_processado:
            cfg.caminho_brasao_esquerdo_processado = os.path.join(self.diretorio_temporario_atual, cfg.caminho_brasao_esquerdo_processado.replace('/', os.path.sep))
        if cfg.caminho_brasao_direito_processado:
            cfg.caminho_brasao_direito_processado = os.path.join(self.diretorio_temporario_atual, cfg.caminho_brasao_direito_processado.replace('/', os.path.sep))
            
        # Atualiza os caminhos das figuras
        for figura in documento_carregado.banco_figuras:
            if figura.caminho_processado:
                figura.caminho_processado = os.path.join(self.diretorio_temporario_atual, figura.caminho_processado.replace('/', os.path.sep))

        # Atualiza os caminhos dos Gráficos (2D)
        for grafico in documento_carregado.banco_graficos:
            if grafico.caminho_imagem_processada:
                grafico.caminho_imagem_processada = os.path.join(self.diretorio_temporario_atual, grafico.caminho_imagem_processada.replace('/', os.path.sep))
            if grafico.caminho_dados_json:
                grafico.caminho_dados_json = os.path.join(self.diretorio_temporario_atual, grafico.caminho_dados_json.replace('/', os.path.sep))

        # --- INÍCIO: Atualizar caminhos Gráficos 3D (v47) ---
        for grafico_3d in documento_carregado.banco_graficos_3d:
            if grafico_3d.caminho_imagem_processada:
                grafico_3d.caminho_imagem_processada = os.path.join(self.diretorio_temporario_atual, grafico_3d.caminho_imagem_processada.replace('/', os.path.sep))
            if grafico_3d.caminho_dados_json:
                grafico_3d.caminho_dados_json = os.path.join(self.diretorio_temporario_atual, grafico_3d.caminho_dados_json.replace('/', os.path.sep))
        # --- FIM: Atualizar caminhos Gráficos 3D (v47) ---

        # Atualiza os caminhos das fórmulas
        for formula in documento_carregado.banco_formulas:
            if formula.caminho_svg:
                formula.caminho_svg = os.path.join(self.diretorio_temporario_atual, formula.caminho_svg.replace('/', os.path.sep))
            if formula.caminho_processado_png:
                formula.caminho_processado_png = os.path.join(self.diretorio_temporario_atual, formula.caminho_processado_png.replace('/', os.path.sep))

        return documento_carregado

    def fechar_projeto(self):
        self._limpar_diretorio_temporario()