# gerador_preview.py
# Descrição: Versão com a correção do bug de cálculo de altura restante após adicionar títulos.

import os
import re
import math
from documento import DocumentoABNT, Capitulo

# --- CONSTANTES DE ESTIMATIVA DE ALTURA (EM CM) ---
# --- CORREÇÃO FINAL: Reduzido de 24.7 para 24.0 para criar um "buffer" inferior. ---
# Isso evita que o texto preencha a página até a borda.
ALTURA_CONTEUDO_PAGINA = 24.0
ALTURA_LINHA_TEXTO = 0.64 # (12pt / 72 * 2.54) * 1.5 = 0.635cm. Arredondado.
ALTURA_TITULO_SECAO = 1.5
ALTURA_LEGENDA = 1.2
ALTURA_LINHA_TABELA = 0.8
ALTURA_FORMULA_ESTIMADA = 4.0
CARACTERES_POR_LINHA = 70 # Estimativa pessimista

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
            altura_restante -= altura_necessaria # CORRIGIDO: Usar altura_necessaria

        def simular_paragrafo_quebravel(texto):
            nonlocal altura_restante
            if not texto.strip(): return
            num_linhas_total = math.ceil(len(texto.strip()) / CARACTERES_POR_LINHA)
            altura_total_paragrafo = num_linhas_total * ALTURA_LINHA_TEXTO
            while altura_total_paragrafo > 0:
                altura_que_cabe = math.floor(altura_restante / ALTURA_LINHA_TEXTO) * ALTURA_LINHA_TEXTO
                if altura_que_cabe <= 0:
                    simular_nova_pagina()
                    continue
                if altura_total_paragrafo <= altura_que_cabe:
                    altura_restante -= altura_total_paragrafo
                    altura_total_paragrafo = 0
                else:
                    altura_total_paragrafo -= altura_que_cabe
                    simular_nova_pagina()

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
                    for k, parte in enumerate(partes):
                        if k % 3 == 0:
                            if parte.strip():
                                paragrafos = parte.strip().split('\n')
                                for paragrafo_texto in paragrafos:
                                    if paragrafo_texto.strip():
                                        simular_paragrafo_quebravel(paragrafo_texto)
                        elif k % 3 == 1:
                            tipo, titulo = parte, partes[k+1]
                            if tipo == "Tabela":
                                obj = next((t for t in self.doc_abnt.banco_tabelas if t.titulo == titulo), None)
                                if obj and obj.dados: simular_adicao_bloco((len(obj.dados) * ALTURA_LINHA_TABELA) + (ALTURA_LEGENDA * 2))
                            elif tipo == "Figura":
                                obj = next((f for f in self.doc_abnt.banco_figuras if f.titulo == titulo), None)
                                if obj: simular_adicao_bloco((obj.largura_cm / 16 * 9) + (ALTURA_LEGENDA * 2))
                            elif tipo == "Formula":
                                simular_adicao_bloco(ALTURA_FORMULA_ESTIMADA + ALTURA_LEGENDA)
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

    def _adicionar_paragrafo_quebravel(self, texto_paragrafo):
        self.classe_pagina_atual = 'pagina'
        if not self.conteudo_pagina_atual:
            self.conteudo_pagina_atual.append(self.classe_pagina_atual)

        texto_restante = texto_paragrafo.strip()
        is_continuacao = False

        while texto_restante:
            if self.altura_restante < ALTURA_LINHA_TEXTO * 2:
                self._nova_pagina()
                is_continuacao = True
                continue

            linhas_que_cabem = math.floor(self.altura_restante / ALTURA_LINHA_TEXTO)
            caracteres_que_cabem = linhas_que_cabem * CARACTERES_POR_LINHA
            
            if not is_continuacao:
                caracteres_que_cabem -= 10 

            texto_para_pagina_atual: str
            
            if len(texto_restante) > caracteres_que_cabem:
                ponto_quebra = texto_restante.rfind(' ', 0, caracteres_que_cabem)
                if ponto_quebra == -1 or ponto_quebra < caracteres_que_cabem * 0.8:
                    ponto_quebra = caracteres_que_cabem
                
                texto_para_pagina_atual = texto_restante[:ponto_quebra].rstrip()
                texto_restante = texto_restante[ponto_quebra:].lstrip()
            else:
                texto_para_pagina_atual = texto_restante
                texto_restante = ""

            base_class = "corpo-texto" if not is_continuacao else "paragrafo-continuado"
            self.conteudo_pagina_atual.append(f'<p class="{base_class}">{texto_para_pagina_atual}</p>')
            
            altura_consumida = math.ceil(len(texto_para_pagina_atual) / CARACTERES_POR_LINHA) * ALTURA_LINHA_TEXTO
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
                overflow-wrap: break-word; /* Padrão */
                word-wrap: break-word;     /* Compatibilidade */
                word-break: break-all;     /* Força a quebra de palavras longas */
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
                display: flex; flex-direction: column; justify-content: center;
            }
            .brasoes-lado-a-lado {
                flex-direction: row; justify-content: space-between; align-items: center;
            }
            .brasoes-lado-a-lado .instituicao-central { flex-grow: 1; padding: 0 1cm; }
            .brasao-container img { display: inline-block; margin: 0; max-height: 3.5cm; }
            .brasao-centralizado { text-align: center; }
            .brasao-esquerda { align-self: flex-start; text-align: left; }
            .brasao-direita { align-self: flex-end; text-align: right; }
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

    def _renderizar_cabecalho_capa_html(self, cfg):
        posicao = cfg.posicao_brasao
        instituicao_html = f'<p class="bloco-texto-capa"><strong>{cfg.instituicao.upper()}</strong></p>'
        if posicao == "Nenhum": return f'<div class="brasao-container">{instituicao_html}</div>'
        if posicao == "Lados (Esquerdo e Direito)":
            html_esq = "<div></div>"
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                url_esq = f"file:///{os.path.abspath(cfg.caminho_brasao_esquerdo_processado).replace(os.path.sep, '/')}"
                html_esq = f'<div><img src="{url_esq}" style="width:{cfg.tamanho_brasao_esquerdo_cm}cm;"></div>'
            html_dir = "<div></div>"
            if cfg.caminho_brasao_direito_processado and os.path.exists(cfg.caminho_brasao_direito_processado):
                url_dir = f"file:///{os.path.abspath(cfg.caminho_brasao_direito_processado).replace(os.path.sep, '/')}"
                html_dir = f'<div><img src="{url_dir}" style="width:{cfg.tamanho_brasao_direito_cm}cm;"></div>'
            instituicao_div = f'<div class="instituicao-central">{instituicao_html}</div>'
            return f'<div class="brasao-container brasoes-lado-a-lado">{html_esq}{instituicao_div}{html_dir}</div>'
        brasao_html = ""
        classe_container = "brasao-container"
        if posicao == "Acima do Nome":
            classe_container += " brasao-centralizado"
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                url = f"file:///{os.path.abspath(cfg.caminho_brasao_esquerdo_processado).replace(os.path.sep, '/')}"
                brasao_html = f'<img src="{url}" style="width:{cfg.tamanho_brasao_esquerdo_cm}cm; margin-bottom: 1cm;">'
        elif posicao == "Apenas Esquerdo":
            classe_container += " brasao-esquerda"
            if cfg.caminho_brasao_esquerdo_processado and os.path.exists(cfg.caminho_brasao_esquerdo_processado):
                url = f"file:///{os.path.abspath(cfg.caminho_brasao_esquerdo_processado).replace(os.path.sep, '/')}"
                brasao_html = f'<img src="{url}" style="width:{cfg.tamanho_brasao_esquerdo_cm}cm; margin-bottom: 1cm;">'
        elif posicao == "Apenas Direito":
            classe_container += " brasao-direita"
            if cfg.caminho_brasao_direito_processado and os.path.exists(cfg.caminho_brasao_direito_processado):
                url = f"file:///{os.path.abspath(cfg.caminho_brasao_direito_processado).replace(os.path.sep, '/')}"
                brasao_html = f'<img src="{url}" style="width:{cfg.tamanho_brasao_direito_cm}cm; margin-bottom: 1cm;">'
        return f'<div class="{classe_container}">{brasao_html}{instituicao_html}</div>'

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
                for k, parte in enumerate(partes):
                    if k % 3 == 0:
                        if parte.strip():
                            paragrafos = parte.strip().split('\n')
                            for paragrafo_texto in paragrafos:
                                if paragrafo_texto.strip(): self._adicionar_paragrafo_quebravel(paragrafo_texto)
                    elif k % 3 == 1:
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
                                altura = (obj.largura_cm / 16 * 9) + (ALTURA_LEGENDA * 2)
                                self._adicionar_elemento_bloco(self._renderizar_figura_html(obj), altura)
                        elif tipo == "Formula":
                            obj = next((f for f in self.doc_abnt.banco_formulas if f.legenda == titulo), None)
                            if obj:
                                self.contador_formulas += 1; obj.numero = self.contador_formulas
                                self._adicionar_elemento_bloco(self._renderizar_formula_html(obj), ALTURA_FORMULA_ESTIMADA + ALTURA_LEGENDA)
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
            for header in tabela.dados[0]: html += f'<th>{header}</th>'
            html += '</tr></thead><tbody>'
            for row in tabela.dados[1:]:
                html += '<tr>'
                for cell in row: html += f'<td>{cell}</td>'
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