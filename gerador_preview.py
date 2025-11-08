# gerador_preview.py
# Descrição: Versão com lógica de quebra de palavras longas (word-break)
# e CSS de alinhamento de brasão corrigido.

import os
import re
import math
from documento import DocumentoABNT, Capitulo
from PIL import Image, ImageFont 

# --- CONSTANTES DE ESTIMATIVA DE ALTURA (EM CM) ---
ALTURA_CONTEUDO_PAGINA = 24.7
ALTURA_LINHA_TEXTO = 0.64 
ALTURA_TITULO_SECAO = 1.5
ALTURA_LEGENDA = 1.2
ALTURA_LINHA_TABELA = 0.8
LARGURA_CONTEUDO_CM = 16.0 
RECUO_PRIMEIRA_LINHA_CM = 1.25
#CARACTERES_POR_LINHA = 69 # <--- Não usamos mais isso

class GeradorHTMLPreview:
    def __init__(self, doc_abnt: DocumentoABNT):
        self.doc_abnt = doc_abnt
        self.entradas_sumario = []
        self.paginas_html = []
        self.conteudo_pagina_atual = []
        self.altura_restante = ALTURA_CONTEUDO_PAGINA
        self.contador_tabelas = 0
        self.contador_figuras = 0
        self.contador_formulas = 0
        self.classe_pagina_atual = 'pagina'
        self.is_artigo = self.doc_abnt.configuracoes.tipo_trabalho == "Artigo Científico"

        self.font_medidor = self._carregar_fonte_medidora()
        self.PX_PER_CM = 96 / 2.54 
        self.LARGURA_CONTEUDO_PX = LARGURA_CONTEUDO_CM * self.PX_PER_CM
        self.RECUO_PRIMEIRA_LINHA_PX = RECUO_PRIMEIRA_LINHA_CM * self.PX_PER_CM
        
        # Mede um espaço e um caractere médio
        try:
            self.LARGURA_ESPACO_PX = self.font_medidor.getbbox(" ")[2]
            # Usamos 'm' como char médio para estimar a quebra de palavras longas
            self.LARGURA_CHAR_MEDIO_PX = self.font_medidor.getbbox("m")[2]
            if self.LARGURA_CHAR_MEDIO_PX == 0: self.LARGURA_CHAR_MEDIO_PX = 9 # Fallback
        except:
            self.LARGURA_ESPACO_PX = 4 # Fallback
            self.LARGURA_CHAR_MEDIO_PX = 9 # Fallback


    def _carregar_fonte_medidora(self):
        """Tenta carregar a fonte Times New Roman 12pt do sistema."""
        try:
            font_path = "C:/Windows/Fonts/times.ttf"
            if not os.path.exists(font_path):
                font_path = "C:/Windows/Fonts/timesbd.ttf"
            return ImageFont.truetype(font_path, 16) # 12pt = 16px
        except IOError:
            print("AVISO: Fonte 'times.ttf' não encontrada. Usando fonte padrão do Pillow.")
            try:
                return ImageFont.load_default(16)
            except:
                return ImageFont.load_default()

    def _calcular_altura_paragrafo(self, texto: str, is_continuacao=False) -> float:
        """
        Calcula a altura real (em cm) que um parágrafo ocupará,
        medindo a largura de cada palavra E quebrando palavras longas.
        """
        palavras = texto.strip().split()
        if not palavras: return 0.0

        linhas = 1
        largura_linha_atual = 0
        if not is_continuacao:
            largura_linha_atual = self.RECUO_PRIMEIRA_LINHA_PX
        
        for palavra in palavras:
            try:
                bbox = self.font_medidor.getbbox(palavra); largura_palavra = bbox[2] - bbox[0]
            except:
                largura_palavra = len(palavra) * (self.LARGURA_CHAR_MEDIO_PX * 0.9) # fallback

            if (largura_linha_atual == (self.RECUO_PRIMEIRA_LINHA_PX if not is_continuacao else 0)) or \
               (largura_linha_atual + self.LARGURA_ESPACO_PX + largura_palavra) <= self.LARGURA_CONTEUDO_PX:
                largura_linha_atual += (self.LARGURA_ESPACO_PX if largura_linha_atual > 0 else 0) + largura_palavra
            
            else:
                linhas += 1
                largura_linha_atual = largura_palavra 
            
            while largura_linha_atual > self.LARGURA_CONTEUDO_PX:
                linhas += 1
                largura_linha_atual -= self.LARGURA_CONTEUDO_PX

        return linhas * ALTURA_LINHA_TEXTO

    def _get_image_aspect_ratio(self, image_path):
        if not image_path or not os.path.exists(image_path):
            return 0.5625 
        try:
            with Image.open(image_path) as img:
                width, height = img.size
                if width > 0:
                    return height / width 
        except Exception as e:
            print(f"Aviso: Não foi possível ler o aspect ratio da imagem {image_path}: {e}")
        return 0.5625 

    def _get_svg_aspect_ratio(self, svg_path):
        if not svg_path or not os.path.exists(svg_path):
            return 0.2 
        try:
            with open(svg_path, 'r', encoding='utf-8') as f:
                svg_content = f.read(1024) 
            match = re.search(r'viewBox="[\d\.\s-]* ([\d\.]+) ([\d\.]+)"', svg_content)
            if match:
                width = float(match.group(1)); height = float(match.group(2))
                if width > 0: return height / width
            width_match = re.search(r'width="([\d\.]+)(ex|pt|px)?"', svg_content)
            height_match = re.search(r'height="([\d\.]+)(ex|pt|px)?"', svg_content)
            if width_match and height_match:
                width = float(width_match.group(1)); height = float(height_match.group(1))
                if width > 0: return height / width
            return 0.2 
        except Exception as e:
            print(f"Aviso: Não foi possível ler o aspect ratio do SVG {svg_path}: {e}")
            return 0.2

    def _estimar_paginacao_e_coletar_sumario(self):
        self.entradas_sumario = []
        altura_restante = ALTURA_CONTEUDO_PAGINA
        pagina_atual = 4
        
        def simular_nova_pagina():
            nonlocal altura_restante, pagina_atual
            pagina_atual += 1
            altura_restante = ALTURA_CONTEUDO_PAGINA

        def simular_adicao_bloco(altura_bloco):
            nonlocal altura_restante
            altura_necessaria = altura_bloco
            if altura_bloco == ALTURA_TITULO_SECAO:
                altura_necessaria += ALTURA_LINHA_TEXTO * 2
            if altura_restante < altura_necessaria:
                simular_nova_pagina()
            altura_restante -= altura_necessaria 

        def simular_paragrafo_quebravel(texto, is_continuacao=False):
            nonlocal altura_restante
            if not texto.strip(): return
            
            altura_total_paragrafo = self._calcular_altura_paragrafo(texto, is_continuacao)
            
            while altura_total_paragrafo > 0:
                altura_que_cabe = math.floor(altura_restante / ALTURA_LINHA_TEXTO) * ALTURA_LINHA_TEXTO
                if altura_que_cabe <= (ALTURA_LINHA_TEXTO * 2): # Evita 1 linha órfã
                    simular_nova_pagina()
                    continue
                if altura_total_paragrafo <= altura_que_cabe:
                    altura_restante -= altura_total_paragrafo
                    altura_total_paragrafo = 0
                else:
                    altura_total_paragrafo -= altura_que_cabe
                    simular_nova_pagina()
                    is_continuacao = True # Próxima parte do parágrafo não terá recuo

        def coletar_recursivo(no_pai: Capitulo, prefixo_numeracao=""):
            for i, no_filho in enumerate(no_pai.filhos, 1):
                numero_completo = f"{prefixo_numeracao}{i}"
                pagina_prevista = pagina_atual
                altura_necessaria_titulo = ALTURA_TITULO_SECAO + (ALTURA_LINHA_TEXTO * 2)
                if altura_restante < altura_necessaria_titulo:
                    pagina_prevista += 1
                self.entradas_sumario.append({
                    "numero": numero_completo, "titulo": no_filho.titulo, "nivel": len(numero_completo.split('.')),
                    "id_ancora": f"secao-{numero_completo.replace('.', '-')}", "pagina": pagina_prevista
                })
                simular_adicao_bloco(ALTURA_TITULO_SECAO)
                if no_filho.conteudo:
                    padrao = r"\{\{(Tabela|Figura|Formula):([^}]+)\}\}"
                    partes = re.split(padrao, no_filho.conteudo)
                    is_continuacao_paragrafo = False
                    for k, parte in enumerate(partes):
                        if k % 3 == 0:
                            if parte.strip():
                                paragrafos = parte.strip().split('\n')
                                for j, paragrafo_texto in enumerate(paragrafos):
                                    if paragrafo_texto.strip():
                                        simular_paragrafo_quebravel(paragrafo_texto, is_continuacao_paragrafo)
                                        is_continuacao_paragrafo = False 
                                    is_continuacao_paragrafo = False 
                            else:
                                is_continuacao_paragrafo = False
                        elif k % 3 == 1:
                            tipo, titulo = parte, partes[k+1]
                            if tipo == "Tabela":
                                obj = next((t for t in self.doc_abnt.banco_tabelas if t.titulo == titulo), None)
                                if obj and obj.dados: simular_adicao_bloco((len(obj.dados) * ALTURA_LINHA_TABELA) + (ALTURA_LEGENDA * 2))
                            elif tipo == "Figura":
                                obj = next((f for f in self.doc_abnt.banco_figuras if f.titulo == titulo), None)
                                if obj:
                                    caminho_img = obj.caminho_processado or obj.caminho_original
                                    aspect_ratio = self._get_image_aspect_ratio(caminho_img)
                                    altura_imagem_cm = obj.largura_cm * aspect_ratio
                                    simular_adicao_bloco(altura_imagem_cm + (ALTURA_LEGENDA * 2))
                            elif tipo == "Formula":
                                obj = next((f for f in self.doc_abnt.banco_formulas if f.legenda == titulo), None)
                                if obj:
                                    aspect_ratio = self._get_svg_aspect_ratio(obj.caminho_svg or obj.caminho_processado_png)
                                    altura_imagem_cm = obj.largura_cm * aspect_ratio
                                    simular_adicao_bloco(altura_imagem_cm + ALTURA_LEGENDA + 0.5) 
                            is_continuacao_paragrafo = False
                coletar_recursivo(no_filho, f"{numero_completo}.")
        
        coletar_recursivo(self.doc_abnt.estrutura_textual)

        simular_nova_pagina()
        self.entradas_sumario.append({
            "numero": "", "titulo": "REFERÊNCIAS", "nivel": 1,
            "id_ancora": "secao-referencias", "pagina": pagina_atual
        })

    def _nova_pagina(self):
        if self.conteudo_pagina_atual:
            classe_real = self.conteudo_pagina_atual.pop(0)
            self.paginas_html.append(f'<div class="{classe_real}">{"".join(self.conteudo_pagina_atual)}</div>')
        self.conteudo_pagina_atual = [self.classe_pagina_atual]
        self.altura_restante = ALTURA_CONTEUDO_PAGINA

    def _adicionar_elemento_bloco(self, html, altura):
        self.classe_pagina_atual = 'pagina'
        if not self.conteudo_pagina_atual: self.conteudo_pagina_atual.append(self.classe_pagina_atual)
        
        altura_necessaria = altura
        if html.startswith("<h1"): 
            altura_necessaria += ALTURA_LINHA_TEXTO * 2
            
        if self.altura_restante < altura_necessaria: self._nova_pagina()
        
        self.conteudo_pagina_atual.append(html)
        self.altura_restante -= altura_necessaria

    def _adicionar_paragrafo_quebravel(self, texto_paragrafo, is_continuacao=False):
        self.classe_pagina_atual = 'pagina'
        if not self.conteudo_pagina_atual:
            self.conteudo_pagina_atual.append(self.classe_pagina_atual)

        texto_restante = texto_paragrafo.strip()
        
        while texto_restante:
            if self.altura_restante < ALTURA_LINHA_TEXTO * 2:
                self._nova_pagina()
                is_continuacao = True
                continue

            altura_total_texto_restante = self._calcular_altura_paragrafo(texto_restante, is_continuacao)
            
            if altura_total_texto_restante <= self.altura_restante:
                base_class = "corpo-texto" if not is_continuacao else "paragrafo-continuado"
                self.conteudo_pagina_atual.append(f'<p class="{base_class}">{texto_restante}</p>')
                self.altura_restante -= altura_total_texto_restante
                texto_restante = ""
            
            else:
                palavras_paragrafo = texto_restante.split()
                texto_para_pagina_atual = ""
                indice_quebra = 0
                
                for i, palavra in enumerate(palavras_paragrafo):
                    texto_teste = texto_para_pagina_atual + " " + palavra if texto_para_pagina_atual else palavra
                    altura_teste = self._calcular_altura_paragrafo(texto_teste, is_continuacao)
                    
                    if altura_teste > self.altura_restante:
                        indice_quebra = i
                        break
                    else:
                        texto_para_pagina_atual = texto_teste
                
                if indice_quebra == 0 and texto_para_pagina_atual:
                     indice_quebra = len(palavras_paragrafo)

                if indice_quebra == 0 and len(palavras_paragrafo) > 0:
                    palavra_longa = palavras_paragrafo[0]
                    largura_disp_linha1 = self.LARGURA_CONTEUDO_PX
                    if not is_continuacao:
                        largura_disp_linha1 -= self.RECUO_PRIMEIRA_LINHA_PX
                    chars_na_linha1 = max(1, int(largura_disp_linha1 / self.LARGURA_CHAR_MEDIO_PX))
                    chars_por_linha_normal = max(1, int(self.LARGURA_CONTEUDO_PX / self.LARGURA_CHAR_MEDIO_PX))
                    linhas_restantes = math.floor((self.altura_restante - ALTURA_LINHA_TEXTO) / ALTURA_LINHA_TEXTO)
                    total_chars_que_cabem = chars_na_linha1 + (linhas_restantes * chars_por_linha_normal)
                    
                    ponto_quebra_char = total_chars_que_cabem
                    texto_para_pagina_atual = palavra_longa[:ponto_quebra_char] 
                    texto_restante = palavra_longa[ponto_quebra_char:] + " " + " ".join(palavras_paragrafo[1:])
                    
                else:
                    texto_para_pagina_atual = " ".join(palavras_paragrafo[:indice_quebra])
                    texto_restante = " ".join(palavras_paragrafo[indice_quebra:])
                
                base_class = "corpo-texto" if not is_continuacao else "paragrafo-continuado"
                self.conteudo_pagina_atual.append(f'<p class="{base_class}">{texto_para_pagina_atual}</p>')
                
                altura_consumida = self._calcular_altura_paragrafo(texto_para_pagina_atual, is_continuacao)
                self.altura_restante -= altura_consumida
            
            if texto_restante:
                self._nova_pagina()
                is_continuacao = True

    def _renderizar_cabecalho_artigo_html(self):
        autores_html = ", ".join([a.nome_completo for a in self.doc_abnt.autores])
        self._adicionar_elemento_bloco(f'<p style="text-align: center;"><strong>{self.doc_abnt.titulo.upper()}</strong></p><br>', ALTURA_LINHA_TEXTO * 2)
        self._adicionar_elemento_bloco(f'<p style="text-align: center;">{autores_html}</p><br>', ALTURA_LINHA_TEXTO * 2)
        self._adicionar_elemento_bloco(f'<p><strong>Resumo</strong></p>', ALTURA_LINHA_TEXTO)
        self._adicionar_paragrafo_quebravel(self.doc_abnt.resumo)
        self._adicionar_elemento_bloco(f'<br><p><strong>Palavras-chave:</strong> {self.doc_abnt.palavras_chave.replace(";", ".")}.</p>', ALTURA_LINHA_TEXTO * 2)

    def gerar_html(self) -> str:
        self.paginas_html = []
        self.conteudo_pagina_atual = []
        self.altura_restante = ALTURA_CONTEUDO_PAGINA
        self.classe_pagina_atual = 'pagina'
        
        cfg = self.doc_abnt.configuracoes
        
        html_style = """
        <style>
            html { scroll-behavior: smooth; }
            body { font-family: 'Times New Roman', Times, serif; font-size: 12pt; background-color: #E0E0E0; counter-reset: page 3; }
            .pagina {
                width: 21cm; height: 29.7cm; padding: 3cm 2cm 2cm 3cm;
                margin: 20px auto; background-color: white;
                box-shadow: 0 0 10px rgba(0,0,0,0.2); box-sizing: border-box;
                position: relative; 
                overflow: hidden; /* Isso esconde o texto que transborda */
                line-height: 1.5;
            }
            .pagina.capa, .pagina.folha-rosto {
                display: flex; flex-direction: column;
                justify-content: space-between; text-align: center;
            }
            .capa-conteudo-meio {
                flex-grow: 1; display: flex;
                flex-direction: column; justify-content: center;
            }
            .pagina:not(.pre-textual) { counter-increment: page; }
            .pagina:not(.pre-textual)::after {
                content: counter(page); position: absolute;
                top: 1.5cm; right: 2cm; font-size: 12pt;
            }
            h1 { font-size: 12pt; font-weight: bold; text-transform: uppercase; margin-top: 1em; margin-bottom: 1em; }
            
            p { 
                margin: 0; padding: 0; 
                overflow-wrap: break-word; /* Padrão (quebra em espaços) */
                word-wrap: break-word;     /* Compatibilidade */
            }
            
            p.corpo-texto { text-align: justify; text-indent: 1.25cm; }
            p.paragrafo-continuado { text-align: justify; text-indent: 0; }
            .paragrafo-quebrado { text-align-last: justify; }
            .capa p, .folha-rosto p { text-indent: 0; }
            .bloco-texto-capa { white-space: normal; overflow-wrap: break-word; }
            .natureza { text-indent: 0; margin-left: 8cm; font-size: 11pt; text-align: justify; }
            .resumo-paragrafo { text-indent: 1.25cm; text-align: justify; }
            .resumo-titulo-palavras-chave { text-indent: 0; font-weight: bold; margin-top: 1em;}
            .referencia { text-align: justify; line-height: 1.0; margin-bottom: 12px; }
            .legenda { font-size: 10pt; text-align: center; text-indent: 0; margin-bottom: 0.5em; }
            .fonte { font-size: 10pt; text-align: left; text-indent: 0; margin-top: 2px; }
            .formula-container { text-align: center; margin: 1em 0; }
            .formula-legenda { font-size: 10pt; text-align: center; text-indent: 0; margin-top: 0.5em; }
            table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 10pt; }
            th, td { border: 1px solid black; padding: 4px; text-align: left; }
            table.abnt { border: none; } table.abnt th, table.abnt td { border: none; }
            table.abnt thead tr { border-top: 1px solid black; border-bottom: 1px solid black; }
            table.abnt tbody tr:last-of-type { border-bottom: 1px solid black; }
            img { display: block; margin: 1em auto; max-width: 100%; height: auto; }
            .sumario-item { display: flex; justify-content: space-between; text-indent: 0; }
            .sumario-item a { text-decoration: none; color: black; display: flex; width: 100%; }
            .sumario-item a:hover { text-decoration: underline; }
            .sumario-titulo { order: 1; white-space: nowrap; }
            .sumario-dots { order: 2; flex-grow: 1; border-bottom: 1px dotted black; margin: 0 5px; transform: translateY(-4px); }
            .sumario-pagina { order: 3; padding-left: 5px; }
            .sumario-nivel-2 { margin-left: 2em; } .sumario-nivel-3 { margin-left: 4em; }
            .brasao-container {
                min-height: 4cm; margin-bottom: 1cm;
                display: flex; flex-direction: column; 
                /* O 'justify-content' foi movido para as classes filhas */
            }
            .brasoes-lado-a-lado {
                flex-direction: row; justify-content: space-between; align-items: center;
            }
            .brasoes-lado-a-lado .instituicao-central { flex-grow: 1; padding: 0 1cm; }
            .brasao-container img { display: inline-block; margin: 0; max-height: 3.5cm; }
            
            /* --- INÍCIO DA CORREÇÃO (ALINHAMENTO BRASÃO) --- */
            /* 1. Alinha os *itens* (img, p) DENTRO do container flex */
            .brasao-centralizado { 
                justify-content: center; /* Alinha verticalmente (para o caso de só ter o <p>) */
                align-items: center; /* Alinha horizontalmente */ 
                text-align: center; /* Fallback para o <p> */
            }
            .brasao-esquerda { 
                justify-content: center;
                align-items: flex-start; /* Alinha horizontalmente à esquerda */ 
                text-align: left;
            }
            .brasao-direita { 
                justify-content: center;
                align-items: flex-end; /* Alinha horizontalmente à direita */ 
                text-align: right;
            }

            /* 2. Alinha o container *em relação à página* (que é display: flex) */
            /* Seleciona o primeiro 'div' filho da capa (que é o .brasao-container) */
            .pagina.capa > div:first-child {
                align-self: stretch; /* Padrão: estica (bom para centralizado e lados) */
            }
            /* Estas regras não são mais necessárias se o .brasao-container já é flex */
            /* --- FIM DA CORREÇÃO --- */
            
        </style>
        """
        
        if self.is_artigo:
            self.classe_pagina_atual = 'pagina'
            self.conteudo_pagina_atual = [self.classe_pagina_atual]
            self._renderizar_cabecalho_artigo_html()
        else:
            self._estimar_paginacao_e_coletar_sumario()
            autores_capa_html = "<br>".join([a.nome_completo.upper() for a in self.doc_abnt.autores])
            self.paginas_html.append(f'<div class="pagina capa pre-textual">{self._renderizar_capa_html(cfg, autores_capa_html)}</div>')
            self.paginas_html.append(f'<div class="pagina folha-rosto pre-textual">{self._renderizar_folha_rosto_html(cfg, autores_capa_html)}</div>')
            self.paginas_html.append(f'<div class="pagina resumo-page pre-textual">{self._renderizar_resumo_html()}</div>')
            if self.entradas_sumario:
                self.paginas_html.append(f'<div class="pagina sumario-page pre-textual">{self._renderizar_sumario_html()}</div>')
            self.classe_pagina_atual = 'pagina'
            self.conteudo_pagina_atual = [self.classe_pagina_atual]
            self.altura_restante = ALTURA_CONTEUDO_PAGINA

        self._renderizar_secoes_recursivamente_html(self.doc_abnt.estrutura_textual)
        self._nova_pagina()
        
        self._adicionar_elemento_bloco("<h1 id='secao-referencias'>REFERÊNCIAS</h1>", ALTURA_TITULO_SECAO)
        self.doc_abnt.ordenar_referencias()
        for ref in self.doc_abnt.referencias:
            ref_html = f'<p class="referencia">{ref.formatar().replace("**", "<strong>").replace("</strong>", "</strong>")}</p>'
            altura_ref = (len(ref.formatar()) / 100 + 1) * (ALTURA_LINHA_TEXTO * 0.8)
            self._adicionar_elemento_bloco(ref_html, altura_ref)
        self._nova_pagina()

        return f"<!DOCTYPE html><html><head><meta charset='UTF-8'>{html_style}</head><body>{''.join(self.paginas_html)}</body></html>"

    # --- INÍCIO DA CORREÇÃO (HTML DO CABEÇALHO) ---
    def _renderizar_cabecalho_capa_html(self, cfg):
        posicao = cfg.posicao_brasao
        instituicao_html = f'<p class="bloco-texto-capa"><strong>{cfg.instituicao.upper()}</strong></p>'

        # --- Caso 1: Nenhum (Funciona) ---
        if posicao == "Nenhum": 
            return f'<div class="brasao-container brasao-centralizado">{instituicao_html}</div>'

        # --- Caso 2: Acima do Nome (Funciona) ---
        if posicao == "Acima do Nome":
            brasao_html = ""
            classe_css_container = "brasao-centralizado" # Classe no container
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                url = f"file:///{os.path.abspath(cfg.caminho_brasao_esquerdo_processado).replace(os.path.sep, '/')}"
                brasao_html = f'<img src="{url}" style="width:{cfg.tamanho_brasao_esquerdo_cm}cm; margin-bottom: 1cm;"><br>'
            
            # A classe .brasao-centralizado no container e o text-align: center no <p> (padrão da capa) resolvem
            return f'<div class="brasao-container {classe_css_container}"><p class="bloco-texto-capa">{brasao_html}<strong>{cfg.instituicao.upper()}</strong></p></div>'

        # --- INÍCIO DA CORREÇÃO ---
        # --- Casos 3, 4, 5: Lados, Apenas Esquerdo, Apenas Direito ---
        # Todos usam o layout 'brasoes-lado-a-lado', mas com divs vazias.

        html_esq = "<div></div>" # Placeholder (para manter o alinhamento)
        html_dir = "<div></div>" # Placeholder (para manter o alinhamento)
        
        # Preenche o lado esquerdo se for "Lados" OU "Apenas Esquerdo"
        if (posicao == "Lados (Esquerdo e Direito)" or posicao == "Apenas Esquerdo"):
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                url_esq = f"file:///{os.path.abspath(cfg.caminho_brasao_esquerdo_processado).replace(os.path.sep, '/')}"
                html_esq = f'<div><img src="{url_esq}" style="width:{cfg.tamanho_brasao_esquerdo_cm}cm;"></div>'
        
        # Preenche o lado direito se for "Lados" OU "Apenas Direito"
        if (posicao == "Lados (Esquerdo e Direito)" or posicao == "Apenas Direito"):
            if cfg.caminho_brasao_direito_processado and os.path.exists(cfg.caminho_brasao_direito_processado):
                url_dir = f"file:///{os.path.abspath(cfg.caminho_brasao_direito_processado).replace(os.path.sep, '/')}"
                html_dir = f'<div><img src="{url_dir}" style="width:{cfg.tamanho_brasao_direito_cm}cm;"></div>'

        # O HTML da instituição fica no meio
        instituicao_div = f'<div class="instituicao-central">{instituicao_html}</div>'
        
        # Retorna o layout de 3 colunas para TODOS os casos de "lado"
        return f'<div class="brasao-container brasoes-lado-a-lado">{html_esq}{instituicao_div}{html_dir}</div>'
    # --- FIM DA CORREÇÃO ---

    def _renderizar_secoes_recursivamente_html(self, no_pai: Capitulo, prefixo_numeracao=""):
        for i, no_filho in enumerate(no_pai.filhos, 1):
            numero_completo = f"{prefixo_numeracao}{i}"
            nivel = len(numero_completo.split('.'))
            titulo_texto = f"{numero_completo} {no_filho.titulo.upper() if nivel == 1 and not self.is_artigo else no_filho.titulo}"
            id_ancora = f"secao-{numero_completo.replace('.', '-')}"
            self._adicionar_elemento_bloco(f"<h1 id='{id_ancora}'>{titulo_texto}</h1>", ALTURA_TITULO_SECAO)
            
            if no_filho.conteudo:
                padrao = r"\{\{(Tabela|Figura|Formula):([^}]+)\}\}"
                partes = re.split(padrao, no_filho.conteudo)
                
                is_continuacao_paragrafo = False
                
                for k, parte in enumerate(partes):
                    if k % 3 == 0: # É texto
                        if parte.strip():
                            paragrafos = parte.strip().split('\n')
                            for j, paragrafo_texto in enumerate(paragrafos):
                                if paragrafo_texto.strip():
                                    eh_novo_paragrafo = (j > 0 or not is_continuacao_paragrafo)
                                    self._adicionar_paragrafo_quebravel(paragrafo_texto, is_continuacao=(not eh_novo_paragrafo))
                                    is_continuacao_paragrafo = True 
                    elif k % 3 == 1: # É um bloco (Figura, etc.)
                        tipo, titulo = parte, partes[k+1]
                        
                        if tipo == "Tabela":
                            obj = next((t for t in self.doc_abnt.banco_tabelas if t.titulo == titulo), None)
                            if obj:
                                self.contador_tabelas += 1; obj.numero = self.contador_tabelas
                                altura = (len(obj.dados) * ALTURA_LINHA_TABELA) + (ALTURA_LEGENDA * 2) if obj.dados else (ALTURA_LEGENDA * 2)
                                self._adicionar_elemento_bloco(self._renderizar_tabela_html(obj), altura)
                                
                        elif tipo == "Figura":
                            obj = next((f for f in self.doc_abnt.banco_figuras if f.titulo == titulo), None)
                            if obj:
                                self.contador_figuras += 1; obj.numero = self.contador_figuras
                                caminho_img = obj.caminho_processado or obj.caminho_original
                                aspect_ratio = self._get_image_aspect_ratio(caminho_img) 
                                altura_imagem_cm = obj.largura_cm * aspect_ratio
                                altura_total_bloco = altura_imagem_cm + (ALTURA_LEGENDA * 2)
                                self._adicionar_elemento_bloco(self._renderizar_figura_html(obj), altura_total_bloco)
                                
                        elif tipo == "Formula":
                            obj = next((f for f in self.doc_abnt.banco_formulas if f.legenda == titulo), None)
                            if obj:
                                self.contador_formulas += 1; obj.numero = self.contador_formulas
                                
                                caminho_imagem = obj.caminho_svg
                                if not caminho_imagem or not os.path.exists(caminho_imagem):
                                    caminho_imagem = obj.caminho_processado_png
                                
                                aspect_ratio = self._get_svg_aspect_ratio(caminho_imagem)
                                altura_imagem_cm = obj.largura_cm * aspect_ratio
                                altura_imagem_cm += 0.5 
                                altura_total_bloco = altura_imagem_cm + ALTURA_LEGENDA
                                
                                self._adicionar_elemento_bloco(self._renderizar_formula_html(obj), altura_total_bloco)
                        
                        is_continuacao_paragrafo = False
                                
            self._renderizar_secoes_recursivamente_html(no_filho, f"{numero_completo}.")
    
    def _renderizar_capa_html(self, cfg, autores_html):
        cabecalho_html = self._renderizar_cabecalho_capa_html(cfg)
        return f"""
        <div>{cabecalho_html}</div>
        <div class="capa-conteudo-meio">
            <p class="bloco-texto-capa"><strong>{autores_html}</strong></p>
            <br><br><br><br>
            <p class="bloco-texto-capa"><strong>{self.doc_abnt.titulo.upper()}</strong></p>
        </div>
        <div><p>{cfg.cidade.upper()}</p><p>{cfg.ano}</p></div>"""

    def _renderizar_folha_rosto_html(self, cfg, autores_html):
        return f"""
        <div><p class="bloco-texto-capa" style="margin-top: 2cm;"><strong>{autores_html}</strong></p></div>
        <div class="capa-conteudo-meio">
            <p class="bloco-texto-capa"><strong>{self.doc_abnt.titulo.upper()}</strong></p><br><br><br>
            <p class="natureza">{cfg.tipo_trabalho} apresentado ao curso de {cfg.modalidade_curso} em {cfg.curso} da {cfg.instituicao}, como requisito parcial para a obtenção do título de {cfg.titulo_pretendido}.</p><br>
            <p class="natureza">Orientador(a): {self.doc_abnt.orientador}</p>
        </div>
        <div><p>{cfg.cidade.upper()}</p><p>{cfg.ano}</p></div>"""

    def _renderizar_resumo_html(self):
        return f"""<h1>RESUMO</h1><p class="resumo-paragrafo">{self.doc_abnt.resumo}</p><p><br></p><p class="resumo-titulo-palavras-chave">Palavras-chave: <span style="font-weight: normal;">{self.doc_abnt.palavras_chave.replace(';', '.')}.</span></p>"""

    def _renderizar_sumario_html(self):
        html = "<h1>SUMÁRIO</h1>"
        for entrada in self.entradas_sumario:
            titulo_sumario = entrada["titulo"].upper() if entrada["nivel"] == 1 or not entrada["numero"] else entrada["titulo"]
            numero_titulo = f'{entrada["numero"]} {titulo_sumario}' if entrada["numero"] else titulo_sumario
            html += f"""<p class="sumario-item sumario-nivel-{entrada['nivel']}"><a href="#{entrada['id_ancora']}"><span class="sumario-titulo">{numero_titulo}</span><span class="sumario-dots"></span><span class="sumario-pagina">{entrada['pagina']}</span></a></p>"""
        return html

    def _renderizar_tabela_html(self, tabela):
        classe_css = 'abnt' if tabela.estilo_borda == 'abnt' else ''
        html = f'<div><p class="legenda">Tabela {tabela.numero} – {tabela.titulo}</p><table class="{classe_css}" align="center">'
        if tabela.dados:
            html += '<thead><tr>'
            # Centraliza o cabeçalho
            for header in tabela.dados[0]: html += f'<th style="text-align: center;">{header}</th>'
            html += '</tr></thead><tbody>'
            for row in tabela.dados[1:]:
                html += '<tr>'
                # Centraliza o conteúdo (ou não) baseado na opção
                align_style = "text-align: center;" if tabela.centralizar_conteudo else "text-align: left;"
                for cell in row: html += f'<td style="{align_style}">{cell}</td>'
                html += '</tr>'
            html += '</tbody>'
        html += '</table>'
        if tabela.fonte: html += f'<p class="fonte">Fonte: {tabela.fonte}</p>'
        html += '</div>'
        return html

    def _renderizar_figura_html(self, figura):
        caminho_abs = os.path.abspath(figura.caminho_processado)
        url_local = f"file:///{caminho_abs.replace(os.path.sep, '/')}"
        html = f'<div><p class="legenda">Figura {figura.numero} – {figura.titulo}</p>'
        html += f'<img src="{url_local}" style="width: {figura.largura_cm}cm;">'
        if figura.fonte: html += f'<p class="fonte">Fonte: {figura.fonte}</p>'
        html += '</div>'
        return html

    def _renderizar_formula_html(self, formula):
        caminho_abs = os.path.abspath(formula.caminho_svg or formula.caminho_processado_png)
        if not (caminho_abs and os.path.exists(caminho_abs)):
            return '<div class="formula-container"><p style="color: red;">[ERRO: Imagem da fórmula não encontrada]</p></div>'
        url_local = f"file:///{caminho_abs.replace(os.path.sep, '/')}"
        html = f"""
        <div class="formula-container">
            <div style="display: flex; align-items: center; justify-content: space-between;">
                <div style="flex-grow: 1; text-align: center;">
                    <img src="{url_local}" alt="{formula.legenda}" style="display: inline-block; width: {formula.largura_cm}cm; max-width: 90%; height: auto; vertical-align: middle;">
                </div>
                <div style="min-width: 4em; text-align: right;">({formula.numero})</div>
            </div>
            <p class="formula-legenda">Equação {formula.numero} – {formula.legenda}</p>
        </div>"""
        return html