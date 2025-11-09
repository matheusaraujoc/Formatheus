# Documentação de Arquitetura: Formatheus

## 1. Visão Geral da Aplicação

O **Formatheus** é uma aplicação desktop híbrida, construída em Python (com PySide6), projetada para ser um assistente completo na criação de trabalhos acadêmicos (TCCs, Artigos, etc.) formatados segundo as normas ABNT.

O programa gerencia todo o ciclo de vida do documento, desde a estruturação de capítulos, passando pela edição de texto, gerenciamento de ativos (figuras, tabelas, fórmulas), até a geração de dois produtos finais:

1.  Uma **Pré-visualização (Preview) em HTML** em tempo real, que simula a paginação e o layout A4.
2.  Um **Documento `.docx`** final, pronto para impressão, com sumário automático e formatação completa.

---

## 2. Arquitetura Tecnológica (Stack)

A aplicação utiliza uma combinação de tecnologias para atingir seus objetivos:

* **Interface Gráfica (GUI):** `PySide6` (Qt for Python).
* **Geração de Documento (Backend):** `python-docx` (para criar o `.docx`).
* **Processamento de Imagem (Backend):** `PIL (Pillow)` (para medição de texto e processamento de imagens).
* **Renderização Híbrida (GUI/Web):** `PySide6.QtWebEngineView` (um navegador Chromium embarcado para o preview HTML).
* **Renderização de Fórmulas (Web):** `MathJax` (uma biblioteca JavaScript externa) carregada no `QtWebEngineView`.
* **Manipulação de XML (Baixo Nível):** `python-docx.oxml` (para bordas de tabela e sumário) e `pywin32` (para atualização do sumário).
* **Formato de Dados/Salvamento:** `JSON` (para metadados), `zipfile` (para o formato `.abnf`), e `tempfile` (para operações seguras).

---

## 3. Arquitetura da Aplicação (Visão de Módulo)

O programa é dividido em quatro grandes áreas lógicas que se comunicam entre si:



### 1. O "Cérebro" (Modelos de Dados)
*Define a *estrutura* de tudo o que pode ser salvo.*
* **Arquivos:** `documento.py`, `formula.py`, `referencia.py`, `modelos_trabalho.py`
* **Responsabilidade:** Define as classes (`@dataclass`) que armazenam os dados em memória (ex: `DocumentoABNT`, `Capitulo`, `Figura`). Não possui interface ou lógica de geração.

### 2. A "Interface" (GUI / Frontend)
*Permite ao usuário *interagir* com os dados.*
* **Arquivos:** `main_app.py`, `tela_inicial.py`, `aba_conteudo.py`, `dialogo_brasao.py`, `dialogo_figura.py`, `dialogo_tabela.py`, `dialogs.py`, `DialogoFormula.py`, `latex_renderer.html`
* **Responsabilidade:** Criar todas as janelas, botões e campos de texto. Lê os dados do "Cérebro" para exibi-los e salva as alterações do usuário de volta no "Cérebro".

### 3. Os "Motores" (Geradores / Backend)
*Traduz os dados do "Cérebro" em *produtos finais*.*
* **Arquivos:** `gerador_docx.py`, `gerador_preview.py`, `normas_abnt.py`
* **Responsabilidade:** Leem o `DocumentoABNT` e o "Livro de Regras" (`normas_abnt.py`) para produzir os arquivos finais: o `.docx` e o HTML de pré-visualização.

### 4. Os "Serviços" (Gerenciadores / Utilitários)
*Fornecem *suporte* à aplicação.*
* **Arquivos:** `gerenciador_projeto.py`, `gerenciador_config.py`, `gerenciador_recuperacao.py`, `stylesheet.py`
* **Responsabilidade:** Lidam com tarefas de infraestrutura: salvar e carregar o arquivo `.abnf` (projeto), gerenciar o auto-save (recuperação), salvar as configurações do usuário (config) e definir o tema visual (stylesheet).

---

## 4. Fluxos de Dados Principais

A aplicação opera com base em fluxos de dados claros que conectam os módulos de arquitetura:

1.  **Inicialização:**
    * `main_app.py` inicia.
    * Ele chama o `gerenciador_recuperacao.py` para verificar se há arquivos `.recovery`.
    * **Se SIM:** O `DialogoRecuperacao` (de `dialogs.py`) é exibido.
    * **Se NÃO:** A `tela_inicial.py` é exibida.
    * A `TelaInicial` retorna uma *ação* (ex: "abrir") e *dados* (ex: "caminho/do/arquivo.abnf") para o `main_app.py`.

2.  **Carregamento de Projeto (`.abnf`):**
    * `main_app.py` chama `gerenciador_projeto.carregar_projeto(caminho)`.
    * `gerenciador_projeto` (usando `zipfile`) extrai o `.zip` para uma pasta temporária.
    * Ele lê o `documento.json` e usa `DocumentoABNT.from_dict()` (de `documento.py`) para recriar o objeto de dados na memória.
    * Ele "reidrata" os caminhos das imagens (ex: `brasoes/img.png`) para caminhos absolutos (ex: `C:\Temp\...\brasoes\img.png`).
    * `main_app.py` recebe o objeto `DocumentoABNT` e chama `_popular_ui_com_documento` para preencher a interface.

3.  **Ciclo de Edição (O "Loop" Principal):**
    * O usuário digita no `QTextEdit` (em `aba_conteudo.py`).
    * O sinal `textChanged` é emitido.
    * A função `_salvar_conteudo_capitulo` é chamada **a cada tecla**, salvando o texto da *View* (o `QTextEdit`) de volta no *Model* (o `documento.capitulo.conteudo`).
    * `main_app.py` detecta essa mudança via `_marcar_modificado` e inicia o `preview_update_timer` (o "debounce" de 750ms).

4.  **Ciclo de Pré-visualização:**
    * O `preview_update_timer` (750ms) dispara, chamando `_atualizar_preview` no `main_app.py`.
    * `_atualizar_preview` chama `gerador_preview.gerar_html()`.
    * O `gerador_preview.py` lê o objeto `DocumentoABNT` (que está sempre atualizado graças ao ciclo de edição) e:
        1.  Chama `_estimar_paginacao_e_coletar_sumario` (a "bola de cristal" que usa `Pillow` para medir texto e imagens) para prever os números de página do sumário.
        2.  Chama `_renderizar_secoes_recursivamente_html` para construir o HTML, usando a medição exata para quebrar o texto (`_adicionar_paragrafo_quebravel`).
    * `main_app.py` recebe a string HTML e a insere no `QWebEngineView` (`self.preview_display.setHtml(...)`).

5.  **Salvamento do Projeto (`.abnf`):**
    * O usuário clica em "Salvar" (`main_app._salvar_projeto`).
    * `main_app.py` chama `_sincronizar_modelo_com_ui` (para salvar os dados da aba "Geral") e `aba_conteudo.sincronizar_conteudo_pendente` (redundante, mas seguro).
    * `main_app.py` chama `gerenciador_projeto.salvar_projeto(self.documento, ...)`.
    * `gerenciador_projeto` (usando `copy.deepcopy`) cria uma cópia segura do `documento`.
    * Ele reescreve os caminhos das imagens para caminhos *relativos* (ex: "imagens/fig1.png").
    * Ele chama `documento.to_dict()` e salva o `documento.json` em uma pasta temporária.
    * Ele copia (`shutil.copy2`) os arquivos de imagem (`_imagens_processadas`, `_brasoes_processados`) para a pasta temporária.
    * Ele compacta (`shutil.make_archive`) a pasta temporária em um `.zip` e a renomeia para `.abnf`.

6.  **Geração do Documento Final (`.docx`):**
    * O usuário clica em "Gerar Documento .docx Final".
    * `main_app.py` chama `_gerar_documento_final`.
    * Uma instância de `GeradorDOCX(self.documento)` é criada.
    * `gerador_docx.py` (com a ajuda do `normas_abnt.py`) constrói o arquivo `.docx` na memória.
    * **Estratégia do Sumário:** O `gerador_docx` salva o arquivo e, em seguida, chama `_atualizar_sumario_com_word`.
    * `pywin32` abre o MS Word em segundo plano, atualiza o sumário (TOC) e salva o arquivo novamente.

---
---

## 5. Análise Detalhada dos Módulos

A seguir, a análise detalhada de cada módulo, agrupada por sua responsabilidade arquitetônica.

### 5.1. O "Cérebro" (Modelos de Dados)

#### `documento.py`
* **Propósito:** É o **"cérebro" (ou "esquema") de todo o projeto**. Define a **estrutura de dados** que armazena *tudo* o que o usuário insere no programa. É a "fonte da verdade".
* **Tecnologias:** `dataclasses`, `typing`, `datetime`.
* **Arquitetura:**
    * **`dataclasses`:** Define os "modelos" (`Tabela`, `Figura`, `Configuracoes`, `Autor`, `Capitulo`). O uso de `@dataclass` elimina a necessidade de `__init__` manuais, tornando o código limpo e legível.
    * **`Capitulo` (A Árvore):** É a estrutura de dados mais importante. É uma **estrutura em árvore recursiva** (`filhos: List['Capitulo']`), permitindo a hierarquia de seções.
        * **Estratégia (Referência Fraca):** O campo `pai: ... repr=False` é uma estratégia essencial para evitar um *loop infinito de recursão* quando o objeto é impresso ou depurado.
    * **`DocumentoABNT` (O Agregador):** A classe principal que "agrega" todos os outros modelos (ex: `self.configuracoes = Configuracoes()`, `self.estrutura_textual = Capitulo(...)`).
    * **Design de "Banco de Dados Central":** As `banco_tabelas` e `banco_figuras` são listas globais no `DocumentoABNT`. Esta é uma decisão de design crucial que permite ao usuário **reutilizar** o mesmo ativo (ex: `{{Figura:Img1}}`) em múltiplos capítulos.
    * **Serialização (`to_dict`, `from_dict`):**
        * **Propósito:** "Traduzem" o objeto Python de/para um dicionário simples que pode ser salvo em JSON pelo `gerenciador_projeto.py`.
        * **Estratégia:** `to_dict` usa `.__dict__` das `dataclasses` como um atalho rápido de serialização.
        * **Lógica Customizada:** `from_dict` usa uma verificação `if/elif` no campo `tipo_ref` (que foi salvo manualmente em `to_dict`) para reconstruir as classes de referência corretas (polimorfismo na desserialização).
* **Gambiarras e Pontos de Atenção:**
    * **Dependências Cegas:** O arquivo depende estruturalmente de `referencia.py` e `formula.py`. Se essas `dataclasses` mudarem, `documento.py` pode quebrar.
    * **Deserialização Frágil:** O `from_dict` usa `ref_data.pop('tipo', None)`. Isso é uma pequena "gambiarra" para limpar dados antigos, tornando o carregamento mais robusto contra arquivos de salvamento de versões anteriores.

---

#### `formula.py`
* **Propósito:** Um `dataclass` focado que define a estrutura de uma `Formula`.
* **Arquitetura:**
    * **`legenda`:** O identificador legível (usado no marcador `{{Formula:...}}`).
    * **`codigo_latex`:** O código-fonte (`\frac...`) para re-edição.
    * **`caminho_svg`:** O arquivo vetorial de alta qualidade usado pelo `gerador_preview.py` (que renderiza SVGs bem).
    * **`caminho_processado_png`:** O arquivo rasterizado usado pelo `gerador_docx.py` (para máxima compatibilidade com o Word).
    * **Decisão de Design (SVG vs PNG):** Manter os dois caminhos é uma estratégia inteligente, garantindo a **melhor qualidade no preview** (SVG) e a **maior compatibilidade no arquivo final** (PNG).
* **Gambiarras e Pontos de Atenção:**
    * **Valor Padrão do LaTeX:** O valor padrão (fórmula de Bhaskara) é uma estratégia de usabilidade para mostrar um exemplo ao usuário quando ele cria uma nova fórmula.

---

#### `referencia.py`
* **Propósito:** Define a estrutura e a lógica de formatação para referências bibliográficas (Livro, Artigo, Site) seguindo as normas ABNT.
* **Arquitetura:**
    * **Padrão de Herança (OOP):** Usa uma classe base `Referencia` (que define a interface comum: `autores`, `titulo`, `ano`) e classes filhas (`Livro`, `Artigo`, `Site`) que herdam dela e sobrescrevem o método `formatar()`.
    * **`formatar_autores` (A Estratégia do Sobrenome):** Lógica que assume separador `;` e que o sobrenome é a *última* palavra (ex: `Matheus da Silva` -> `SILVA, Matheus da`).
    * **`get_chave_ordenacao` (A "Gambiarra" de Ordenação):** Pega o sobrenome do *primeiro* autor para a ordenação alfabética. "Gambiarra" de fallback: se não houver autor, usa o `titulo`, como manda a ABNT.
    * **`formatar()` (A Estratégia do Negrito):** Insere marcadores `**` (Markdown) no texto. O `gerador_docx.py` e o `gerador_preview.py` são responsáveis por encontrar esses marcadores e aplicar o negrito real (`<strong>` ou `run.bold = True`).
* **Gambiarras e Pontos de Atenção:**
    * **Uso Incomum de `@dataclass`:** As classes filhas são marcadas como `@dataclass` mas sobrescrevem o `__init__`, anulando o principal benefício do decorador. O código é funcional, mas não idiomático.
    * **Limitação da Estratégia do Sobrenome:** A lógica de `formatar_autores` falha em sobrenomes compostos (ex: "Castelo Branco") ou com sufixos (ex: "Filho", "Neto").

---

#### `modelos_trabalho.py`
* **Propósito:** Um módulo de configuração "fixa" (hard-coded) que serve como banco de dados para os *templates* de capítulos.
* **Arquitetura:**
    * **`ESTRUTURAS_MODELO` (Configuration as Code):** A "fonte da verdade" é um grande dicionário Python.
    * **Encapsulamento:** Usa *getters* (`get_nomes_modelos`, `get_estrutura_por_nome`) para desacoplar a UI dos dados.
    * **Estratégia (Programação Defensiva):** `get_estrutura_por_nome` usa `.get(nome_modelo, [])`. Se um modelo não for encontrado, ele retorna uma lista vazia em vez de travar o programa.
* **Gambiarras e Pontos de Atenção:**
    * **A "Gambiarra" Central (Inflexibilidade):** Os modelos são "fixos" no código. A única forma de adicionar um novo modelo é o *desenvolvedor* editar este arquivo. O usuário final não pode criar seus próprios modelos.

---
---

### 5.2. A "Interface" (GUI / Frontend)

Os componentes visuais que o usuário vê e com os quais interage.

---

#### `main_app.py`
* **Propósito:** O **"Maestro"** da orquestra. É o arquivo principal (`if __name__ == '__main__':`) que inicializa e conecta todos os outros módulos. A classe `ABNTHelperApp` é a janela principal.
* **Arquitetura:**
    * **`if __name__ == '__main__':` (O Lançador):** Contém a **Máquina de Estados de Inicialização**. Ele primeiro verifica o `gerenciador_recuperacao` e decide se mostra o `DialogoRecuperacao` ou a `TelaInicial`.
    * **Estratégia (O Loop `while True:`):** Este loop envolve a inicialização do app (`app.exec()`). Ele permite que o app "reinicie" (definindo `self.wants_to_restart = True`) e volte para a `TelaInicial` sem fechar o processo do Python.
    * **Gerenciamento de Estado (Flags):**
        * `self.modificado`: A flag "sujo" (dirty bit) que adiciona o `*` ao título da janela e pergunta "Deseja salvar?" ao fechar (`closeEvent`).
        * `self._populando_ui`: A **"gambiarra" de bloqueio de sinal** mais importante. É definida como `True` ao carregar um projeto para impedir que os sinais `textChanged` (disparados por `setText`) marquem o projeto como modificado (`_marcar_modificado`).
    * **Estratégia de UI (`_reconfigurar_layout`):** Permite ao usuário alternar entre o preview "Lado-a-Lado" (em um `QSplitter`) e "Aba" (em um `QTabWidget`), *reparentando* dinamicamente o `self.preview_container`.
    * **Estratégia de Desempenho (Timers):**
        * `preview_update_timer`: Um "debounce" de 750ms. O preview só atualiza 750ms *depois* que o usuário para de digitar.
        * `autosave_timer`: Um timer periódico que dispara o `_auto_salvar_recuperacao`.
    * **Estratégia (Persistência do Scroll):** Usa uma coreografia Python/JavaScript (`window.scrollY` e `window.scrollTo`) para salvar e restaurar a posição do scroll do `QWebEngineView` a cada atualização.
* **Gambiarras e Pontos de Atenção:**
    * **`os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'`:** Uma "gambiarra" de depuração que expõe o `QWebEngineView` em `http://127.0.0.1:9222` para depuração no Chrome.

---

#### `tela_inicial.py`
* **Propósito:** O **"Portão de Entrada"** do app. É um `QDialog` que atua como o "hub" de navegação, permitindo ao usuário criar, abrir ou recuperar um projeto.
* **Arquitetura:**
    * **Estratégia do Cartão (`ProjetoRecenteItem`):** Um `QListWidget` não pode ser estilizado de forma complexa. A solução é criar um `QWidget` (`ProjetoRecenteItem`) separado com o layout do "cartão". O `QListWidgetItem` é usado como um *container* vazio, e `self.lista_recentes.setItemWidget(item, item_widget)` é chamado para "colocar" o widget customizado dentro do item da lista.
    * **Seleção por ID (`setObjectName`):** O `ProjetoRecenteItem` recebe um ID de objeto. Isso permite que o `stylesheet.py` o estilize com CSS (`QWidget#ProjetoRecenteItem {...}`), criando o visual de cartão.
    * **Lógica de Retorno (`self.resultado`):** Este diálogo não *faz* nada. Ele apenas armazena a escolha do usuário em `self.resultado` (ex: `("novo", "TCC")`) e chama `self.accept()`. O `main_app.py` então captura esse resultado.
    * **Estratégia do `lambda`:** O loop que cria os botões de modelo usa `lambda m=nome_modelo: ...`. Isso é uma estratégia clássica do Python para "capturar" o valor da variável `nome_modelo` no momento da criação do lambda, evitando um bug comum de closure em loops.
    * **Programação Defensiva:** `on_item_recente_clicado` verifica se o arquivo (`os.path.exists`) ainda existe. Se não, ele informa o usuário e limpa a entrada "morta" da lista de recentes.

---

#### `aba_conteudo.py`
* **Propósito:** O **"coração pulsante"** da UI. É o painel principal de edição (árvore de capítulos, editor de texto, bancos de ativos).
* **Arquitetura:**
    * **Sincronização em Tempo Real:** `self.editor_capitulo.textChanged.connect(...)` salva o texto no `documento.capitulo.conteudo` a *cada tecla digitada*. Isso mantém o modelo sempre atualizado, pronto para o auto-save ou preview.
    * **Sistema de Marcadores (Placeholders):** A estratégia central de design. O editor de texto é "burro"; ele não renderiza nada. Ele apenas insere marcadores (ex: `{{Figura:Img1}}`, `{{QUEBRA_PAGINA}}`). Os geradores (`gerador_docx` e `gerador_preview`) fazem o trabalho de substituí-los.
* **"Gambiarras" e Estratégias:**
    * **"Gambiarra" (Sincronização Invertida):** A função `_sincronizar_modelo_com_arvore` (usada no "Arrastar e Soltar") é uma "gambiarra" eficaz. Em vez de mover itens no *modelo* de dados (complicado), ela deixa o `QTreeWidget` (a *view*) fazer a reorganização visual e, em seguida, **recria** o modelo de dados do zero com base na nova ordem da *view*.
    * **Estratégia (Filtro por Regex):** O filtro "Mostrar apenas do tópico atual" (`atualizar_bancos_visuais`) funciona lendo o texto do `editor_capitulo` e usando `re.findall(r"\{\{Tabela:([^}]+)\}\}", ...)` para ver quais marcadores estão em uso.
    * **Estratégia (Flag de Bloqueio):** `self._carregando_capitulo` é uma flag de "trava" (mutex) essencial. Ela impede que o sinal `textChanged` (disparado por `setPlainText`) chame a função de salvar (`_salvar_conteudo_capitulo`) enquanto o programa ainda está *carregando* o texto, evitando um loop infinito.

---

#### `dialogo_brasao.py` e `dialogo_figura.py`
* **Propósito:** Diálogos "gêmeos" que fornecem um editor de imagem (corte retangular e poligonal) para os ativos de Brasão e Figura.
* **Arquitetura (Classe `CropLabel`):**
    * **Padrão "Máquina de Estados"**: O `CropLabel` usa `self.mode` ('rect' ou 'poly') para mudar seu comportamento em `mousePressEvent` e `mouseMoveEvent`.
    * **Estratégia 1 (Tradução de Coordenadas):** A função `get_crop_coords()` é a "tradutora" que converte as coordenadas da seleção na tela (imagem *escalada*) para as coordenadas da imagem *original* (em disco), usando um `self.scale_factor`.
    * **Estratégia 2 (Overlay Negativo):** O `paintEvent` usa `QPainterPath` e `Qt.FillRule.OddEvenFill` para "cavar um buraco" na sobreposição escura, em vez de tentar desenhar ao redor dela.
    * **Estratégia 3 (Linha Elástica):** `setMouseTracking(True)` permite ao `mouseMoveEvent` desenhar a linha do polígono que segue o cursor.
* **Arquitetura (Diálogo):**
    * **Backend com `PIL`:** Quando o usuário clica "OK", a função `_processar_imagem` usa a biblioteca `PIL`.
    * **Estratégia (Corte Poligonal):** Como o `PIL` não corta polígonos, o código usa a técnica de **máscara de alfa**: cria uma máscara preta (`Image.new("L")`), desenha um polígono branco (`ImageDraw.polygon`) nela e, em seguida, usa `img.paste(mask=mask)` para colar apenas a área poligonal em uma nova imagem transparente.
* **Gambiarras e Pontos de Atenção:**
    * **"Gambiarra" (Duplicação de Código / Violação de DRY):** A classe `CropLabel` (200+ linhas) está **duplicada** em ambos os arquivos. Este é o maior *débito técnico* do projeto. Se um bug for encontrado no `CropLabel`, ele precisa ser corrigido em dois lugares.

---

#### `dialogo_tabela.py`
* **Propósito:** Um diálogo CRUD (Criar/Ler/Atualizar/Deletar) para gerenciar uma `Tabela`.
* **Arquitetura:**
    * **`QTableWidget`:** O componente central. É uma "gambiarra" de design eficaz: em vez de implementar um `QTableView` (complexo, com modelo de dados), o código usa o `QTableWidget` (simples, como uma planilha) e sincroniza os dados manualmente.
    * **Padrão "Preenchimento e Coleta":**
        1.  `__init__` (Preenchimento): Lê `self.tabela.dados` e preenche o `QTableWidget`.
        2.  `get_dados_tabela` (Coleta): Lê o `QTableWidget` (célula por célula) e reconstrói o `self.tabela.dados` quando o usuário clica "OK".
    * **Validação na Saída (`accept`):** Sobrescreve `accept()` para validar se o título está vazio *antes* de permitir que a janela feche.

---

#### `DialogoFormula.py` e `latex_renderer.html`
* **Propósito:** A solução **híbrida (Desktop + Web)** para renderizar fórmulas LaTeX.
* **Arquitetura (Coreografia Python <-> JS):**
    1.  **`DialogoFormula` (Python):** Carrega o `latex_renderer.html` em um `QWebEngineView` (o navegador).
    2.  **`latex_renderer.html` (JS):** Carrega a biblioteca `MathJax` de um CDN.
    3.  **Usuário digita** no `<textarea>`. O JavaScript (`debounceRender`) espera 500ms e chama `renderLatex()`, que usa o `MathJax` para renderizar a fórmula no `div#preview`.
    4.  **Usuário clica "OK"** (Python).
    5.  **Python -> JS:** `DialogoFormula` chama `window.getEditorContent()` no JavaScript.
    6.  **JS -> Python:** O JS retorna o código LaTeX, que é salvo em `self.formula.codigo_latex`.
    7.  **Python -> JS:** `DialogoFormula` chama `window.prepareAndTriggerDownload()`.
    8.  **Estratégia (Download Falso):** O JavaScript (`latex_renderer.html`) converte a fórmula em SVG, **adiciona o `xmlns`** (uma "gambiarra" crítica, pois o MathJax não o inclui) e simula o clique em um link de download.
    9.  **Python (Interceptação):** O `QWebEngineProfile` (Python) intercepta esse "download" (`downloadRequested`).
    10. **`_handle_automatic_download` (Python):** O Python salva o arquivo SVG em uma pasta temporária.
    11. **Conversão Nativa:** `_converter_svg_para_png` (Python) usa `QSvgRenderer` e `QPainter` (Qt nativo) para converter o SVG em um PNG de alta qualidade.
    12. **Finalização:** Os caminhos para *ambos* os arquivos (`.svg` e `.png`) são salvos no objeto `Formula`.
* **Gambiarras e Pontos de Atenção:**
    * **Escapando o LaTeX (`_on_load_finished`):** `codigo_js_escapado = self.formula.codigo_latex.replace("\\", "\\\\")...` é uma "gambiarra" frágil para injetar o código LaTeX em uma string JavaScript.
    * **Download Falso:** A transferência de arquivos via simulação de download é uma estratégia brilhante para contornar a dificuldade de passar dados binários do JS de volta para o Python.

---

#### `dialogs.py`
* **Propósito:** Módulo utilitário para diálogos *simples* e *reutilizáveis* (Recuperação e Referências).
* **`ReferenciaDialog`:**
    * **Estratégia (Formulário Dinâmico):** `update_form_visibility` usa dicionários de widgets (`self.campos_livro`) para esconder e reexibir campos dinamicamente conforme o `QComboBox` ("Livro", "Artigo", "Site") é alterado.
* **`DialogoRecuperacao`:**
    * **Estratégia (Armazenamento de Dados):** Armazena o dicionário `arq_info` (com todos os metadados) diretamente no `QListWidgetItem` (`item.setData(...)`), tornando trivial a recuperação dos dados.

---
---

### 5.3. Os "Motores" (Geradores / Backend)

Os módulos que transformam o "Cérebro" em produtos finais.

---

#### `normas_abnt.py`
* **Propósito:** O **"Livro de Regras" (hard-coded)**. Centraliza todas as constantes de formatação ABNT (margens, fontes, recuos) e as funções que as aplicam no `python-docx`.
* **Arquitetura:**
    * **"A "Gambiarra" Central (Regras Fixas):** A maior decisão de design é que todas as regras (`self.MARGEM_SUPERIOR = Cm(3)`) são "fixas" no `__init__`. O usuário não pode personalizar as margens. O programa é um *Formatador ABNT*, não um *Formatador Genérico*.
    * **Configuração de Estilos Globais:** `configurar_pagina_e_estilos` redefine o estilo `doc.styles['Normal']` (a base de tudo) e cria estilos customizados (`CitacaoLonga`, `Referencias`).
    * **"Gambiarra" (Correção de Cor do Word):** O loop `for i in range(1, 10): ...` é uma "gambiarra" defensiva que força a cor dos estilos `Heading` (Título) para preto, sobrescrevendo o padrão azul do Word.
    * **Estratégia (OXML para Bordas):** `aplicar_estilo_tabela_abnt` é a estratégia mais avançada. Como `python-docx` não suporta bordas ABNT (só superior/inferior), o código "desce" para o nível XML (`OxmlElement`) e escreve manualmente as regras de borda (`<w:top val="single">`, `<w:left val="nil">`).

---

#### `gerador_docx.py`
* **Propósito:** A **"Linha de Produção Industrial"**. Lê o `DocumentoABNT` e constrói o arquivo `.docx` final.
* **Arquitetura:**
    * **Padrão "Motor de Seções":** `_gerar_trabalho_academico` usa `doc.add_section()` e `footer.is_linked_to_previous = False` para criar as seções isoladas (Capa, Folha de Rosto, Resumo) que não têm números de página. A Seção 4 (Conteúdo) é onde `_set_page_numbering` é chamado para iniciar a numeração.
    * **Parser de Conteúdo (`_renderizar_secoes_recursivamente`):**
        * **Regex:** Usa o regex `r"\{\{(?:(Tabela...)...|(QUEBRA...))\}\}"` para encontrar *todos* os marcadores.
        * **Estratégia de Iteração:** Usa o loop `while idx < len(partes): ... idx += 4` para iterar sobre a lista achatada de `re.split` (Texto, Grupo1, Grupo2, Grupo3).
        * **Lógica de Quebra de Página:** Implementa a regra ABNT `if nivel_titulo == 1 and i > 1: self.doc.add_page_break()`.
    * **Estratégia do Sumário (`adicionar_sumario` e `_atualizar_sumario_com_word`):**
        * **A "Gambiarra" do `pywin32`:** Esta é a "gambiarra" mais frágil de todo o sistema.
        1.  `adicionar_sumario` (Python) usa `OxmlElement` para inserir o *placeholder* do Sumário (`TOC ...`).
        2.  `python-docx` **não pode** preencher este sumário.
        3.  `_atualizar_sumario_com_word` (Python) usa `win32com.client` para abrir o MS Word *real* em segundo plano, carregar o `.docx`, forçar a atualização do sumário (`doc.TablesOfContents(1).Update()`) e salvar.
        * **Risco:** Isso só funciona em Windows e exige que o MS Word esteja instalado. O código se protege com `if not WIN32_AVAILABLE:`.
* **Gambiarras e Pontos de Atenção:**
    * **Estratégia do Layout da Fórmula:** `_renderizar_formula` usa **Tab Stops (Paradas de Tabulação)** para centralizar a imagem da fórmula e alinhar o número (`(1)`) à direita na mesma linha.

---

#### `gerador_preview.py`
* **Propósito:** O **"Simulador Visual"**. Cria um HTML/CSS que *imita* o `gerador_docx.py` para fornecer um preview em tempo real. Este é o módulo mais complexo do projeto.
* **Arquitetura (Simulação vs. Renderização):**
    1.  **Fase 1: Simulação (`_estimar_paginacao_e_coletar_sumario`):**
        * É uma "bola de cristal" que *prevê* a altura de todo o documento para gerar o Sumário.
        * **Estratégia (Medição Exata):** Esta é a estratégia central. Ele **não usa mais `CARACTERES_POR_LINHA`**.
        * **Medição de Texto:** `_calcular_altura_paragrafo` usa `ImageFont.truetype("times.ttf", ...)` e `font_medidor.getbbox(palavra)` para **medir a largura exata de cada palavra**. Ele simula as quebras de linha com precisão de pixel.
        * **Medição de Figura:** `_get_image_aspect_ratio` usa `Image.open` para ler as dimensões reais de JPG/PNG e calcular a altura de exibição.
        * **Medição de Fórmula:** `_get_svg_aspect_ratio` usa `re.search` para ler os atributos `viewBox` do arquivo SVG e calcular a altura de exibição.
    2.  **Fase 2: Renderização (`_adicionar_paragrafo_quebravel`):**
        * Esta função também usa a medição exata para *cortar* o texto. Ela "preenche" uma página virtual com palavras (medidas) até que a altura restante (`self.altura_restante`) acabe. Ela então corta o parágrafo (`texto_para_pagina_atual` e `texto_restante`) e chama `_nova_pagina()`.
* **"Gambiarras" e Pontos de Atenção:**
    * **"Gambiarra" (Dependência de SO):** `_carregar_fonte_medidora` depende de `C:/Windows/Fonts/times.ttf`. Isso **falhará imediatamente** em um macOS ou Linux.
    * **"Gambiarra" (Quebra de Palavra Longa):** A lógica do "AAAAA..." (`while largura_linha_atual > self.LARGURA_CONTEUDO_PX:`) é uma "gambiarra" funcional que estima a altura de palavras únicas que são mais longas que a própria linha.
    * **CSS (Rede de Segurança):** O CSS `overflow: hidden;` na classe `.pagina` é a "rede de segurança". Se a simulação falhar por 1 pixel, o CSS impede que o texto vaze visualmente.

---
---

### 5.4. Os "Serviços" (Gerenciamento e Utilitários)

Módulos de infraestrutura que dão suporte à aplicação.

---

#### `gerenciador_projeto.py`
* **Propósito:** O **"Cofre"**. Define o formato `.abnf` (um `.zip` disfarçado) e lida com salvar e carregar o projeto.
* **Arquitetura:**
    * **`salvar_projeto` (Serialização):**
        1.  `copy.deepcopy(documento)`: (Estratégia de Segurança) Cria uma cópia dos dados para evitar corrupção.
        2.  `tempfile.TemporaryDirectory()`: Cria uma pasta temporária.
        3.  `shutil.copy2(...)`: Copia os ativos (figuras, brasões, fórmulas) para subpastas.
        4.  **Estratégia (Caminhos Relativos):** Re-escreve os caminhos no `documento.json` para serem relativos (ex: `"imagens/fig1.png"`).
        5.  `shutil.make_archive(...)`: Compacta a pasta temporária em um `.zip` e a renomeia para `.abnf`.
    * **`carregar_projeto` (Desserialização):**
        1.  Cria uma nova pasta temporária (`self.diretorio_temporario_atual`).
        2.  `zipfile.ZipFile(...).extractall()`: Descompacta o `.abnf` (JSON e imagens).
        3.  `DocumentoABNT.from_dict()`: Recria o objeto (com caminhos relativos).
        4.  **Estratégia (Re-hidratação):** Re-escreve os caminhos relativos para que sejam **absolutos**, apontando para a pasta temporária (ex: `C:\Temp\load_...\imagens\fig1.png`).
* **Gambiarras e Pontos de Atenção:**
    * **`_processar_imagem_brasao` (Código Morto):** Esta função é um resquício de uma lógica antiga e bugada. Ela não é mais chamada pelo `salvar_projeto` (que agora apenas copia o arquivo pré-processado), mas permaneceu no código.

---

#### `gerenciador_config.py`
* **Propósito:** O "cérebro" da aplicação. Salva as *preferências do usuário* (não o projeto) no `abnf_helper_config.json`.
* **Arquitetura:**
    * **Estratégia (Migração de Config):** `carregar_config` usa `config.setdefault()` para adicionar *novas* chaves de configuração e `del` para remover chaves *obsoletas*. Isso é uma estratégia de migração "schema-on-read" que garante compatibilidade entre versões.
    * **Estratégia (Gerenciamento de Recentes):** `add_projeto_recente` salva um `timestamp` e `get_projetos_recentes` ordena por ele, garantindo que a lista esteja sempre na ordem "Mais Recente".
    * **"Gambiarra" (Blindagem):** O código se recusa ativamente a adicionar caminhos que terminam em `.abnf.recovery` à lista de recentes.
* **Gambiarras e Pontos de Atenção:**
    * **"Gambiarra" (Localização):** O `CONFIG_FILE` é salvo no mesmo diretório do script, tornando o app "portátil", mas "esquecendo" as configurações se a pasta for movida.
    * **"Gambiarra" (Salvamento Não-Atômico):** O `salvar_config` sobrescreve o arquivo (`'w'`). Se o PC desligar nesse exato instante, o JSON pode ser corrompido.

---

#### `gerenciador_recuperacao.py`
* **Propósito:** O **"Anjo da Guarda"**. Protege o usuário contra falhas (Auto-Save) e contra si mesmo (Backups).
* **Arquitetura (Auto-Save):**
    * **"Gambiarra" (Localização Segura):** O `RECOVERY_DIR` é salvo em `%LOCALAPPDATA%` (pasta oculta do sistema). Esta estratégia crucial permite que o auto-save funcione mesmo se o usuário estiver trabalhando em um pen drive.
    * **Estratégia (Nomes de Arquivo):** Usa `hash(caminho_absoluto)` para projetos salvos (para evitar conflitos) e `timestamp` para "Novos Projetos" (que não têm caminho).
    * **Estratégia (Arquivo Gêmeo):** Salva o `.abnf.recovery` (os dados) e um `.json` (os metadados, como o nome original, para mostrar ao usuário).
    * **"Gambiarra" (Limpeza Dupla):** `limpar_recuperacao` (tenta recriar o hash) e `limpar_recuperacao_pelo_caminho_direto` (usada quando é impossível recriar o nome, como no caso do "Novo Projeto").
* **Arquitetura (Backups):**
    * **Localização:** Salva em uma subpasta `.abnf_backups` *ao lado* do arquivo do usuário (fácil de encontrar).
    * **Lógica de "Rodízio" (`_limpar_backups_antigos`):** Ordena todos os backups por data e exclui os mais antigos, mantendo apenas os 10 mais recentes.

---

#### `stylesheet.py`
* **Propósito:** Define a **identidade visual** (tema) de toda a aplicação em um único lugar.
* **Arquitetura:**
    * **Estratégia (Classes CSS Falsas):** QSS não tem classes. O código usa a "gambiarra" de *Seletores de Propriedade* (`[cssClass="..."]`). Os widgets definem essa propriedade (`.setProperty("cssClass", "destructive")`), e o QSS a estiliza (vermelho).
    * **Estratégia (Ícone do ComboBox):** O código esconde a seta padrão (`image: none;`) e usa `background-image: url(...)` no `::drop-down` para definir um ícone PNG customizado.
    * **"Gambiarra" (Formatação de String):**
        * O caminho para o ícone (`arrow_down.png`) é *injetado* na string QSS usando `_STYLE_SHEET_TEMPLATE.format(ICON_URL_PATH=...)`.
        * **O Erro:** `format()` entra em conflito com as chaves `{}` do QSS.
        * **A Correção:** Todas as chaves literais do QSS no arquivo são **duplicadas** (ex: `QWidget {{ ... }}`) para "escapá-las" da formatação do Python.
* **Pontos de Atenção:** O desenvolvedor deve sempre lembrar de duplicar as chaves (`{{ }}`) ao editar o QSS.


## Documentação Detalhada: `aba_conteudo.py`

### 1\. Propósito Principal

Este arquivo é o **coração pulsante da interface gráfica (GUI)** do seu aplicativo. Ele define a `AbaConteudo`, que é o painel central onde o usuário gasta 90% do seu tempo.

Sua responsabilidade é dupla:

1.  **Visualização (View):** Apresentar a estrutura do documento (capítulos, subcapítulos) e o conteúdo (texto, figuras, tabelas).
2.  **Controle (Controller):** Agir como o intermediário principal entre o usuário e o modelo de dados (`documento.py`). Ele "ouve" as ações do usuário (digitar, clicar em botões) e atualiza o modelo de dados em tempo real.

### 2\. Tecnologias e Bibliotecas Utilizadas

  * **`PySide6` (Qt for Python):** Esta é a biblioteca fundamental para toda a interface. O `aba_conteudo.py` faz uso pesado de:

      * **Widgets:** `QWidget` (a base da aba), `QHBoxLayout` (para dividir em painéis esquerdo/direito), `QTextEdit` (o editor de texto), `QTreeWidget` (a árvore de capítulos), `QTabWidget` (as abas de Figuras/Tabelas/Fórmulas), `QPushButton`, `QCheckBox`, `QLineEdit`.
      * **Sinais e Slots:** A principal forma de comunicação. `button.clicked.connect(...)` e `editor.textChanged.connect(...)` são a cola que faz o módulo funcionar.
      * **Modelo/Visão (Simplificado):** O `QTreeWidget` e as `QListWidget`s são usados para *visualizar* dados que estão armazenados no `documento.py`.

  * **`re` (Python Regex):** A biblioteca de Expressões Regulares é usada para uma estratégia específica: filtrar os bancos de ativos.

### 3\. Arquitetura e Decisões de Design

Este módulo implementa diversos padrões e estratégias de design de software:

#### 3.1. O Padrão "Controlador" (Model-View-Controller)

A classe `AbaConteudo` não armazena (quase) nenhum dado. Ela recebe o objeto `documento` (o Modelo) em seu `__init__`.

  * **Leitura (Model -\> View):** Funções como `_popular_arvore` e `_carregar_capitulo_no_editor` leem os dados do `self.documento` e os exibem nos widgets (`QTreeWidget`, `QTextEdit`).
  * **Escrita (View -\> Model):** Funções como `_salvar_conteudo_capitulo` e `_sincronizar_modelo_com_arvore` pegam a informação dos widgets e a salvam de volta no `self.documento`.

#### 3.2. Sincronização em Tempo Real (A Estratégia do `textChanged`)

A decisão de design mais importante para a fluidez do programa está aqui:

```python
self.editor_capitulo.textChanged.connect(self._on_editor_text_changed)
# ... que chama ...
def _on_editor_text_changed(self):
    self._salvar_conteudo_capitulo()
    self.atualizar_bancos_visuais()
```

Isso significa que a **cada tecla que o usuário digita**, o conteúdo do `QTextEdit` é salvo de volta no objeto `capitulo.conteudo`.

  * **Pró:** O usuário nunca perde trabalho (o modelo de dados está *sempre* atualizado, pronto para o auto-save).
  * **Contra (Potencial Risco):** Em textos gigantescos ou lógicas complexas, isso poderia causar lentidão. No entanto, como a operação é apenas uma atribuição de string (`capitulo.conteudo = ...`), o desempenho é excelente.

#### 3.3. O Sistema de Marcadores (Placeholders)

Este módulo **não** é um editor WYSIWYG ("What You See Is What You Get"). Ele não renderiza as tabelas ou figuras dentro do `QTextEdit`.

Em vez disso, ele usa um **sistema de marcadores** (placeholders):

  * `{{Tabela:Nome da Tabela}}`
  * `{{Figura:Nome da Figura}}`
  * `{{QUEBRA_PAGINA}}`

Isso é uma estratégia (um truque de design) brilhante: ela desacopla a edição da renderização. Os módulos `gerador_docx.py` e `gerador_preview.py` é que têm a responsabilidade de encontrar (com Regex) e substituir esses marcadores. Isso torna o editor de texto muito mais simples e rápido.

### 4\. "Gambiarras" e Pontos de Atenção

O código contém algumas soluções que, embora funcionem, são "gambiarras" (soluções rápidas que podem ser frágeis) ou estratégias (truques específicos).

#### 4.1. "Gambiarra": A Sincronização Invertida da Árvore

Veja a função `_sincronizar_modelo_com_arvore`: ela lê a árvore *visual* (`QTreeWidget`) e **recria o modelo de dados** (`self.documento.estrutura_textual.filhos`) a partir dela.

  * **Por que é uma "gambiarra"?** A arquitetura "ideal" de software (MVC/MVVM) faria o oposto: o `dropEvent` atualizaria o *modelo de dados* (a lista `documento.filhos`), e o `QTreeWidget` (a *view*) se atualizaria automaticamente para refletir o modelo.
  * **Por que funciona?** Fazer o `drag-and-drop` no modelo de dados é complexo. É muito mais simples deixar o `QTreeWidget` fazer a reorganização visual (ele já sabe fazer isso) e, quando o usuário soltar o mouse, simplesmente jogar o modelo de dados antigo fora e recriá-lo com base no que a árvore está mostrando. É uma solução rápida e eficaz.

#### 4.2. Estratégia: O Filtro dos Bancos de Ativos

A função `atualizar_bancos_visuais` usa Regex para filtrar as listas de figuras/tabelas:

```python
conteudo_capitulo = capitulo_selecionado.conteudo
titulos_usados = set(re.findall(r"\{\{Tabela:([^}]+)\}\}", conteudo_capitulo))
```

  * **O que ela faz:** Em vez de ter um link de banco de dados (ex: "capítulo 5 usa as tabelas 2 e 4"), ela **lê o texto puro** do capítulo, procura todos os marcadores `{{Tabela:...}}` e usa isso para filtrar a lista.
  * **Por que é uma estratégia?** É uma forma inteligente de implementar o filtro "Mostrar apenas do tópico atual" sem precisar de um sistema complexo de referenciamento. Ela depende diretamente do sistema de marcadores.

#### 4.3. Estratégia: O Flag de Bloqueio `_carregando_capitulo`

Este é um truque clássico de GUI para evitar loops de sinal (re-entrância):

1.  O usuário clica em um capítulo.
2.  `_on_capitulo_selecionado_changed` é chamado.
3.  `_carregar_capitulo_no_editor` é chamado.
4.  A flag `self._carregando_capitulo` é setada para `True`.
5.  A linha `self.editor_capitulo.setPlainText(...)` é executada.
6.  `setPlainText` dispara o sinal `textChanged`.
7.  `_on_editor_text_changed` (que está conectado a esse sinal) é chamado.
8.  **A "mágica":** A primeira coisa que `_salvar_conteudo_capitulo` faz é checar `if self._carregando_capitulo: return`.
9.  Como a flag está `True`, a função para imediatamente. Ela não tenta salvar o conteúdo que ela mesma está carregando.
10. `_carregar_capitulo_no_editor` termina e seta a flag para `False`.

Sem essa flag, o programa entraria em um loop infinito ou teria um comportamento caótico.

### 5\. Dependências Externas (Importações)

  * `documento`: Essencial. É onde os dados (`Capitulo`, `Tabela`, `Figura`, `Formula`) estão armazenados.
  * `dialogo_tabela.TabelaDialog`: A janela pop-up para criar/editar tabelas.
  * `dialogo_figura.DialogoFigura`: A janela pop-up para criar/editar figuras (com a ferramenta de corte).
  * `DialogoFormula.DialogoFormula`: A janela pop-up para criar/editar fórmulas (com o editor LaTeX).


## Documentação: `dialogo_brasao.py`

### 1. Propósito Principal

Este arquivo define o `DialogoBrasao`, uma janela pop-up (`QDialog`) com uma finalidade muito específica: **carregar, cortar e configurar a imagem do brasão da instituição** (ou brasões) que aparecerá na capa do documento.

Este módulo é um dos mais complexos da aplicação em termos de interface gráfica, pois ele **implementa um editor de imagens personalizado** (`CropLabel`) com duas ferramentas de corte distintas.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`PySide6` (Qt for Python):** Usado para toda a interface, incluindo:
    * `QDialog`: A base da janela.
    * `QHBoxLayout`: Para o layout principal de dois painéis (Controles na esquerda, Imagem na direita).
    * `QLabel`: Usado como a classe base para a ferramenta de corte.
    * `QRadioButton` / `QButtonGroup`: Para criar o seletor de ferramentas (Retângulo vs. Polígono).
    * **`QPainter` / `QPen` / `QColor` / `QPainterPath`:** Este é o coração da ferramenta de corte. O `QPainter` é usado para desenhar *sobre* o `QLabel`, criando o *overlay* escuro (com `QPainterPath` e `OddEvenFill`) e as linhas de seleção vermelhas e tracejadas (`QPen`).
* **`PIL` (Pillow):** Usada para o processamento de imagem no *backend* (após o usuário clicar "OK").
    * `Image.open()`: Carrega a imagem original.
    * `img.crop()`: Executa o corte retangular.
    * **`ImageDraw` / `Image.new("L")` / `img.paste(mask=...)`:** Esta é a estratégia principal para o corte poligonal. O Pillow não pode "recortar" um polígono, então o código cria uma máscara de transparência (alfa) em preto e branco e a usa para "colar" apenas a porção poligonal da imagem original em uma nova imagem transparente.
    * `img.thumbnail()`: Redimensiona a imagem final (já cortada) para um tamanho otimizado (150px) antes de salvar.

### 3. Arquitetura e Decisões de Design

Este módulo é dividido em duas classes principais que trabalham juntas: `CropLabel` (a ferramenta) e `DialogoBrasao` (a janela).

#### 3.1. Classe `CropLabel(QLabel)` - A Ferramenta de Corte

Esta é a parte mais engenhosa do código. É um `QLabel` que foi sobrescrito para se transformar em um "mini-Photoshop".

* **Padrão "Máquina de Estados":** A classe opera em dois modos (`self.mode`), 'rect' ou 'poly'. Os eventos do mouse (`mousePressEvent`, `mouseMoveEvent`) contêm lógica `if/elif` que muda completamente o comportamento do widget com base no modo ativo.
* **Escalonamento e Mapeamento de Coordenadas (A Estratégia Central):**
    1.  A imagem original (`self.original_pixmap`) **não** é a imagem que o usuário vê. A imagem vista é a `self.scaled_pixmap`, que é redimensionada para caber na janela.
    2.  O código armazena o `self.scale_factor` (a proporção entre a imagem original e a escalada) e o `self.pixmap_rect_in_widget` (a posição exata da imagem dentro do widget).
    3.  **`_clamp_pos_to_pixmap`:** Uma função de segurança crucial que impede o usuário de clicar ou arrastar para fora da área da imagem (na borda cinza do `QLabel`).
    4.  **`get_crop_coords()`:** Esta é a função de "tradução". Quando o usuário termina a seleção (na imagem *escalada*), esta função pega as coordenadas da tela (ex: 50, 100), converte-as para coordenadas relativas à imagem (removendo o offset) e multiplica-as pelo `self.scale_factor` para obter as coordenadas *exatas* correspondentes na imagem *original* de alta resolução. É isso que permite um corte preciso.

* **Lógica de Desenho (`paintEvent`):**
    * Esta função usa o `QPainterPath` com a regra `Qt.FillRule.OddEvenFill`. É um truque inteligente:
        1.  Ele desenha um retângulo escuro sobre a imagem inteira.
        2.  Em seguida, desenha a seleção do usuário (retângulo ou polígono) "dentro" desse retângulo.
        3.  O `OddEvenFill` torna a área de interseção (a seleção) transparente, criando o efeito de "buraco" no *overlay* escuro.

* **Lógica de Seleção Poligonal:**
    * Usa `setMouseTracking(True)` para que `mouseMoveEvent` seja chamado *mesmo sem o mouse estar pressionado*, permitindo desenhar a linha "elástica" (`self.preview_point`).
    * Detecta o fechamento do polígono medindo a distância do clique atual ao primeiro ponto (`self.poly_points[0]`).

#### 3.2. Classe `DialogoBrasao(QDialog)` - A Janela

* **Interface:** Divide a janela em dois painéis (Controles e Preview), o que é um layout de UI excelente e intuitivo.
* **Controle de Ferramenta:** Usa um `QButtonGroup` para gerenciar os `QRadioButton`s ('rect' vs 'poly'). Quando o modo muda (`_mudar_modo_corte`), ele:
    1.  Chama `self.preview_label.set_mode(...)` para trocar o estado da ferramenta.
    2.  Atualiza o `self.info_label` com instruções específicas para a ferramenta selecionada.
* **Processamento (`_processar_imagem`):**
    * Esta função é o "backend" da janela. Ela só é chamada quando o usuário clica em "OK".
    * Ela pega o dicionário de coordenadas do `preview_label.get_crop_coords()`.
    * Usa `PIL` (Pillow) para realizar a operação de corte real (seja `img.crop()` ou a estratégia da máscara `ImageDraw.polygon()`).
    * **Otimização:** Ela não salva a imagem gigante original. Ela corta, redimensiona para 150x150px (`thumbnail`) e salva um `.png` pequeno na pasta `_brasoes_processados`. O `self.caminho_processado` aponta para este novo arquivo otimizado.

### 4. "Gambiarras" e Pontos de Atenção

* **"Gambiarra" de Nomenclatura de Arquivo:** O código em `_processar_imagem` que garante um nome de arquivo único (usando um `while os.path.exists(...)` e adicionando `_1`, `_2`, etc.) é uma forma simples, mas não ideal, de lidar com conflitos. Se o usuário carregar `imagem.png` 1000 vezes, ele criará 1000 arquivos. Uma abordagem mais robusta usaria um hash (como MD5) do conteúdo do arquivo ou um UUID como nome, mas a solução atual é funcional para um usuário único.
* **Lógica de "Usar Imagem Inteira":** O código usa um `QMessageBox` para perguntar ao usuário se ele quer usar a imagem inteira se nenhuma seleção for feita. Isso é tratado por um *flag* (`self._usar_imagem_inteira`), que é verificado dentro de `_processar_imagem`. É uma solução simples e eficaz.


## Documentação Detalhada: `dialogo_figura.py`

### 1. Propósito Principal

Este módulo define o `DialogoFigura`, uma janela (`QDialog`) responsável por todo o ciclo de vida de uma Figura dentro do projeto: desde a **criação** (carregar uma imagem) até a **edição avançada** (corte) e **configuração de metadados** (título, fonte, largura).

Ele é fundamentalmente um "mini-editor de imagens" focado em ABNT, construído sobre dois pilares: a classe `DialogoFigura` (a janela e os controles) e a classe `CropLabel` (a ferramenta de corte visual).

Este arquivo é uma cópia quase idêntica do `dialogo_brasao.py`, mas adaptado para o objeto `Figura` do documento, que tem regras de processamento diferentes (como redimensionamento baseado em `LARGURA_MAXIMA_PX` em vez de um thumbnail fixo).

### 2. Tecnologias e Bibliotecas Utilizadas

* **`PySide6` (Qt for Python):** É a base de toda a interface.
    * **Widgets de Layout:** `QHBoxLayout`, `QVBoxLayout`, `QFormLayout` para criar a estrutura de dois painéis (Controles e Preview).
    * **Widgets de Formulário:** `QLineEdit` (para Título/Fonte), `QComboBox` (para seleção de Largura), `QRadioButton` e `QButtonGroup` (para alternar entre os modos de corte), `QFrame` (para agrupar as ferramentas), `QFileDialog` (para selecionar o arquivo).
    * **`QPainter` e Gráficos 2D:** Esta é a tecnologia central da ferramenta de corte. `QPainter` é usado para "desenhar sobre" um `QLabel`, `QPen` define o traço (vermelho, tracejado), `QPainterPath` e `QPolygonF` são usados para construir as formas geométricas (retângulo e polígono) que serão desenhadas.
* **`PIL` (Pillow) - `Image` e `ImageDraw`:** Esta é a biblioteca de processamento de imagem do *backend*.
    * **`Image.open`:** Carrega a imagem original do disco.
    * **`img.convert("RGBA")`:** Garante que a imagem tenha um canal alfa (transparência), o que é **essencial** para o corte poligonal.
    * **`img.crop(coords)`:** Executa o corte retangular (rápido e simples).
    * **`Image.new("L", ...)` e `ImageDraw.Draw(mask)`:** Usados na estratégia de corte poligonal para criar uma máscara de alfa (explicado abaixo).
    * **`img.paste(mask=...)`:** Aplica a máscara de alfa para criar o corte poligonal.
    * **`img.resize(...)`:** Redimensiona a imagem final (já cortada) para os limites da ABNT (`LARGURA_MAXIMA_PX`).
    * **`img.convert("RGB")`:** Otimização que remove o canal alfa (transparência) ao salvar, caso o corte tenha sido retangular, economizando espaço.

### 3. Arquitetura e Decisões de Design

O módulo é dividido em duas classes:

#### 3.1. Classe `CropLabel(QLabel)` - A Ferramenta de Corte

Esta é a classe mais complexa do arquivo. É uma estratégia de engenharia de UI que transforma um simples `QLabel` em uma tela de edição interativa.

* **Padrão de "Máquina de Estados"**: A classe opera em dois modos (`self.mode`), 'rect' (retângulo) ou 'poly' (polígono). As funções de eventos do mouse (`mousePressEvent`, `mouseMoveEvent`) usam `if self.mode == 'rect'`... `elif self.mode == 'poly'`... para mudar seu comportamento drasticamente. Isso é uma implementação clássica de uma Máquina de Estados.
* **Estratégia 1: Tradução de Coordenadas (A Lógica Central)**
    O maior desafio é que o usuário está clicando em uma imagem *escalada* (`scaled_pixmap`) dentro de uma janela redimensionável, mas o corte precisa ser aplicado na imagem *original* (`original_pixmap`).
    1.  **Mapeamento:** `_update_scaled_pixmap` calcula o `self.scale_factor` (ex: 3.0, se a original for 3x maior) e o `self.pixmap_rect_in_widget` (o "padding" ou espaço vazio ao redor da imagem escalada).
    2.  **Segurança:** `_clamp_pos_to_pixmap` é uma função de "trava" essencial. Ela impede que os cliques do usuário fora da imagem (mas dentro do `QLabel`) sejam registrados, o que quebraria o cálculo de coordenadas.
    3.  **Tradução:** `get_crop_coords` é a função "mágica". Ela pega as coordenadas da seleção na tela, subtrai o offset (`-self.pixmap_rect_in_widget.topLeft()`) para torná-las relativas à imagem escalada, e então multiplica pelo `self.scale_factor` para "traduzi-las" para as coordenadas da imagem original.
* **Estratégia 2: O Overlay "Negativo" (paintEvent)**
    Para criar o efeito de "buraco" na seleção, o código não tenta desenhar quatro retângulos escuros ao redor da seleção. Ele usa um truque de `QPainterPath`:
    1.  Cria um `QPainterPath` e adiciona o retângulo da imagem inteira.
    2.  Adiciona a seleção (retângulo ou polígono) *dentro* desse caminho.
    3.  Define a regra de preenchimento como `Qt.FillRule.OddEvenFill`.
    4.  Isso faz com que o `QPainter` preencha a área com 1 forma (o overlay), mas deixe a área com 2 formas (a seleção) transparente.
* **Estratégia 3: A Linha Elástica (Modo Polígono)**
    Ao definir `self.setMouseTracking(True)`, o `CropLabel` força o Qt a enviar eventos `mouseMoveEvent` *mesmo se o botão do mouse não estiver pressionado*. Isso permite que a função armazene a posição do mouse em `self.preview_point` e se redesenhe (`self.update()`), criando a "linha elástica" que segue o cursor do último ponto clicado.

#### 3.2. Classe `DialogoFigura(QDialog)` - O Controlador da Janela

Esta classe gerencia a UI (os campos de formulário) e o `CropLabel`, e executa a lógica de processamento final.

* **Gerenciamento de Estado:** A função `_mudar_modo_corte` atua como o controlador da "Máquina de Estados". Ela diz ao `CropLabel` qual ferramenta usar (`.set_mode()`) e atualiza o `self.info_label` com instruções relevantes.
* **Processamento de Imagem (`_processar_imagem`)**: Esta é a lógica de "backend" que é executada quando o usuário clica em "OK".
    1.  **Corte (Rect vs. Poly):** Ele primeiro aplica o corte (se houver) usando `img.crop()` ou a estratégia da máscara de polígono com `ImageDraw`.
    2.  **Redimensionamento (Padrão ABNT):** Após o corte, ele verifica se a nova `img_processada` ainda é mais larga que o limite ABNT (`LARGURA_MAXIMA_PX`). Se for, ele a redimensiona para baixo, mantendo a proporção. Isso é diferente do `dialogo_brasao`, que redimensiona para um *thumbnail* fixo (150px).
    3.  **Otimização de Salvamento:** Ao salvar, ele verifica se o corte foi poligonal (`dados_corte['mode'] == 'poly'`). Se foi, salva como `PNG` com transparência (RGBA). Se foi retangular ou sem corte, ele converte para `RGB` antes de salvar, removendo o canal alfa desnecessário e economizando espaço.
    4.  **Otimização de "Não-Processamento":** O código tem uma estratégia inteligente no início da função: se o caminho do arquivo não mudou, e já existe um arquivo processado, e o usuário não fez um novo corte, ele simplesmente retorna `True` e pula todo o caro processamento de imagem.

### 4. "Gambiarras" e Pontos de Atenção (Duplicação de Código)

* **A "Gambiarra" Principal (Violação de DRY):** A classe `CropLabel` (com mais de 200 linhas) está **duplicada** neste arquivo e no `dialogo_brasao.py`.
    * **Por quê?** Isso foi uma decisão de design para manter cada diálogo auto-contido (provavelmente vindo de `dialogo_figura.py` sendo criado primeiro, e `dialogo_brasao.py` sendo uma cópia adaptada).
    * **Qual é o Risco?** Este é um **grande débito técnico**. Se um bug for encontrado no `CropLabel` (por exemplo, um erro de cálculo no `get_crop_coords`), o desenvolvedor deve se lembrar de corrigi-lo em **dois arquivos diferentes**. A solução ideal seria mover o `CropLabel` para seu próprio arquivo (ex: `crop_widget.py`) e importá-lo em ambos os diálogos.


## Documentação: `dialogo_tabela.py`

### 1\. Propósito Principal

Este módulo define o `TabelaDialog`, uma janela pop-up (`QDialog`) que funciona como um **editor de tabelas dedicado**. Sua responsabilidade é permitir ao usuário criar uma nova tabela ou editar uma existente, configurando seus metadados (Título, Fonte) e suas opções de formatação (Estilo de Borda, Centralização), além de editar o conteúdo das células.

Este componente é um exemplo clássico de diálogo CRUD (Create, Read, Update, Delete) focado em um único objeto de dados (`Tabela`).

### 2\. Tecnologias e Bibliotecas Utilizadas

  * **`PySide6` (Qt for Python):** Utilizada para toda a interface, com destaque para:
      * `QDialog`: A base da janela modal.
      * `QTableWidget`: Este é o widget central. É uma **solução de "nível de planilha"** que fornece uma grade editável pronta para uso, com gerenciamento de linhas, colunas e células.
      * `QFormLayout`: Usado para organizar de forma limpa os campos de metadados (Título, Fonte, etc.).
      * `QLineEdit`: Para entrada de texto (Título, Fonte).
      * `QComboBox`: Para selecionar o estilo da borda ("ABNT" vs "Grade").
      * `QCheckBox`: Para a opção de centralização de conteúdo.
      * `QMessageBox`: Para exibir um aviso de validação (ex: "Título Obrigatório").
  * **`documento.Tabela` (Modelo de Dados):** O diálogo recebe um objeto `Tabela` (do `documento.py`) em seu `__init__` para preencher os campos. Ao final, ele retorna o mesmo objeto, atualizado com os novos dados.

### 3\. Arquitetura e Decisões de Design

#### 3.1. Arquitetura de "Preenchimento e Coleta"

Este diálogo segue um padrão de design muito direto e eficaz:

1.  **Fase 1: Construtor (`__init__`) - (Preenchimento)**

      * O diálogo é inicializado com um objeto `Tabela` (ou cria um novo se `tabela=None`).
      * Os widgets da interface (`self.titulo_input`, `self.fonte_input`, `self.centralizar_check`, etc.) são preenchidos com os valores existentes no objeto `self.tabela`.
      * A função `popular_tabela_widget` lê a lista de listas `self.tabela.dados` e a utiliza para popular as células do `QTableWidget`.

2.  **Fase 2: Edição (Interação do Usuário)**

      * O usuário interage com os widgets.
      * Funções como `adicionar_linha`, `remover_linha`, etc., modificam diretamente o `QTableWidget` (a *View*). **Importante:** Elas *não* modificam o `self.tabela.dados` (o *Model*) em tempo real.

3.  **Fase 3: `get_dados_tabela()` - (Coleta)**

      * Esta função só é chamada (pelo `aba_conteudo.py`) *depois* que o usuário clica em "OK" e o diálogo é fechado com sucesso.
      * Ela faz o oposto do `__init__`: lê os valores dos widgets (`.text()`, `.isChecked()`, etc.) e os salva de volta no objeto `self.tabela`.
      * Para os dados da grade, ela itera sobre o `self.table_widget` (a *View*) e constrói uma nova lista de listas, que então sobrescreve `self.tabela.dados` (o *Model*).

#### 3.2. Validação na Saída (`accept`)

O código sobrescreve a função `accept()` padrão do `QDialog`.

```python
def accept(self):
    if not self.titulo_input.text().strip():
        QMessageBox.warning(...)
        return # Impede o fechamento da janela
    super().accept() # Permite o fechamento da janela
```

  * **Decisão de Design:** Em vez de validar a cada tecla, a validação (neste caso, "Título Obrigatório") é feita apenas no momento em que o usuário tenta confirmar. Se a validação falhar, o diálogo simplesmente se recusa a fechar, forçando o usuário a corrigir o erro. Esta é uma abordagem muito eficiente em termos de desempenho e simples de implementar.

### 4\. "Gambiarras" e Pontos de Atenção

  * **Estratégia de Duplicação de Dados (View/Model Separados):**

      * O `QTableWidget` (View) e o `self.tabela.dados` (Model) **não são sincronizados em tempo real**.
      * Os dados são lidos do *Model* no início (`popular_tabela_widget`) e salvos de volta no *Model* no final (`get_dados_tabela`).
      * **Risco (Gambiarra Menor):** Se o usuário clicar em "Cancelar", todas as alterações feitas na grade (adicionar/remover linhas) são simplesmente descartadas, pois o `get_dados_tabela` nunca é chamado.
      * **Benefício:** Isso torna o código *extremamente* simples. Não há necessidade de sinais complexos para cada edição de célula. Para um diálogo modal (que bloqueia o resto do app), essa abordagem é perfeitamente aceitável e muito comum.

  * **Criação de Dados Padrão (Fallback):**

      * A linha `self.tabela = tabela if tabela else Tabela(dados=[...])` é uma estratégia defensiva.
      * Ela permite que o mesmo diálogo seja usado tanto para **Criar** (quando `tabela` é `None`) quanto para **Editar** (quando `tabela` é fornecida). Ao criar, ele já fornece uma tabela 2x2 padrão para que o `QTableWidget` não apareça vazio, melhorando a experiência do usuário.


## Documentação: `dialogo_formula.py`

Este módulo é, sem dúvida, o mais complexo tecnicamente em toda a aplicação, pois ele atua como uma "ponte" entre três mundos diferentes: a sua aplicação desktop (PySide6), um navegador web embarcado (WebEngine), e um renderizador JavaScript (MathJax).

### 1. Propósito Principal

Este módulo define o `DialogoFormula`, uma janela (`QDialog`) que permite ao usuário escrever código **LaTeX** e convertê-lo em imagens **SVG** e **PNG** de alta qualidade, que podem ser usadas no documento final.

Ele resolve um problema complexo: como renderizar fórmulas matemáticas complexas em uma aplicação desktop? A solução adotada é uma estratégia poderosa: em vez de tentar recriar um renderizador LaTeX em Python, o programa **embarca um navegador web completo** (`QWebEngineView`) para usar a melhor ferramenta do mundo para isso: a biblioteca **MathJax**.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`PySide6` (Qt for Python):**
    * **`QWebEngineView` / `QWebEnginePage`:** Este é o componente central. É um navegador Chromium completo embarcado dentro da janela do `QDialog`.
    * **`QWebEngineProfile` / `downloadRequested`:** Usado para *interceptar* o download do arquivo SVG que o JavaScript tenta baixar.
    * **`page().runJavaScript(...)`:** A principal "ponte" de comunicação. É usada para enviar dados do Python (o código LaTeX salvo) para o JavaScript e para pedir dados de volta (`window.getEditorContent()`).
    * **`QSvgRenderer` / `QImage` / `QPainter`:** Módulos gráficos nativos do Qt. Eles são usados no *backend* para converter o arquivo `.svg` (vetorial, baixado do MathJax) em um arquivo `.png` (rasterizado, necessário para o `gerador_preview.py` e compatibilidade).
* **`formula.py` (Modelo de Dados):** Usado para armazenar o resultado final (o objeto `Formula` com os caminhos para os arquivos `.svg` e `.png`).
* **`latex_renderer.html` (Arquivo Externo, Não Mostrado):** Este é o "cérebro" do lado do cliente. É um arquivo HTML/JS que:
    1.  Carrega a biblioteca MathJax de um CDN.
    2.  Fornece um `<textarea>` para o usuário digitar.
    3.  Contém funções JavaScript (como `window.setEditorContent` e `window.prepareAndTriggerDownload`) que o Python pode chamar.
    4.  A função `prepareAndTriggerDownload` é a estratégia final: ela converte a fórmula MathJax em um SVG e, em seguida, simula o clique em um link de download para enviar o arquivo ao Qt.

### 3. Arquitetura e Decisão de Design (O Fluxo de "Salvar")

O fluxo de salvamento deste diálogo é o processo mais complexo de toda a aplicação e é uma "coreografia" precisa entre Python, JavaScript e o Navegador:

1.  **Usuário clica "OK".**
2.  A função `trigger_save_process` (Python) é chamada.
3.  A UI é bloqueada (cursor de espera, botões desativados).
4.  **Python -> JS:** O Python chama `window.getEditorContent()` no JavaScript.
5.  **JS -> Python:** O JavaScript retorna o código LaTeX do `<textarea>` para a função de callback `on_latex_code_received`.
6.  `on_latex_code_received` (Python) salva o código LaTeX no `self.formula`.
7.  **Python -> JS:** O Python chama `window.prepareAndTriggerDownload()`.
8.  **JavaScript (em `latex_renderer.html`):**
    * O MathJax converte a fórmula em um SVG.
    * O JavaScript cria um "Blob" (um arquivo em memória) com o SVG.
    * O JavaScript cria um link de download (`<a href=... download=... >`) e o "clica".
9.  **Navegador -> Python:** O clique no link dispara o sinal `downloadRequested` do `QWebEngineProfile`.
10. **`_handle_automatic_download` (Python):**
    * O Python "intercepta" o download.
    * Ele cria um arquivo temporário (`_temp_svg_path`) e diz ao navegador para salvar o SVG lá.
    * Ele conecta o sinal `stateChanged` do download à próxima etapa.
11. **`_on_download_state_changed` (Python):**
    * Quando o download é concluído (`DownloadCompleted`), esta função é chamada.
    * Ela chama `_converter_svg_para_png` para a etapa final.
12. **`_converter_svg_para_png` (Python/Qt Nativo):**
    * Carrega o `_temp_svg_path` em um `QSvgRenderer`.
    * Cria uma `QImage` (um bitmap) vazia e transparente.
    * Usa um `QPainter` para "desenhar" o SVG vetorial sobre o bitmap.
    * Salva a `QImage` como o arquivo `.png` final.
13. **Finalização:** A UI é desbloqueada (`_restore_ui_state`) e o diálogo é fechado (`super().accept()`).

### 4. "Gambiarras" e Pontos de Atenção

* **Estratégia: Comunicação Python <-> JavaScript**
    * A forma como o Python e o JavaScript conversam usando `runJavaScript` e *callbacks* é uma técnica avançada e poderosa. Não é uma "gambiarra", mas sim a solução correta para este problema.
* **Estratégia: Download Falso para Transferência de Arquivo**
    * A técnica de simular um download no JavaScript (`prepareAndTriggerDownload`) apenas para ser interceptado pelo PySide6 (`downloadRequested`) é uma estratégia brilhante.
    * **Por quê?** É *extremamente* difícil para o JavaScript retornar um arquivo binário (ou um SVG grande como texto) diretamente para o Python através de `runJavaScript`. Simular um download é a forma mais limpa e robusta de transferir o arquivo do "mundo web" para o "mundo desktop".
* **"Gambiarra" (Menor): Conversão SVG -> PNG**
    * A função `_converter_svg_para_png` usa a biblioteca `QtSvg`. Isso é ótimo, mas adiciona uma dependência de sistema. Se o QtSvg não estivesse disponível, o código falharia. (No seu caso, como você usa PySide6, ele *está* disponível). Uma alternativa "pura" do Python seria usar bibliotecas como `cairosvg`, mas a solução atual é mais integrada ao framework.
* **"Gambiarra": Escapando o LaTeX (`_on_load_finished`)**
    * `codigo_js_escapado = self.formula.codigo_latex.replace("\\", "\\\\")...`
    * Isso é um "calcanhar de Aquiles" clássico. O código LaTeX (que contém `\`, `\n`, `'`) precisa ser "escapado" para poder ser inserido com segurança *dentro* de uma string JavaScript (`window.setEditorContent('...')`). Se uma fórmula usar um caractere que não foi previsto (como aspas duplas `"`), ela quebrará a string JS e a fórmula não será carregada. Uma solução 100% robusta seria passar o código como JSON.
* **"Gambiarra": Caminho da Fonte (em `gerador_preview.py`, mas relevante aqui)**
    * O código `_carregar_fonte_medidora` no `gerador_preview.py` assume que a fonte `times.ttf` está em `C:/Windows/Fonts/`. Isso é uma "gambiarra" que só funciona em Windows e falhará em macOS ou Linux. A solução correta (mas muito mais complexa) seria empacotar o arquivo `.ttf` com o programa ou usar a biblioteca `matplotlib.font_manager` para encontrar a fonte no sistema.


## 📄 Documentação Detalhada: `dialogo_lista.py`

### 1. Visão Geral

O arquivo `dialogo_lista.py` define a classe `ListaDialog`, uma janela de diálogo modal (`QDialog`) projetada especificamente para a criação e edição de objetos `ListaABNT`.

Esta janela gerencia duas responsabilidades principais:
1.  **Configuração de Metadados:** Permite ao usuário definir o **título** (identificador único), o **tipo de enumeração** (ABNT, Numérica, etc.) e se o título deve ser visível no documento final.
2.  **Edição Estrutural:** Fornece um editor em árvore (`QTreeWidget`) que permite ao usuário criar, editar, remover e reordenar (`drag-and-drop`) os itens hierárquicos (`ItemLista`) que compõem a lista.

A classe é crucial para desacoplar a lógica de edição de listas da `aba_conteudo`, fornecendo uma interface de usuário focada e reutilizável.

### 2. Dependências

* **PySide6:** Utiliza vários componentes da biblioteca Qt para a interface gráfica, incluindo `QDialog`, `QTreeWidget`, `QLineEdit`, `QComboBox`, `QCheckBox`, e `QDialogButtonBox`.
* **documento.py:** Depende fundamentalmente das classes de modelo de dados `ListaABNT` (o contêiner da lista) e `ItemLista` (os nós individuais da árvore).

---

### 3. Análise da Classe `ListaDialog`

A classe `ListaDialog` é a única classe neste arquivo e herda de `QDialog`.

#### 3.1. Atributos Principais

* `self.lista` (ListaABNT): O objeto de dados **"em trabalho"**. Se for uma nova lista, é uma nova instância. Se for uma edição, é o mesmo objeto passado para o construtor. Todos os widgets da UI (campos de texto, árvore) são populados a partir deste objeto e, ao salvar, atualizam este objeto.
* `self.lista_original_para_edicao` (ListaABNT | None): Armazena uma **referência** ao objeto `lista_existente` original passado no construtor. É usado **exclusivamente** no método `accept()` para a verificação de duplicidade, permitindo diferenciar entre "salvar com o mesmo nome" (permitido) e "salvar com um nome que conflita com *outra* lista" (proibido).
* `self.banco_listas` (list[ListaABNT]): Uma referência à lista completa de *todas* as listas do documento. É usado **exclusivamente** no método `accept()` para verificar se o novo título já existe.
* `self.arvore_itens` (QTreeWidget): O componente visual (a **View**) que exibe a hierarquia dos `ItemLista`. O usuário interage diretamente com este widget.

#### 3.2. Método `__init__` (Construtor)

O construtor configura o diálogo, distinguindo entre o modo de "criação" e "edição".

* **Parâmetros:**
    * `lista_existente` (ListaABNT | None): Se `None`, o diálogo entra em modo de **criação**. Se um objeto `ListaABNT` é fornecido, entra em modo de **edição**.
    * `banco_listas` (list[ListaABNT] | None): A lista completa de listas do projeto, necessária para a validação de duplicidade de título.
* **Lógica de Inicialização:**
    1.  **Gerenciamento de Estado:** Armazena `lista_existente` em `self.lista_original_para_edicao` e `banco_listas` em `self.banco_listas`.
    2.  **Criação/Edição:** Define `self.lista` (o objeto de trabalho). Se for uma nova lista (`lista_existente` é `None`), ele também adiciona um `ItemLista` padrão ("Item a)") para que o usuário não comece com uma árvore vazia.
    3.  **Construção da UI (Layout):** O layout é dividido em 4 seções:
        * **Seção 1 (Formulário):** `titulo_input`, `mostrar_titulo_check`, e `tipo_enumeracao_combo`. Seus valores iniciais são lidos de `self.lista`.
        * **Seção 2 (Árvore):** O `QTreeWidget` (`self.arvore_itens`) é configurado.
            * `setDragDropMode(InternalMove)`: Permite que o usuário arraste e solte itens *dentro* da árvore para reordená-los.
            * `setSelectionMode(SingleSelection)`: Garante que apenas um item possa ser selecionado por vez.
            * `popular_arvore_widget()`: É chamado para preencher a árvore com base no modelo `self.lista.raiz`.
            * `itemDoubleClicked`: Conectado ao slot `editar_item` para facilitar a edição.
        * **Seção 3 (Botões da Árvore):** Botões para "Adicionar Item", "Adicionar Subitem", "Editar Item" e "Remover Item", conectados aos seus respectivos slots.
        * **Seção 4 (OK/Cancelar):** Um `QDialogButtonBox` padrão. O sinal `accepted` é conectado ao método `accept()`, que contém toda a lógica de validação.

---

### 4. Fluxo de Dados: Modelo ⇔ View

A parte mais complexa deste diálogo é a sincronização entre o modelo de dados (`ItemLista`) e a visualização (`QTreeWidget`).

#### 4.1. `popular_arvore_widget(self)` (Modelo -> View)

* **Propósito:** Lê a estrutura de dados (o `ItemLista` aninhado dentro de `self.lista.raiz`) e a "desenha" no `QTreeWidget`.
* **Como funciona:**
    1.  Usa uma função recursiva interna `adicionar_filhos_recursivo`.
    2.  Para cada `filho_modelo` (`ItemLista`) no `no_pai_modelo`, ele cria um `item_widget` (`QTreeWidgetItem`).
    3.  **PONTO-CHAVE:** A linha `item_widget.setData(0, QtCore.Qt.ItemDataRole.UserRole, filho_modelo)` armazena uma **referência direta** ao objeto do modelo (`ItemLista`) dentro do item da view (`QTreeWidgetItem`).
    4.  Isso permite que, ao interagir com a view (ex: clicar em "Editar"), possamos recuperar instantaneamente o objeto de dados correspondente.

#### 4.2. `_construir_modelo_da_arvore(self)` (View -> Modelo)

* **Propósito:** Faz o oposto. Lê a estrutura *visual* atual do `self.arvore_itens` (que pode ter sido modificada por `drag-and-drop` ou remoções) e constrói um **novo** objeto `ItemLista` (modelo) que reflete essa estrutura.
* **Como funciona:**
    1.  Cria uma `nova_raiz_modelo` vazia.
    2.  Usa uma função recursiva `percorrer_arvore_ui` que itera pelos itens do `QTreeWidget`.
    3.  Para cada `child_item_widget` (da view), ele recupera o `child_node_modelo` (o `ItemLista`) que foi armazenado usando `item.data()`.
    4.  **PONTO-CHAVE:** Ele limpa os filhos do modelo (`child_node_modelo.filhos.clear()`) porque a estrutura atual da **View** é agora a "fonte da verdade".
    5.  Ele reconstrói a hierarquia do modelo chamando `parent_node_modelo.adicionar_filho(child_node_modelo)` na nova ordem.
    6.  Retorna a `nova_raiz_modelo` preenchida, que substituirá a `self.lista.raiz` original.

---

### 5. Métodos Principais (Slots)

#### 5.1. Slots de Edição da Árvore

* `adicionar_item_raiz(self)` / `adicionar_item_filho(self)`: Criam tanto o `ItemLista` (modelo) quanto o `QTreeWidgetItem` (view), ligam um ao outro com `setData` e os adicionam à árvore (no nível raiz ou como filho do item selecionado, respectivamente). Em seguida, chamam `editar_item()` para uma experiência de usuário fluida.
* `editar_item(self, item_widget)`: Recupera o `ItemLista` do `item_widget` usando `item.data()`. Abre um `QInputDialog` para obter o novo texto. Se válido, atualiza **ambos**: `item_modelo.texto` e `item_widget.setText()`.
* `remover_item(self)`: Remove o `QTreeWidgetItem` selecionado da *view* (`self.arvore_itens`). A remoção do modelo de dados só é efetivada quando `_construir_modelo_da_arvore` é chamado durante o `accept()`.

#### 5.2. `accept(self)` (Validação e Salvamento)

Este é o método mais crítico. Ele é acionado quando o usuário clica em "OK" e **impede o fechamento do diálogo** se qualquer validação falhar.

O fluxo de execução é:
1.  **Validar Título Vazio:** Pega o `titulo_input`. Se estiver vazio, exibe um `QMessageBox.warning` e `return` (o diálogo permanece aberto).
2.  **Validar Duplicidade de Título:**
    * Pega o `novo_titulo`.
    * Itera por `self.banco_listas` (fornecido no `__init__`).
    * Se um `lista_existente` tem o mesmo título (ignorando maiúsculas/minúsculas):
        * Verifica se `lista_existente` é **o mesmo objeto** que `self.lista_original_para_edicao`.
        * Se **sim** (é o mesmo objeto), o usuário está apenas salvando. O loop continua (`continue`).
        * Se **não** (é um objeto diferente), o título colide com outra lista. Exibe `QMessageBox.warning` e `return` (o diálogo permanece aberto).
3.  **Sincronizar Dados:** Se as validações de título passarem:
    * Atualiza os atributos simples em `self.lista` (título, mostrar_titulo, tipo_enumeracao).
    * Chama `self.lista.raiz = self._construir_modelo_da_arvore()` para salvar a estrutura da árvore (View) de volta no Modelo.
4.  **Validar Lista Vazia:** Verifica se `self.lista.raiz.filhos` está vazio (o que aconteceria se o usuário removesse todos os itens). Se estiver, exibe `QMessageBox.warning` e `return` (o diálogo permanece aberto).
5.  **Fechar Diálogo:** Se todas as validações passarem, chama `super().accept()` para fechar o diálogo com um status "Aceito".

#### 5.3. `get_dados_lista(self)` (Método de Acesso)

* **Propósito:** Método público chamado pelo `aba_conteudo` *após* o diálogo ser fechado com sucesso (via `accept()`).
* **Retorno:** Retorna o objeto `self.lista`, que agora está validado e totalmente atualizado com os metadados e a nova estrutura da árvore.


## Documentação: `dialogs.py`

### 1\. Propósito Principal

Este arquivo é um **módulo de utilidade** que agrupa várias janelas de diálogo (`QDialog`) menores e independentes usadas em diferentes partes do aplicativo.

Diferente de `dialogo_figura` ou `aba_conteudo`, este arquivo não foca em uma única funcionalidade "principal", mas serve como uma "caixa de ferramentas" de diálogos para tarefas específicas, como:

1.  **`ReferenciaDialog`**: Criar e editar referências bibliográficas (Livros, Artigos, Sites).
2.  **`DialogoRecuperacao`**: Lidar com a recuperação de arquivos após uma falha do sistema.

(Nota: Este arquivo *costumava* conter `DialogoFigura` e `TabelaDialog`, que foram corretamente refatorados para seus próprios arquivos para melhorar a organização e reduzir a duplicação de código).

### 2\. Tecnologias e Bibliotecas Utilizadas

  * **`PySide6` (Qt for Python):** Usado para todos os elementos de UI.
      * `QDialog`, `QVBoxLayout`, `QFormLayout`, `QDialogButtonBox`: A estrutura básica de todas as janelas.
      * `QComboBox`: Usado crucialmente no `ReferenciaDialog` para trocar o tipo de referência.
      * `QLineEdit`: Para entrada de dados de texto.
      * `QListWidget`: Usado no `DialogoRecuperacao` para listar os arquivos.
      * `QMessageBox`: Para confirmações (ex: "Confirmar Exclusão").
  * **`referencia.py` (Modelo de Dados):** Importa as classes `Livro`, `Artigo`, e `Site` para criar e popular os objetos de referência.
  * **`gerenciador_recuperacao.py` (Não importado, mas relacionado):** O `DialogoRecuperacao` é a interface gráfica para os dados que o `gerenciador_recuperacao` encontra.

### 3\. Arquitetura e Decisões de Design (Classe por Classe)

#### 3.1. Classe `ReferenciaDialog(QDialog)`

Esta é uma janela de diálogo **dinâmica**. Ela muda sua própria interface com base na seleção do usuário.

  * **Estratégia 1: Dicionários de Widgets (`self.campos_livro`, etc.)**

      * O código armazena os `QLineEdit`s específicos de cada tipo em dicionários (`self.campos_livro`, `self.campos_artigo`, `self.campos_site`).
      * **Benefício:** Isso torna a função `update_form_visibility` muito limpa e fácil de gerenciar.

  * **Estratégia 2: O Formulário Dinâmico (`update_form_visibility`)**

      * Este é o "cérebro" do diálogo. Quando o usuário troca o `tipo_combo` (ex: de "Livro" para "Site"), esta função é chamada.
      * **Lógica:**
        1.  Primeiro, ela esconde *todos* os campos específicos (usando `all_specific_fields = {**...}` para unir os dicionários).
        2.  Depois, ela descobre quais campos *devem* aparecer (ex: `fields_to_show = self.campos_site`).
        3.  Finalmente, ela torna visíveis apenas os campos desse conjunto.
      * **Benefício:** Isso é muito mais eficiente do que criar três diálogos separados ou três "páginas" de `QStackedWidget`.

  * **Padrão "Preenchimento e Coleta":**

      * **Preenchimento (`_popular_campos`):** Se um objeto `ref` é passado, ele preenche os campos comuns (título, ano) e, em seguida, usa `isinstance(ref, Livro)` para preencher os campos específicos corretos.
      * **Coleta (`get_data`):** Quando o usuário clica "OK", esta função lê o `tipo_combo.currentText()` e constrói o objeto de dados correto (ex: `Livro(...)`, `Artigo(...)`), coletando os dados dos `QLineEdit`s apropriados.

#### 3.2. Classe `DialogoRecuperacao(QDialog)`

Este diálogo é uma interface crítica de "recuperação de desastres", projetada para ser clara e segura.

  * **Design Focado na Segurança:**
      * A interface não é um simples "OK/Cancelar". Ela usa botões com texto explícito: "Recuperar Selecionados", "Descartar Selecionados", e "Decidir Depois" (`reject()`).
      * **Confirmação Destrutiva:** A ação "Descartar" (que apaga arquivos) é protegida por um `QMessageBox.question` para forçar o usuário a confirmar uma ação que não pode ser desfeita.
  * **Estratégia 1: Armazenamento de Dados em `QListWidgetItem`**
      * O diálogo não armazena apenas o *nome* do arquivo na lista. Ele armazena o *dicionário completo* (`arq_info`) dentro do item da lista:
    <!-- end list -->
    ```python
    item.setData(QtCore.Qt.ItemDataRole.UserRole, arq_info)
    ```
      * **Benefício:** Quando o usuário clica em "Recuperar", a função `_processar_selecao` não precisa procurar os dados novamente. Ela simplesmente pega os itens marcados e extrai o dicionário completo (`item.data(...)`), que já contém o caminho (`recovery_file_path`) necessário.
  * **Estratégia 2: O Sinalizador `self.acao`**
      * As funções `_recuperar_clicado` e `_descartar_clicado` ambas chamam a *mesma* função de lógica, `_processar_selecao`.
      * Elas usam a flag `self.acao = 'recuperar'` ou `self.acao = 'descartar'` para dizer à `_processar_selecao` em qual lista (`self.arquivos_para_recuperar` ou `self.arquivos_para_descartar`) ela deve colocar os itens marcados.

### 4\. "Gambiarras" e Pontos de Atenção

  * **"Gambiarra" Menor (Conversão de Tipo em `get_data`):**
      * A função `get_data` do `ReferenciaDialog` tem blocos `try/except` para converter o "Ano" ou "Páginas" em inteiros (`int(...)`).
      * Se o usuário digitar "ABC" no campo "Ano", o código não dá erro; ele silenciosamente o converte para `0`.
      * **Pró:** Isso impede o programa de travar.
      * **Contra:** Seria melhor validar os campos *antes* de fechar o diálogo (como o `TabelaDialog` faz com o título) e avisar o usuário: "O ano deve ser um número." A forma atual é uma "falha silenciosa".
  * **Duplicação de Código (Refatorada):** Este arquivo costumava conter `TabelaDialog`. Isso foi corrigido movendo `TabelaDialog` para seu próprio arquivo (`dialogo_tabela.py`), o que melhorou muito a manutenção do projeto (seguindo o princípio DRY - Don't Repeat Yourself).


## Documentação: `documento.py`

### 1. Propósito Principal

Este arquivo é o **"cérebro" (ou "esquema") de todo o projeto**. Ele não contém nenhuma lógica de interface (GUI), nem lógica de geração de arquivos (DOCX). Sua única responsabilidade é definir a **estrutura de dados** que armazena *tudo* o que o usuário insere no programa.

Ele é a "fonte da verdade". Todos os outros módulos, como a interface (`aba_conteudo.py`), os geradores (`gerador_docx.py`, `gerador_preview.py`) e o sistema de salvamento (`gerenciador_projeto.py`), leem e escrevem dados com base nas classes definidas aqui.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`dataclasses` (Python):** Esta é a tecnologia central do arquivo.
    * `@dataclass` é um decorador que transforma classes simples em "classes de dados". Ele escreve automaticamente métodos como `__init__`, `__repr__`, e `__eq__` para você.
    * **Benefício:** Isso torna o código incrivelmente limpo, legível e fácil de manter. Em vez de escrever um `__init__` longo para a `Tabela` (com `self.titulo = titulo`, `self.fonte = fonte`, etc.), você apenas declara os campos e seus tipos.
* **`typing` (Python):** Usado para *type hinting* (ex: `List`, `Optional`). Isso não força a verificação de tipos, mas melhora drasticamente a legibilidade e ajuda ferramentas de análise a encontrar bugs.
* **`datetime` (Python):** Usado na `Configuracoes` para definir o `ano` e `mes` atuais como padrão.
* **Módulos do Projeto (Modelos de Dados):**
    * `referencia.py`: Importa as estruturas de dados `Referencia`, `Livro`, `Artigo`, `Site`.
    * `formula.py`: Importa a estrutura de dados `Formula`.

### 3. Arquitetura e Decisões de Design

#### 3.1. As `dataclasses` (Os Modelos)

O arquivo define "modelos" de dados claros para cada entidade do projeto:

* **`Tabela`**: Armazena os dados de uma tabela, incluindo uma `List[List[str]]` (uma lista de listas, representando a grade) e suas opções de formatação (`estilo_borda`, `centralizar_conteudo`).
* **`Figura`**: Armazena os metadados de uma figura, crucialmente separando o `caminho_original` (o arquivo do usuário) do `caminho_processado` (o arquivo otimizado/cortado).
* **`Configuracoes`**: Armazena todos os metadados da "capa" e "folha de rosto" (instituição, cidade, ano, etc.), incluindo os dados do brasão.
* **`Autor`**: Uma classe simples para armazenar o nome do autor.
* **`Capitulo`**: Esta é a estrutura de dados mais importante. É uma **estrutura em árvore recursiva**.
    * Um `Capitulo` tem um `titulo`, um `conteudo` (o texto) e uma `List['Capitulo']` (seus filhos).
    * Isso permite a hierarquia infinita (1., 1.1, 1.1.1, etc.) que o `QTreeWidget` (`aba_conteudo.py`) visualiza.
    * O `is_template_item` é um flag inteligente para diferenciar capítulos-padrão (ex: "INTRODUÇÃO") de capítulos personalizados pelo usuário.

#### 3.2. A Classe `DocumentoABNT` (O Agregador)

Esta não é uma `dataclass`, mas é a classe principal que "agrega" todos os outros modelos. Um objeto `DocumentoABNT` é a **representação completa de um projeto do usuário**.

* **`self.configuracoes`**: Um *objeto* `Configuracoes`.
* **`self.estrutura_textual`**: O *objeto* `Capitulo` raiz, que contém todos os outros capítulos como seus `filhos`.
* **Bancos de Dados (`banco_tabelas`, `banco_figuras`, etc.):** São listas que armazenam *todos* os ativos do projeto. Esta é uma decisão de design crucial:
    * **Design Centralizado:** As figuras e tabelas não são "propriedade" de um capítulo. Elas são armazenadas globalmente no `DocumentoABNT`.
    * **Benefício:** Isso permite que o usuário insira a mesma figura (usando o marcador `{{Figura:Img1}}`) em três capítulos diferentes, sem ter que duplicar o ativo.

#### 3.3. Serialização (A Estratégia de Salvar/Carregar)

O `gerenciador_projeto.py` precisa salvar toda a classe `DocumentoABNT` em um arquivo `documento.json`. As funções `to_dict` e `from_dict` são as "tradutoras" que fazem isso acontecer.

* **`to_dict(self)`:**
    * **Propósito:** Converte o objeto Python (com suas classes customizadas) em um dicionário simples, que pode ser facilmente escrito em JSON.
    * **Estratégia:** Ele usa `self.configuracoes.__dict__` e `[a.__dict__ for a in self.autores]` como um atalho. Como as `dataclasses` armazenam seus dados em `__dict__`, isso é uma forma rápida de serializá-las.
    * **Lógica Customizada:** Para `referencias`, ele precisa adicionar manualmente o `tipo_ref` (ex: "Livro"), pois `isinstance(ref, Livro)` não pode ser salvo em JSON.

* **`from_dict(cls, data)` (Método de Classe):**
    * **Propósito:** Faz o oposto. Recebe um dicionário (lido do JSON) e reconstrói o objeto `DocumentoABNT` com todas as suas classes customizadas.
    * **Lógica Customizada:** Para `referencias`, ele lê o `tipo_ref` e usa um `if/elif` para reconstruir a classe correta (`Livro(**ref_data)`, `Artigo(**ref_data)`).
    * **Lógica Recursiva:** Para a `estrutura_textual`, ele chama `Capitulo.from_dict(data)`, que por sua vez chama `Capitulo.from_dict` para seus filhos, reconstruindo a árvore inteira.

### 4. "Gambiarras" e Pontos de Atenção

* **`referencia.py` e `formula.py` (Dependências Cegas):** Este arquivo importa `Referencia`, `Livro`, `Artigo`, `Site` e `Formula` de outros módulos. Isso significa que o `documento.py` depende *estruturalmente* desses arquivos. Se `formula.py` for alterado, `documento.py` pode quebrar.
* **`Capitulo.pai` (Referência Fraca):** O campo `pai: Optional['Capitulo']` é marcado com `repr=False`. Isso é uma **estratégia essencial** para evitar um *loop infinito de recursão*. Se `repr=True` (o padrão), imprimir um capítulo (`print(capitulo)`) faria o Python tentar imprimir o pai, que tentaria imprimir seus filhos (incluindo o capítulo original), que tentaria imprimir o pai... e o programa travaria.
* **Deserialização de Referências (Frágil):** O `from_dict` usa `ref_data.pop('tipo_ref', None)` e `ref_data.pop('tipo', None)`. Isso é uma pequena "gambiarra" para limpar dados antigos ou conflitantes durante o carregamento, tornando o processo de carregamento mais robusto contra versões antigas do formato de salvamento.


## Documentação: `formula.py`

### 1. Propósito Principal

Este arquivo é um **modelo de dados** (`dataclass`) extremamente focado. Seu único propósito é definir a estrutura de dados `Formula`, que armazena todas as informações necessárias para gerenciar uma fórmula matemática no projeto.

Ele atua como um "contêiner" de dados que é criado e preenchido pelo `DialogoFormula` e, em seguida, armazenado na lista `documento.banco_formulas`.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`dataclasses` (Python):** O módulo `dataclass` é usado para criar a classe `Formula`.
    * **Benefício:** Isso elimina a necessidade de escrever um método `__init__` manual. Os campos são declarados com tipos e valores padrão, tornando o código limpo, legível e fácil de manter.
* **`typing` (Não usado, mas implícito):** Embora não explicitamente importado, o conceito de *type hints* (ex: `str = ""`, `float = 16.0`) é fundamental para o funcionamento das `dataclasses`.

### 3. Arquitetura e Decisões de Design

#### 3.1. A Estrutura da `dataclass Formula`

Cada campo desta classe tem uma responsabilidade clara no fluxo de dados do programa:

* **`legenda: str`**:
    * Este é o "identificador" legível pelo usuário.
    * É usado no `aba_conteudo.py` para exibir na `lista_formulas` (o banco de fórmulas).
    * É usado no `gerador_preview.py` e `gerador_docx.py` para encontrar a fórmula (ex: `{{Formula:Minha Legenda}}`).
    * É usado para gerar a legenda final (ex: "Equação 1 – Minha Legenda").

* **`codigo_latex: str`**:
    * Armazena o código LaTeX bruto (ex: `\frac{...}`).
    * **Fluxo:** É salvo pelo `DialogoFormula` e usado para repopular o editor de LaTeX (`QWebEngineView`) quando o usuário edita uma fórmula existente.

* **`caminho_svg: str`**:
    * Armazena o caminho para o arquivo vetorial `.svg` (ex: `_abnthelper_formulas_svg_temp/tempfile.svg`).
    * Este arquivo é o "original" de alta qualidade gerado pelo MathJax (no navegador) e baixado pelo `DialogoFormula`.
    * É usado pelo `gerador_preview.py` para exibir a fórmula na pré-visualização (o HTML renderiza SVGs perfeitamente).

* **`caminho_processado_png: str`**:
    * Armazena o caminho para o arquivo rasterizado `.png` (ex: `_formulas_processadas/tempfile.png`).
    * Este arquivo é a "cópia de produção" criada pelo `DialogoFormula` (usando o `QSvgRenderer`) a partir do `.svg`.
    * **Propósito:** Este é o arquivo que o `gerador_docx.py` insere no documento `.docx` final, pois o `python-docx` tem um suporte muito mais robusto para PNGs do que para SVGs.

* **`largura_cm: float = 16.0`**:
    * Controla a largura de exibição da fórmula tanto no `.docx` quanto na pré-visualização HTML.
    * O padrão de `16.0` cm (largura máxima da página de 21cm com margens de 3cm/2cm) é uma **decisão de design defensiva**, garantindo que fórmulas muito largas não "vazem" para fora da página por padrão.

* **`numero: int = 0`**:
    * Este campo é um placeholder. Ele é **ignorado** quando o usuário cria a fórmula.
    * Ele só é preenchido *depois*, durante a geração do documento (`gerador_docx.py` e `gerador_preview.py`), quando o `contador_formulas` é incrementado.

### 4. "Gambiarras" e Pontos de Atenção

* **Valor Padrão do LaTeX (`codigo_latex: str = r"\frac{..."`):**
    * Isso é uma estratégia de usabilidade. Quando o usuário clica em "Criar Fórmula", o editor não aparece vazio. Ele aparece com a fórmula de Bhaskara como um exemplo. Isso guia o usuário e mostra a ele a sintaxe esperada.

* **Separação de SVG vs. PNG:**
    * Manter *dois* caminhos de arquivo (`caminho_svg` e `caminho_processado_png`) é uma decisão de design inteligente.
    * **SVG:** É usado pelo `gerador_preview.py` porque navegadores (como o `QWebEngineView`) renderizam SVGs perfeitamente em qualquer zoom, resultando em uma pré-visualização nítida.
    * **PNG:** É usado pelo `gerador_docx.py` porque o `python-docx` (e o próprio MS Word) têm compatibilidade universal com PNGs, enquanto o suporte a SVG pode ser inconsistente.
    * Isso garante a **melhor qualidade no preview** (SVG) e a **maior compatibilidade no arquivo final** (PNG).


## Documentação: `gerador_docx.py`

Este é o módulo **`gerador_docx.py`**. Se o `documento.py` é o "cérebro" e o `aba_conteudo.py` é o "coração" da interface, este arquivo é a **"linha de produção industrial"**.

Sua única responsabilidade é pegar o objeto `DocumentoABNT` (o modelo de dados abstrato) e traduzi-lo em um arquivo físico `.docx` formatado de acordo com as regras da ABNT. Ele é o *backend* do que o `gerador_preview.py` faz no *frontend*.

### 1. Propósito Principal

O `GeradorDOCX` é uma classe de "renderização" (renderização final). Ele consome o objeto `DocumentoABNT` (preenchido pela interface) e o objeto `MotorNormasABNT` (contendo as regras de formatação) para construir, passo a passo, um documento Microsoft Word `.docx` complexo, com seções, numeração de página, estilos e um sumário automatizado.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`python-docx`:** A biblioteca principal. Ela é usada para criar e manipular programaticamente o arquivo `.docx`. Quase todas as operações (adicionar parágrafo, tabela, imagem) dependem dela.
* **`python-docx.oxml` e `qn`:** Esta é uma estratégia de nível avançado. A biblioteca `python-docx` não oferece funções de alto nível para *todas* as funcionalidades do Word (como criar um sumário ou bordas ABNT). Nesses casos, este código "desce" para o nível do XML subjacente (Office Open XML) e constrói os elementos manualmente (ex: `OxmlElement('w:sdt')` para o sumário).
* **`pywin32` (`win32com.client`):** Esta é a "magia negra" do módulo. É uma biblioteca **exclusiva para Windows** que permite ao Python controlar outros aplicativos da Microsoft, como o Word. Ela é usada para uma estratégia crucial:
    1.  O `python-docx` cria um *placeholder* (um marcador de lugar) para o sumário.
    2.  O `pywin32` (se disponível) abre o Microsoft Word em segundo plano (*invisivelmente*), abre o arquivo `.docx` recém-salvo, força o Word a *atualizar* o sumário (preenchendo os números de página), salva o arquivo e fecha o Word.
* **`re` (Python Regex):** Usado para a lógica de *parsing* (análise) de conteúdo.
* **Módulos do Projeto:**
    * `documento.py`: Para importar os modelos de dados (`DocumentoABNT`, `Capitulo`).
    * `normas_abnt.py`: Para importar o `MotorNormasABNT`, que fornece todas as regras de estilo.

### 3. Arquitetura e Decisões de Design

#### 3.1. O "Motor de Seções" (`_gerar_trabalho_academico`)

A formatação ABNT exige que diferentes partes do documento (capa, resumo, conteúdo textual) tenham formatações de página diferentes (ex: sem número de página, com número de página).

O código implementa isso de forma muito inteligente usando **Seções do Word**:

1.  **Seção 1 (Capa):** É a seção padrão. `_renderizar_capa()` é chamada.
2.  **Seção 2 (Folha de Rosto):** O código `self.doc.add_section(WD_SECTION.NEW_PAGE)` cria uma nova seção. A estratégia principal é a linha `section_rosto.footer.is_linked_to_previous = False`. Isso quebra o vínculo com o rodapé da capa, garantindo que o texto "Cidade/Ano" da capa não apareça aqui.
3.  **Seção 3 (Resumo):** O mesmo processo é repetido.
4.  **Seção 4 (Conteúdo Principal):** Esta é a seção mais importante.
    * Ela também é desvinculada (`is_linked_to_previous = False`).
    * A função `_set_page_numbering(section_main)` é chamada. Esta função usa a estratégia do `OxmlElement` para inserir o código de campo XML (`PAGE`) no cabeçalho *apenas desta seção*.
5.  **Seção 5 (Referências):** Esta seção é adicionada, mas *não* é desvinculada (`is_linked_to_previous = True`). Isso faz com que ela *herde* o cabeçalho/rodapé da Seção 4, garantindo que a numeração de página continue corretamente.

#### 3.2. O Parser de Conteúdo (`_renderizar_secoes_recursivamente`)

Esta é a função mais importante do gerador. Ela percorre a árvore de capítulos e analisa o `.conteudo` de cada um.

* **O Regex (A Estratégia de Parsing):**
    `padrao = r"\{\{(?:(Tabela|Figura|Formula):([^}]+)|(QUEBRA_PAGINA|PAGINA_EM_BRANCO))\}\}"`
    Esta é uma expressão regular complexa projetada para encontrar *todos* os marcadores. Ela captura os marcadores em 3 grupos:
    * `Grupo 1`: O tipo (Tabela, Figura, Formula)
    * `Grupo 2`: O título (ex: "Minha Figura 1")
    * `Grupo 3`: O comando (ex: "QUEBRA_PAGINA")
* **O Loop (A Estratégia de Iteração):**
    A função `re.split(padrao, ...)` quebra o texto em uma lista "plana". Por exemplo:
    `"Texto A {{Figura:Img1}} Texto B"`
    Vira:
    `['Texto A ', 'Figura', 'Img1', None, ' Texto B ']`
    A lógica `while idx < len(partes): ... idx += 4` é uma estratégia inteligente para iterar sobre essa lista de 4 em 4 (Texto, Grupo1, Grupo2, Grupo3), processando o texto normal e, em seguida, processando o marcador que o segue.
* **Quebra de Página de Capítulo:** A lógica `if nivel_titulo == 1 and i > 1:` implementa a regra da ABNT de que todo capítulo principal (2, 3, 4...) deve começar em uma nova folha.

#### 3.3. Estratégias de Renderização Específicas

* **Brasões (`_renderizar_capa`):** A ABNT não dita regras de brasão. Para criar o layout "Esquerda-Centro-Direita" (`Lados (Esquerdo e Direito)`), o código usa um truque de layout clássico: **cria uma tabela de 3 colunas sem bordas**. Isso permite alinhar imagens e texto horizontalmente, algo que é muito difícil de fazer no Word usando apenas parágrafos.
* **Tabelas (`_renderizar_tabela`):** A função `self.regras.aplicar_estilo_tabela_abnt(t)` é outra estratégia de `oxml`. Ela remove programaticamente todas as bordas (internas e externas) e depois adiciona *apenas* as bordas superior, inferior e de cabeçalho, como a ABNT exige.
* **Fórmulas (`_renderizar_formula`):** A ABNT exige que fórmulas sejam centralizadas, mas sua numeração (ex: "(1)") seja alinhada à direita.
    * **A "Gambiarra":** Tentar fazer isso em um único parágrafo é quase impossível.
    * **A Solução (Estratégia):** O código usa **Tab Stops (Paradas de Tabulação)**. Ele define um Tab Stop *Centralizado* no meio da página (8cm) e um Tab Stop *Direito* no final (16cm).
    * Em seguida, ele insere `\t` (pula para o centro) -> insere a imagem da fórmula -> insere `\t` (pula para a direita) -> insere o número `(1)`.

### 4. "Gambiarras" e Pontos de Atenção

* **A Dependência do `pywin32`:** Esta é a maior "gambiarra" e a maior fraqueza do módulo. A função `_atualizar_sumario_com_word` **só funciona em Windows** e **só funciona se o usuário tiver o Microsoft Word instalado**.
    * **Mitigação:** O código lida com isso de forma defensiva com o `try/except ImportError` no topo e o `if not WIN32_AVAILABLE:`, garantindo que o programa não trave no macOS ou Linux, mas o sumário gerado nesses sistemas não terá números de página ou links.
* **Validação de Caminho de Imagem:** As funções `_renderizar_figura` e `_renderizar_formula` incluem blocos `try/except`. Se o arquivo de imagem (ex: `.png`) não for encontrado no disco, o programa não trava. Em vez disso, ele insere uma mensagem de erro (ex: `[ERRO: Imagem '...' não encontrada]`) diretamente no documento `.docx`, informando ao usuário o que deu errado.
* **Duplicação de Código (Corrigida):** O código `_renderizar_tabela` *tinha* um bloco `if tabela_obj.fonte:` duplicado (um bug de copiar/colar), que foi corrigido na versão que você enviou. Isso destaca que, embora funcional, o código poderia ser refatorado para ser mais limpo (DRY - Don't Repeat Yourself).


## Documentação: `gerador_preview.py`

### 1. Propósito Principal

Este módulo é o **Simulador Visual (Frontend)** do seu aplicativo. Seu único propósito é ler o objeto `DocumentoABNT` (o "cérebro") e gerar um único arquivo **HTML/CSS** que *simula* a aparência de um documento ABNT final, incluindo:

* **Paginação:** Simula as páginas A4 (`<div class="pagina">`).
* **Margens:** Simula as margens ABNT (3cm, 2cm, etc.) usando `padding` no CSS.
* **Elementos:** Renderiza capas, sumário, texto, figuras, tabelas e fórmulas.
* **Estimativa de Paginação:** Sua função mais complexa é *prever* a altura de cada elemento (texto, imagens) para "adivinhar" em qual página cada capítulo começará. Isso é essencial para gerar o **Sumário** com os números de página corretos *antes* de renderizar o documento.

Este módulo é o "gêmeo" do `gerador_docx.py`. O `gerador_preview` cria o HTML (o visual rápido), e o `gerador_docx` cria o `.docx` (o arquivo final).

### 2. Tecnologias e Bibliotecas Utilizadas

* **`PIL (Pillow)` - `Image` e `ImageFont`:** Esta é a tecnologia-chave para a "simulação exata".
    * `ImageFont.truetype("times.ttf", ...)`: Carrega a fonte Times New Roman do sistema operacional.
    * `font_medidor.getbbox(palavra)`: **A Estratégia Central.** Esta função é usada para *medir a largura exata em pixels* de cada palavra. Isso elimina a necessidade de "adivinhar" o tamanho do texto (o `CARACTERES_POR_LINHA` foi removido/ignorado).
    * `Image.open()`: Usado pela função `_get_image_aspect_ratio` para abrir arquivos `PNG/JPG` e ler suas dimensões reais.
* **`re` (Python Regex):** Usado extensivamente para duas tarefas:
    1.  **Parsing de Marcadores:** A expressão regular `padrao = r"\{\{(?:(Tabela|...)...\}\}"` é usada para encontrar e extrair os marcadores (como `{{Figura:Img1}}` ou `{{QUEBRA_PAGINA}}`) do texto do usuário.
    2.  **Parsing de SVG:** Usado em `_get_svg_aspect_ratio` para "ler" o arquivo `.svg` como texto e encontrar os atributos `viewBox` ou `width`/`height` para calcular a proporção da fórmula.
* **`os`, `math`:** Bibliotecas padrão do Python para manipulação de caminhos de arquivo e cálculos (como `math.ceil`).

### 3. Arquitetura e Decisões de Design

Este módulo opera em duas fases principais, ambas iniciadas por `gerar_html()`:

#### Fase 1: Simulação e Coleta (`_estimar_paginacao_e_coletar_sumario`)

Esta fase é uma "bola de cristal". Ela precisa construir o Sumário (que vai na Página 3-4), mas para fazer isso, ela precisa saber em qual página o "Capítulo 3" (que vai na Página 20) começará.

1.  **Lógica:** A função `coletar_recursivo` "finge" que está renderizando o documento.
2.  Ela percorre os capítulos e o texto.
3.  **Medição de Texto:** Para cada parágrafo, ela chama `simular_paragrafo_quebravel`, que usa a função de medição exata (`_calcular_altura_paragrafo`) para saber quantas linhas o texto ocupará.
4.  **Medição de Imagem:** Para cada Figura (`{{Figura:...}}`), ela chama `_get_image_aspect_ratio` para obter a proporção real (altura/largura) da imagem `PNG/JPG`. Ela então calcula a altura de exibição (ex: `altura_imagem_cm = obj.largura_cm * aspect_ratio`) e subtrai isso da "altura restante" da página.
5.  **Medição de Fórmula:** Para cada Fórmula (`{{Formula:...}}`), ela chama `_get_svg_aspect_ratio` para obter a proporção do `SVG` e calcular sua altura exata.
6.  **Quebra de Página:** Quando a `altura_restante` não é suficiente para o próximo elemento (texto, título, imagem), a função `simular_nova_pagina()` é chamada, e o `pagina_atual` é incrementado.
7.  **Resultado:** Ao final, a lista `self.entradas_sumario` está cheia com os números de página corretos (ex: `[{titulo: "CONCLUSÃO", pagina: 25}]`).

#### Fase 2: Renderização (`_renderizar_secoes_recursivamente_html`, etc.)

Esta fase é a "impressão" real. Ela percorre o documento *novamente*, mas desta vez ela gera o HTML.

1.  **Páginas Pré-Textuais:** Renderiza a Capa, Folha de Rosto, Resumo e o Sumário (agora com os dados corretos da Fase 1).
2.  **Lógica de Renderização:** `_renderizar_secoes_recursivamente_html` faz o mesmo que a Fase 1, mas em vez de apenas *simular*, ela chama `self._adicionar_paragrafo_quebravel` e `self._adicionar_elemento_bloco`.
3.  **Controle de Paginação:** `_adicionar_paragrafo_quebravel` é a função mais inteligente. Ela também mede o texto (assim como a simulação), mas desta vez ela *corta* o texto se ele não couber, colocando o `texto_para_pagina_atual` na página atual e passando o `texto_restante` para a próxima chamada (`_nova_pagina()`).
4.  **Renderização de Imagens:** As funções `_renderizar_figura_html` e `_renderizar_formula_html` criam tags `<img>`. Elas usam uma estratégia crucial:
    * **`file:///{caminho_abs}`:** Elas não copiam a imagem; elas apontam o `src` da imagem diretamente para o arquivo local no computador do usuário (ex: `C:/Users/.../_imagens_processadas/img.png`). Isso só funciona porque o `QWebEngineView` (o navegador) tem permissão para acessar arquivos locais.
5.  **Renderização de Brasão:** A função `_renderizar_cabecalho_capa_html` usa a estratégia de layout de 3 colunas (reutilizando a lógica `brasoes-lado-a-lado`) para lidar com todos os casos de alinhamento lateral, inserindo `<div></div>` vazios como *placeholders* para os lados esquerdo ou direito, se não houver brasão.

### 4. "Gambiarras" e Pontos de Atenção

* **Estratégia: Medição Exata de Fonte (`_calcular_altura_paragrafo`)**
    * Esta é a solução mais avançada e precisa do código. Ela elimina a necessidade de "adivinhar" (`CARACTERES_POR_LINHA`).
    * **Risco (A "Gambiarra" do Caminho):** Ela depende fundamentalmente de `font_path = "C:/Windows/Fonts/times.ttf"`. Isso é uma "gambiarra" específica do Windows. Este código **falhará imediatamente** em um macOS ou Linux, pois o `ImageFont.truetype` não encontrará a fonte e usará uma fonte padrão do Pillow (que tem métricas diferentes), quebrando toda a simulação.
* **"Gambiarra": Lógica de Quebra de Palavra Longa (o "AAAAA..." caso)**
    * A função `_calcular_altura_paragrafo` tem um loop `while largura_linha_atual > self.LARGURA_CONTEUDO_PX:`. Esta é a correção para o bug "AAAAA...". Ela "finge" quebrar a palavra longa em várias linhas, subtraindo a largura da página da largura da palavra até que ela caiba.
    * A função `_adicionar_paragrafo_quebravel` tem uma lógica ainda mais complexa para *realmente* quebrar a palavra longa, estimando quantos caracteres cabem (`chars_na_linha1 + (linhas_restantes * chars_por_linha_normal)`). Isso é uma "gambiarra" baseada em estimativa (usando `LARGURA_CHAR_MEDIO_PX`), que funciona, mas é menos precisa do que a quebra por palavra.
* **Regras "Viúva/Órfã":**
    * A lógica `if altura_que_cabe <= (ALTURA_LINHA_TEXTO * 2):` e `if html.startswith("<h1"): altura_necessaria += ALTURA_LINHA_TEXTO * 2` são estratégias de tipografia. Elas garantem que um título não fique sozinho no final de uma página e que um parágrafo não deixe uma única linha órfã, forçando uma quebra de página mais cedo.
* **CSS `overflow: hidden;`:**
    * Esta é a "rede de segurança". Se, apesar de toda a medição exata, o simulador errar por 1 pixel e o texto "vazar" 1 pixel além da margem inferior de `2cm`, esta regra de CSS simplesmente *corta* e *esconde* o texto vazado, impedindo que ele apareça na página seguinte e quebre o layout.


## Documentação: `gerenciador_config.py`

### 1. Propósito Principal

Este arquivo é um módulo de serviço (utility) que gerencia o arquivo `abnf_helper_config.json`. Sua responsabilidade é salvar e carregar todas as configurações que o aplicativo deve "lembrar" após ser fechado.

Suas funções principais são:
1.  **Gerenciar Configurações:** Salvar e carregar as configurações de *features* do programa, como o auto-save e o backup automático (`recovery` e `backup`).
2.  **Gerenciar Projetos Recentes:** Manter a lista de projetos que o usuário abriu recentemente, que é exibida na `tela_inicial.py`.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`json` (Biblioteca Padrão do Python):** Esta é a tecnologia central do módulo. Um arquivo JSON (`abnf_helper_config.json`) é usado como um banco de dados simples para armazenar as configurações. É uma escolha de design leve, humana-legível e que não requer bancos de dados externos (como SQLite).
* **`os` (Biblioteca Padrão do Python):** Usado para interações com o sistema de arquivos, como verificar se o arquivo de configuração existe (`os.path.exists`) e para normalizar caminhos de arquivo (`os.path.abspath`, `os.path.basename`).
* **`datetime` (Biblioteca Padrão do Python):** Usado para uma estratégia específica: adicionar um *timestamp* a cada projeto recente.

### 3. Arquitetura e Decisões de Design

Este módulo é um "singleton" funcional (um módulo cujas funções são chamadas diretamente, sem instanciar uma classe).

#### 3.1. Estratégia: Migração de Configuração e "Schema-on-Read"

A função `carregar_config()` é a mais inteligente do módulo. Ela não apenas carrega o JSON, mas também **garante a compatibilidade com versões futuras** do programa.

* **`get_default_config()`:** Esta função atua como o "schema" (a estrutura) da configuração.
* **Estratégia de `setdefault()`:** Quando `carregar_config()` é chamada, ela usa `config.setdefault('backup', defaults['backup'])`.
    * **O que isso faz:** Se o usuário está abrindo uma nova versão do seu programa que tem a *feature* "backup", mas o seu arquivo `config.json` antigo não tem essa chave, `setdefault` a adiciona automaticamente. Isso é uma **migração de dados simples e robusta**. O programa não quebra; ele apenas adiciona a nova configuração padrão.
* **Estratégia de Limpeza:** A linha `del config['recovery']['autosave_interval_min']` é uma migração *explícita*. Ela mostra que uma versão *anterior* do programa usava uma chave chamada `autosave_interval_min`, que agora é obsoleta. O código a remove para evitar conflitos com a nova chave `autosave_periodic_interval_min`.

#### 3.2. Gerenciamento de Projetos Recentes (MRU)

A lista de projetos recentes (MRU - Most Recently Used) não é uma lista simples; ela é gerenciada de forma inteligente:

1.  **Estratégia do Timestamp:** Quando `add_projeto_recente` é chamado, ele não apenas salva o caminho, mas também salva o `datetime.now().timestamp()`.
2.  **Lógica de Re-ordenação:** A função `add_projeto_recente` primeiro *remove* qualquer entrada antiga daquele projeto e, em seguida, *insere* (`.insert(0, ...)`) a nova entrada no **topo** da lista.
3.  **Resultado:** A função `get_projetos_recentes` então ordena (`sort(...)`) a lista pelo `timestamp`. Isso garante que a `tela_inicial` sempre mostre os projetos na ordem exata em que foram acessados pela última vez, que é o comportamento que o usuário espera.

#### 3.3. "Gambiarra": A Blindagem (Defensive Programming)

Este módulo se comunica com o `gerenciador_recuperacao.py` (que lida com falhas). O `gerenciador_recuperacao` cria arquivos temporários que terminam em `.abnf.recovery`.

* **O Risco:** O programa poderia, acidentalmente, tentar salvar um desses arquivos de *recuperação* na lista de projetos *recentes*, "poluindo" a tela inicial do usuário com arquivos temporários.
* **A "Blindagem" (Estratégia):** As funções `get_projetos_recentes` e `add_projeto_recente` contêm blocos de "BLINDAGEM" (comentados no código). Elas verificam explicitamente se o caminho do arquivo termina com `.abnf.recovery` e, se terminar, **recusam-se** a adicioná-lo à lista.
* **Resultado:** É uma decisão de design defensiva e inteligente que impede a contaminação dos dados do usuário.

### 4. "Gambiarras" e Pontos de Atenção

* **"Gambiarra": Localização do Arquivo de Configuração**
    * A constante `CONFIG_FILE = "abnf_helper_config.json"` define que o arquivo JSON será salvo no mesmo diretório onde o script (`main_app.py`) está sendo executado.
    * **Desvantagem:** Se o usuário mover a pasta do programa (ex: de `Downloads` para `Documentos`), o `config.json` antigo ficará para trás e o programa será "resetado" (perdendo a lista de recentes).
    * **Alternativa (Mais Complexa):** Aplicações profissionais geralmente salvam configurações em pastas de dados do usuário (ex: `%APPDATA%` no Windows). A abordagem atual é uma "gambiarra" em favor da **simplicidade** (o programa é totalmente "portátil").
* **"Gambiarra" (Menor): Salvamento Não-Atômico**
    * A função `salvar_config` abre o `CONFIG_FILE` e o sobrescreve (`'w'`).
    * **Risco:** Se o computador desligar *exatamente* no milissegundo em que o arquivo estiver sendo salvo, o `config.json` pode ficar corrompido (vazio).
    * **Alternativa (Mais Complexa):** Um "salvamento atômico" (salvar como `config.json.tmp` e depois renomear para `config.json`) resolveria isso, mas para um arquivo de configuração simples, o risco é mínimo e a "gambiarra" atual é aceitável.


## Documentação: `gerenciador_projeto.py`

### 1. Propósito Principal

Este módulo é o **"Cofre"** do seu aplicativo. Sua única responsabilidade é lidar com a **serialização** (Salvar) e **desserialização** (Carregar) de todo o estado do projeto de e para o disco.

Ele é o componente que define o seu formato de arquivo personalizado `.abnf`. Ele pega o objeto `DocumentoABNT` (que vive na memória) e o empacota em um único arquivo, e vice-versa.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`zipfile` (Biblioteca Padrão do Python):** Esta é a tecnologia-chave. O arquivo `.abnf` é, na verdade, um arquivo `.zip` disfarçado. Esta biblioteca é usada para criar o arquivo zip (`salvar_projeto`) e para extraí-lo (`carregar_projeto`).
* **`json` (Biblioteca Padrão do Python):** Usado para salvar a *estrutura* do documento (os metadados, o texto dos capítulos, etc.). O arquivo `documento.json` dentro do zip é o "cérebro" do projeto salvo.
* **`tempfile` (Biblioteca Padrão do Python):** Usado para criar diretórios temporários seguros. Isso é uma estratégia crucial para um salvamento e carregamento robusto.
* **`shutil` (Biblioteca Padrão do Python):** Usado para operações de arquivo de alto nível, como copiar imagens (`shutil.copy2`) e criar o arquivo zip (`shutil.make_archive`).
* **`copy.deepcopy`:** Usado para criar uma cópia completa em memória do objeto `DocumentoABNT` antes de salvá-lo.
* **Módulos do Projeto:**
    * `documento.py`: Essencial, pois ele precisa do `DocumentoABNT.to_dict()` e `DocumentoABNT.from_dict()` para traduzir o objeto para JSON.
    * `gerenciador_config.py`: Usado no final do salvamento para adicionar o projeto à lista de "Projetos Recentes".

### 3. Arquitetura e Decisões de Design

#### 3.1. O Formato `.abnf` (Uma Estratégia de ZIP)

A decisão de usar um arquivo `.zip` renomeado para `.abnf` é uma **estratégia de design excelente e padrão da indústria** (o próprio formato `.docx` do Microsoft Word funciona exatamente assim).

* **Benefícios:**
    1.  **Portabilidade:** Todos os ativos (imagens, fórmulas) e o texto são agrupados em um **único arquivo**. O usuário pode enviar esse arquivo `.abnf` por e-mail, e ele contém tudo.
    2.  **Não-Corrupção:** O texto (JSON) e as imagens (ativos binários) não são misturados.
    3.  **Depuração:** Se um arquivo `.abnf` ficar corrompido, você pode renomeá-lo para `.zip` e abri-lo manualmente para inspecionar o `documento.json` e as imagens.

#### 3.2. O Processo de `salvar_projeto` (Serialização)

Este processo é muito robusto e segue etapas claras:

1.  **Criar Cópia:** `copy.deepcopy(documento)` é a primeira etapa. Isso é uma **estratégia de segurança**. O código não salva o objeto `documento` *vivo* que a interface está usando. Ele congela uma cópia. Isso impede que o usuário faça uma alteração na interface *enquanto* o salvamento está ocorrendo, o que poderia corromper os dados.
2.  **Criar Diretório Temporário:** `tempfile.TemporaryDirectory()` cria uma pasta segura (ex: `C:\Temp\abnf_save_...`).
3.  **Organizar Ativos:** O código cria subpastas (`imagens/`, `formulas_svg/`, `brasoes/`) dentro da pasta temporária.
4.  **Processar Ativos (A "Correção do Brasão"):**
    * O código **copia** (`shutil.copy2`) os arquivos *já processados* (ex: `_brasoes_processados/img_cortada.png`) do diretório do aplicativo para a pasta temporária (`temp_dir/brasoes/`).
    * **Estratégia de Caminho Relativo:** Ele então **sobrescreve** o caminho no objeto `doc_para_salvar` (ex: `cfg.caminho_brasao_esquerdo_processado`) para ser um *caminho relativo* (ex: `"brasoes/img_cortada.png"`).
5.  **Serializar o "Cérebro":** Ele chama `doc_para_salvar.to_dict()` (que agora contém os caminhos relativos) e salva o resultado como `documento.json` na pasta temporária.
6.  **Empacotar:** `shutil.make_archive(...)` transforma a pasta temporária inteira em um arquivo `.zip`.
7.  **Limpeza:** O `with tempfile.TemporaryDirectory()` garante que a pasta temporária seja automaticamente excluída, mesmo se o salvamento falhar.

#### 3.3. O Processo de `carregar_projeto` (Desserialização)

Este processo é o inverso exato do salvamento e é a razão pela qual a estratégia do caminho relativo funciona.

1.  **Criar Diretório Temporário:** Ele cria um *novo* diretório temporário (`self.diretorio_temporario_atual`).
2.  **Extrair:** `zipfile.ZipFile(...).extractall()` descompacta todo o `.abnf` (o `documento.json` e todas as pastas de imagem) neste novo local temporário.
3.  **Desserializar o "Cérebro":** Ele carrega o `documento.json` e usa `DocumentoABNT.from_dict()` para recriar o objeto `DocumentoABNT` na memória. Neste ponto, os caminhos das imagens ainda são *relativos* (ex: `"brasoes/img_cortada.png"`).
4.  **Estratégia de Re-hidratação de Caminho:** O código então itera sobre todos os brasões e figuras, pegando o caminho relativo e **juntando-o** (`os.path.join`) com o caminho da pasta temporária.
    * `cfg.caminho_brasao... = os.path.join(self.diretorio_temporario_atual, ...)`
    * **Resultado:** O objeto `DocumentoABNT` que é retornado ao `main_app` agora tem **caminhos absolutos** (ex: `C:\Temp\abnf_load_...\brasoes\img_cortada.png`) que são válidos e apontam para os arquivos que acabaram de ser extraídos.

### 4. "Gambiarras" e Pontos de Atenção

* **Função `_processar_imagem_brasao` (Código Morto/Legado):**
    * A nota nesta função é crucial: `NOTA: Esta função é usada pelo código antigo de salvamento.`
    * **Risco (Gambiarra Menor):** Isso é "código morto". A função `salvar_projeto` (corrigida) não a utiliza mais. Ela provavelmente foi mantida para referência ou por segurança. Em um projeto final, isso deveria ser removido para evitar confusão, pois ela contém a lógica *antiga* e *bugada* de reprocessar o brasão.
* **Gerenciamento de Estado Temporário:**
    * A classe armazena `self.diretorio_temporario_atual`. As funções `_limpar_diretorio_temporario()` e `fechar_projeto()` são essenciais para excluir esta pasta quando o usuário abre um novo projeto ou fecha o aplicativo.
    * **Risco:** Se o aplicativo travasse *antes* de `fechar_projeto()` ser chamado, essa pasta temporária (`abnf_load_...`) ficaria "órfã" no disco, desperdiçando espaço. Isso é um risco normal e aceitável do uso de diretórios temporários gerenciados manualmente.


## Documentação: `gerenciador_recuperacao.py`

### 1. Propósito Principal

Este módulo gerencia duas redes de segurança distintas, mas relacionadas:

1.  **Recuperação de Falhas (Auto-Save):** Protege contra *travamentos* do programa ou desligamentos inesperados. Ele salva periodicamente (a cada 10 minutos, definido no `gerenciador_config.py`) uma cópia de recuperação do trabalho do usuário em um local seguro.
2.  **Backup de Versão (On-Save):** Protege contra *erros do usuário* (ex: deletar um capítulo inteiro e salvar). Cada vez que o usuário clica em "Salvar", este módulo primeiro faz um backup (`.abnf.bak`) da versão *anterior* do arquivo.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`os`, `shutil`, `json`, `datetime`, `time` (Bibliotecas Padrão):**
    * `os` e `pathlib.Path`: Usados extensivamente para criar e manipular caminhos de arquivo de forma segura e compatível com diferentes sistemas operacionais.
    * `shutil.copy2`: Usado para criar o arquivo de backup, pois `copy2` preserva metadados (como data de modificação).
    * `json`: Usado para salvar o arquivo de *metadados* (`.json`) que acompanha o arquivo de recuperação.
    * `datetime`: Usado para criar *timestamps* (carimbos de data/hora) para os nomes dos arquivos de backup e para registrar quando um auto-save ocorreu.

* **`pathlib.Path` (A Estratégia Elegante):**
    * O código usa `pathlib` em vez de `os.path.join` em muitos lugares. Esta é uma decisão de design moderna.
    * **Exemplo:** `RECOVERY_DIR = Path(os.getenv('LOCALAPPDATA', Path.home())) / 'ABNTHelper' / 'recovery'`
    * **Benefício:** A sobrecarga da barra (`/`) torna a junção de caminhos mais limpa e legível do que `os.path.join(os.path.join(...))`.
    * **Exemplo 2:** `caminho_recuperacao.with_suffix('.json')` é uma forma muito mais robusta de trocar "arquivo.abnf.recovery" por "arquivo.json" do que fazer `replace()` manual.

### 3. Arquitetura e Decisões de Design

#### 3.1. Lógica de Recuperação de Falhas (Auto-Save)

Esta é a lógica mais complexa.

* **"Gambiarra" 1: O Diretório `RECOVERY_DIR` (`%LOCALAPPDATA%`)**
    * **Decisão:** O auto-save *não* é salvo ao lado do arquivo `.abnf` do usuário. Ele é salvo em uma pasta "escondida" do sistema (`C:\Users\Usuario\AppData\Local\ABNTHelper\recovery`).
    * **Por quê?** Isso é uma estratégia crucial. Se o usuário estiver trabalhando em um pen drive e o pen drive for removido, o programa ainda pode fazer o auto-save no disco local, salvando o trabalho do usuário. Também evita "poluir" a pasta do usuário com arquivos `.recovery`.
* **`get_caminho_recuperacao` (O "Gerador de Nomes")**
    * **Caso A (Projeto Salvo):** `nome_base = str(hash(os.path.abspath(...)))`.
        * **Estratégia:** O nome do arquivo de recuperação é um *hash* (um número longo, ex: `87912...231.abnf.recovery`). Por que não usar o nome original (ex: `TCC.abnf.recovery`)? Para evitar conflitos. Se o usuário tiver dois arquivos chamados `TCC.abnf` em pastas diferentes, o `hash` do caminho completo (`C:\...`) garante que cada um tenha um arquivo de recuperação *único*.
    * **Caso B (Novo Projeto):** `nome_base = f"novo_projeto_{int(time.time())}"`.
        * **"Gambiarra":** Para um projeto que nunca foi salvo, não há caminho para "hashear". A solução é criar um nome baseado no *timestamp* atual (ex: `novo_projeto_167888...`). Isso é intencionalmente único e impossível de recriar.
* **O "Arquivo Gêmeo" (Metadados):**
    * A função `salvar_recuperacao` não salva apenas o arquivo `.abnf.recovery`. Ela também salva um `.json` com o mesmo nome.
    * **Por quê?** O arquivo `.recovery` é binário (zip). O `.json` é texto e armazena os *metadados* (como o nome original do projeto, ex: "Meu TCC.abnf", e a data do save) que são mostrados ao usuário na `DialogoRecuperacao` na próxima vez que ele abre o app.
* **A "Gambiarra" da Limpeza Dupla:**
    * O módulo tem duas funções de limpeza: `limpar_recuperacao` e `limpar_recuperacao_pelo_caminho_direto`.
    * **Por quê?** `limpar_recuperacao` tenta *recriar* o nome do arquivo usando o `hash()` (Caso A). Isso funciona bem quando o usuário salva ou fecha um projeto *existente*.
    * `limpar_recuperacao_pelo_caminho_direto` é a "blindagem". Ela é usada quando o usuário *descarta* um arquivo de recuperação. Como é impossível recriar o nome de um "Novo Projeto" (Caso B), a `DialogoRecuperacao` passa o caminho *exato* do arquivo a ser deletado.

#### 3.2. Lógica de Backup (On-Save)

Esta lógica é mais simples e direta:

* **Localização:** Os backups são salvos em uma subpasta `.abnf_backups` *ao lado* do arquivo original do usuário.
    * **Benefício:** O usuário pode encontrar seus próprios backups facilmente. O `.` no nome da pasta a torna "semi-oculta" na maioria dos sistemas.
* **Nomeação:** Os backups são nomeados com um timestamp (ex: `MeuTCC_2025-11-08_14-30-01.abnf.bak`). Isso é muito melhor do que `MeuTCC.bak` (que seria sobrescrito).
* **Limpeza (`_limpar_backups_antigos`):**
    * Esta é uma função de "rodízio" (log rotation).
    * Ela lê *todos* os backups `.bak` na pasta.
    * Ela os ordena pela data de modificação (`os.path.getmtime`), do mais novo para o mais antigo.
    * Ela então **exclui** todos os arquivos que estiverem além do limite (`max_backups`, que está definido como 10 no `gerenciador_config.py`).
    * **Resultado:** O usuário sempre terá os 10 backups mais recentes do seu projeto, de forma automática.


## Documentação: `latex_renderer.html`

### 1. Propósito Principal

Este arquivo é o **renderizador de LaTeX em tempo real**. Sua única função é fornecer um ambiente web (HTML, CSS, JavaScript) que é carregado dentro de um `QWebEngineView` (o navegador embarcado) no `DialogoFormula`.

Ele é a "ponte" que permite ao seu aplicativo PySide6 usar a poderosa biblioteca **MathJax** (baseada em JavaScript) para converter texto LaTeX digitado pelo usuário em uma fórmula visual e, subsequentemente, em um arquivo de imagem SVG.

### 2. Tecnologias e Bibliotecas Utilizadas

* **HTML5:** Define a estrutura da página: um `<textarea>` para o editor, uma `div` para os controles (botão, checkbox) e uma `div` para a pré-visualização.
* **CSS:** Usado para estilizar a página.
    * **Estratégia de Layout (CSS Grid):** O `display: grid` e `grid-template-rows: 40% auto 1fr;` é uma decisão de design inteligente. Em vez de usar Flexbox (que pode ser "mole"), o Grid cria um layout *rígido* onde o editor de texto tem 40% da altura, os controles têm altura automática, e o painel de preview (`#preview-container`) ocupa **todo o espaço restante** (`1fr`). Isso garante que o preview não "encolha" quando o usuário redimensiona a janela.
* **JavaScript (Puro / "Vanilla"):** Esta é a lógica principal.
    * **MathJax (Biblioteca Externa):** Importada de um CDN (`src="...mathjax@3..."`). Esta é a biblioteca que faz todo o trabalho pesado de converter LaTeX (ex: `\frac`) em uma imagem vetorial (SVG).
    * **`XMLSerializer` e `Blob` (APIs do Navegador):** Usadas para converter o SVG renderizado em um arquivo que pode ser baixado.

### 3. Arquitetura e Decisões de Design

#### 3.1. A "Ponte" de Comunicação (Python <-> JavaScript)

Este arquivo foi projetado especificamente para "conversar" com o `DialogoFormula.py`. Ele faz isso expondo funções globais no objeto `window` do JavaScript:

* **`window.setEditorContent(content)`:**
    * **Direção:** Python -> JavaScript.
    * **Propósito:** O `DialogoFormula` chama esta função (em `_on_load_finished`) para preencher o `<textarea>` com o código LaTeX salvo quando o usuário está *editando* uma fórmula existente.
* **`window.getEditorContent()`:**
    * **Direção:** JavaScript -> Python.
    * **Propósito:** O `DialogoFormula` chama esta função (em `trigger_save_process`) para "perguntar" ao JavaScript qual é o código LaTeX que o usuário digitou antes de salvar.
* **`window.prepareAndTriggerDownload()`:**
    * **Direção:** Python -> JavaScript (Iniciação); JavaScript -> Python (Resultado).
    * **Propósito:** Esta é a estratégia de salvamento. O Python a chama quando quer salvar.

#### 3.2. A Lógica de Renderização (MathJax)

* **`renderLatex()` (Função Principal):**
    * **"Gambiarra" (Menor) de LaTeX:** O código `if (!latexCode.startsWith('$$')...)` é uma "ajuda" automática. Se o usuário digitar apenas `x^2`, o código adiciona os delimitadores `$$...$$` necessários para que o MathJax o reconheça como um bloco de fórmula.
    * **Renderização Assíncrona:** A chamada `MathJax.typesetPromise([preview])` é **assíncrona**. O código não bloqueia; ele "pede" ao MathJax para renderizar e continua. Isso é essencial para manter a interface fluida.
* **Estratégia de Desempenho (`debounceRender`)**
    * O código **não** chama `renderLatex()` a cada tecla digitada. Isso travaria o editor.
    * Em vez disso, ele usa um *debounce* de 500ms. Quando o usuário digita, um timer é iniciado. Se ele digitar outra tecla, o timer é resetado. A renderização só acontece 500ms *depois* que o usuário **parou** de digitar.
    * Isso é um pilar fundamental para o bom desempenho da ferramenta.

#### 3.3. A Lógica de Salvamento (`prepareAndTriggerDownload`)

Esta é a "coreografia" complexa que se conecta ao `DialogoFormula.py`:

1.  `await renderLatex()`: Garante que a fórmula esteja 100% renderizada.
2.  `preview.querySelector('mjx-container > svg')`: O MathJax não cria um SVG simples; ele o envolve em *containers*. Este seletor "cava" através desses containers para encontrar o elemento `<svg>` bruto.
3.  `svg.setAttribute('xmlns', ...)`: O SVG gerado pelo MathJax não tem o atributo `xmlns` (namespace XML), que é *obrigatório* para que ele seja um arquivo `.svg` válido. Esta linha o adiciona manualmente. **Esta é a "gambiarra" mais importante de todo o arquivo.**
4.  `XMLSerializer().serializeToString(svg)`: Converte o objeto SVG do DOM em uma string de texto (ex: `<svg>...</svg>`).
5.  `new Blob(...)`: Cria um "arquivo" em memória com essa string de texto.
6.  `URL.createObjectURL(blob)`: Cria um link temporário para esse arquivo em memória (ex: `blob:http://.../1234-abcd`).
7.  `link.download = "formula.svg"`: Diz ao navegador que este link deve ser baixado com este nome.
8.  `link.click()`: Simula um clique do usuário no link.
9.  **A Mágica:** Este clique é o que o `QWebEngineProfile` no `DialogoFormula.py` está "ouvindo" com o sinal `downloadRequested`. O Python intercepta esse "download" e o salva no disco.

#### 3.4. Estratégia: Zoom com Scroll do Mouse

O `previewContainer.addEventListener('wheel', ...)` intercepta o scroll do mouse (`wheel`).
* `event.preventDefault()`: Impede que a página inteira role.
* Ele altera o `font-size` (em `em`) da `div#preview`.
* **Por quê?** Como o SVG renderizado pelo MathJax usa unidades relativas (`em`), aumentar o tamanho da fonte do container (`#preview`) automaticamente escala o SVG (dá zoom), o que é um truque de CSS muito elegante.


## Documentação: `main_app.py`

### 1. Propósito Principal

Este arquivo é o **"Maestro"** da orquestra. Ele é o ponto de entrada principal (`if __name__ == '__main__':`) que inicializa e conecta todos os outros módulos em uma aplicação funcional.

A classe `ABNTHelperApp` é a janela principal (`QWidget`) que contém toda a interface do usuário. Suas responsabilidades são:

1.  **Orquestração:** Importar e inicializar todos os componentes principais (Modelo de Dados, Gerenciador de Projeto, Gerador de Preview, Abas de Conteúdo, etc.).
2.  **Gerenciamento de Estado Global:** Manter o estado central da aplicação, como qual documento está aberto (`self.documento`), onde ele está salvo (`self.caminho_projeto_atual`) e se ele foi modificado (`self.modificado`).
3.  **Construção da UI Principal:** Construir os elementos da janela principal, como a Barra de Menu (`QMenuBar`), o `QTabWidget` principal e o painel de Pré-visualização (`QWebEngineView`).
4.  **Sincronização de Dados:** Servir como o "controlador" de mais alto nível, garantindo que os dados da UI sejam salvos no modelo (`_sincronizar_modelo_com_ui`) antes de qualquer operação de salvamento ou geração.
5.  **Ciclo de Vida da Aplicação:** Gerenciar o fluxo de inicialização (lidando com `TelaInicial` e `DialogoRecuperacao`) e o fluxo de encerramento (verificando alterações não salvas).

### 2. Tecnologias e Bibliotecas Utilizadas

* **`PySide6` (Qt for Python):** A base de toda a aplicação.
    * `QApplication`: Gerencia o loop de eventos global.
    * `QWidget`: A classe base para a janela principal.
    * `QMenuBar`, `QAction`: Usado para criar o menu superior (Arquivo, Editar, Visualização).
    * `QTabWidget`: Usado para criar a navegação principal (Geral, Conteúdo, Referências).
    * `QSplitter`: **Estratégia de UI** usada para criar o layout "Lado a Lado" (`lado_a_lado`), permitindo ao usuário arrastar a divisão entre o editor e o preview.
    * `QTimer`: Essencial para duas estratégias de desempenho:
        * `preview_update_timer`: Um timer *one-shot* (disparo único) que implementa a lógica de "debounce" (anti-tremulação) para a pré-visualização.
        * `autosave_timer`: Um timer *periódico* que dispara o auto-save (`_auto_salvar_recuperacao`) em intervalos definidos no `gerenciador_config.py`.
* **`PySide6.QtWebEngineWidgets` (`QWebEngineView`):** Um navegador Chromium completo, usado para renderizar o HTML gerado pelo `gerador_preview.py`.
* **`re` (Python Regex):** Usado em `_gerar_documento_final` para "sanitizar" o título do projeto, removendo caracteres inválidos (`[<>:"/\\|?*]`) antes de usá-lo como nome de arquivo.
* **Módulos do Projeto:** Este arquivo importa e conecta *quase todos* os outros módulos:
    * `documento.py`: Para criar a instância `self.documento = DocumentoABNT()`.
    * `gerador_docx.py`: Chamado por `_gerar_documento_final`.
    * `aba_conteudo.py`: Criado e adicionado como a aba "Conteúdo Textual".
    * `gerador_preview.py`: Criado e chamado por `_atualizar_preview`.
    * `gerenciador_projeto.py`: Usado para salvar e carregar o `.abnf`.
    * `dialogs.py`, `dialogo_figura.py`, `dialogo_brasao.py`: Chamados para abrir as janelas de edição.
    * `modelos_trabalho.py`: Usado para popular o `QComboBox` de "Tipo de Trabalho".
    * `tela_inicial.py`, `gerenciador_config.py`, `gerenciador_recuperacao.py`: Usados no bloco `if __name__ == '__main__':` para gerenciar o início do programa.

### 3. Arquitetura e Decisões de Design

#### 3.1. O Bloco `if __name__ == '__main__':` (O Lançador)

Este bloco não é apenas um "iniciador"; ele contém uma **Máquina de Estados de Inicialização** complexa e robusta:

1.  **Verificar Recuperação:** Ele primeiro chama `verificar_arquivos_recuperaveis()`.
2.  **Estado 1: Recuperação:** Se arquivos são encontrados, ele *ignora* a `TelaInicial` e mostra o `DialogoRecuperacao`.
    * **Estratégia (Recuperação Múltipla):** Se o usuário recupera múltiplos arquivos, o código abre o *primeiro* na janela principal e "joga" os outros na Área de Trabalho do usuário, uma solução inteligente para evitar abrir 10 janelas do app.
3.  **Estado 2: Tela Inicial:** Se não há recuperação, ele mostra a `TelaInicial`.
4.  **Estado 3: Ação:** Com base na ação do usuário (`acao_inicial`), ele decide se deve chamar `win.iniciar_novo_projeto_com_modelo()`, `win.carregar_projeto_pelo_caminho()` ou `win.carregar_projeto_pelo_caminho(is_recovery=True)`.
5.  **O `while True:` Loop (Estratégia de Reinício):**
    * O loop `while True:` envolve *toda* a inicialização da aplicação.
    * Quando o usuário clica em "Voltar à Tela Inicial" (`_voltar_tela_inicial`), o código define `self.wants_to_restart = True` e fecha a janela.
    * O loop `app.exec()` termina, o `if not win.wants_to_restart:` falha, e o `while True:` **reinicia o processo**, mostrando a `TelaInicial` novamente sem fechar o programa. Esta é uma estratégia muito eficaz para um ciclo de vida de aplicação.

#### 3.2. Gerenciamento de Estado (Flags de Sincronização)

O `main_app.py` usa duas flags cruciais para evitar comportamento caótico:

1.  **`self.modificado` (Flag "Sujo"):**
    * `False` por padrão.
    * `_marcar_modificado()`: Esta função é conectada (via `_conectar_sinais_modificacao`) a *quase todos* os widgets de edição.
    * **Propósito 1 (UI):** Adiciona o `*` ao título da janela para informar ao usuário.
    * **Propósito 2 (Segurança):** `closeEvent` e `_verificar_alteracoes_nao_salvas` usam esta flag para perguntar "Deseja salvar?" antes de fechar.
    * **Propósito 3 (Desempenho):** Inicia o `self.autosave_timer` *apenas* na primeira modificação.

2.  **`self._populando_ui` (Flag de "Carregamento"):**
    * Esta é a **"gambiarra" de bloqueio de sinal** mais importante.
    * **Problema:** Quando `_popular_ui_com_documento` é chamada (ao carregar um projeto), ela preenche campos como `self.cfg_instituicao.setText(...)`. Isso *dispara* o sinal `textChanged`, que chama `_marcar_modificado()`, marcando erroneamente o projeto como "sujo" (modificado).
    * **Solução:** O `_popular_ui_com_documento` define `self._populando_ui = True` no início. A função `_marcar_modificado` verifica `if self._populando_ui: return` e para imediatamente. No final do carregamento, a flag é definida como `False`.

#### 3.3. Estratégia: O Preview Lado-a-Lado (`_reconfigurar_layout`)

O `main_app.py` permite dois modos de preview ("lado_a_lado" ou "aba"). A função `_reconfigurar_layout` é uma estratégia de UI que *reparenta* widgets dinamicamente.

* **Modo Lado-a-Lado:** O `self.tabs` e o `self.preview_container` são colocados *dentro* de um `QSplitter`.
* **Modo Aba:** O `self.preview_container` é *removido* do `QSplitter` e *adicionado* (`self.tabs.addTab(...)`) como uma nova aba dentro do `self.tabs`.

Isso dá ao usuário flexibilidade total de layout sem duplicar widgets.

#### 3.4. Estratégia: Persistência do Scroll do Preview

O preview (sendo uma página web) perde a posição do scroll a cada atualização. O `main_app.py` resolve isso:

1.  `_atualizar_preview` chama `_salvar_scroll_preview`.
2.  `_salvar_scroll_preview` (Python) chama `window.scrollY` (JavaScript) e armazena o resultado em `self.scroll_posicao` (via o callback `_on_scroll_posicao_recebida`).
3.  O preview é atualizado (`self.preview_display.setHtml(...)`).
4.  Quando o `loadFinished` (sinal do `QWebEngineView`) é emitido, `_restaurar_scroll_preview` é chamado.
5.  `_restaurar_scroll_preview` (Python) chama `window.scrollTo(0, {self.scroll_posicao})` (JavaScript), restaurando a posição exata.

### 4. "Gambiarras" e Pontos de Atenção

* **`os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'`:** Esta linha (no topo) é uma "gambiarra" de depuração. Ela abre a porta 9222 para que você possa abrir o Google Chrome, digitar `http://127.0.0.1:9222` e depurar o `QWebEngineView` (o preview) como se fosse um site normal.
* **Sincronização Manual de Dados:** O `main_app.py` força uma sincronização de dados antes de salvar ou gerar. Ele chama `self.aba_conteudo.sincronizar_conteudo_pendente()` (para garantir que o texto do editor seja salvo no `capitulo.conteudo`) e `self._sincronizar_modelo_com_ui()` (para salvar os campos da aba "Geral" no `documento.configuracoes`). Isso é necessário porque o modelo de dados não é atualizado automaticamente (o que seria um padrão MVVM mais complexo).


## Documentação: `modelos_trabalho.py`

### 1. Propósito Principal

Este arquivo é um módulo de **configuração "fixa" (hard-coded)**. Seu único propósito é servir como um banco de dados centralizado para os **modelos (templates) de capítulos** que o aplicativo oferece.

Ele define quais capítulos-padrão (ex: "INTRODUÇÃO", "METODOLOGIA") devem ser criados quando um usuário inicia um novo projeto, com base no tipo de trabalho acadêmico selecionado (ex: "TCC" vs. "Artigo Científico").

Ele é a "Fonte Única da Verdade" (Single Source of Truth) para a estrutura de capítulos padrão do programa.

### 2. Tecnologias e Bibliotecas Utilizadas

* **Python Padrão:** Este módulo é 100% Python puro. Ele não usa bibliotecas externas.
* **Estruturas de Dados:**
    * **`dict` (Dicionário):** A estrutura de dados principal (`ESTRUTURAS_MODELO`) para mapear nomes de modelos (chaves) a listas de capítulos (valores).
    * **`list` (Lista):** Usada para armazenar a sequência ordenada de títulos de capítulos para cada modelo.

### 3. Arquitetura e Decisões de Design

Este módulo é um exemplo clássico de **"Configuration as Code" (Configuração como Código)**.

#### 3.1. `ESTRUTURAS_MODELO` (O Banco de Dados)

Esta é a constante principal. É um dicionário Python simples.

* **Chave (Key):** O nome legível do modelo (ex: `"Trabalho de Conclusão de Curso (TCC)"`). Este é o texto exato que é usado para popular a interface gráfica (o `QComboBox` no `main_app.py` e os botões na `tela_inicial.py`).
* **Valor (Value):** Uma lista de strings (`List[str]`) que define os títulos dos capítulos de Nível 1 e sua ordem padrão.

#### 3.2. Funções de Acesso (API do Módulo)

O módulo não expõe o dicionário `ESTRUTURAS_MODELO` diretamente. Em vez disso, ele usa duas funções de acesso (getters), o que é uma excelente prática de **encapsulamento**:

1.  **`get_nomes_modelos()`:**
    * **Propósito:** Fornece à interface (como `tela_inicial.py`) a lista de todos os modelos disponíveis para exibição.
    * **Design:** Ela chama `list(ESTRUTURAS_MODELO.keys())`. Isso desacopla a interface do módulo. Se, no futuro, você decidir carregar os modelos de um arquivo JSON, a `tela_inicial.py` não precisará ser alterada, apenas esta função.

2.  **`get_estrutura_por_nome(nome_modelo: str)`:**
    * **Propósito:** Retorna a lista de capítulos para um modelo específico.
    * **Estratégia (Programação Defensiva):** A linha `return ESTRUTURAS_MODELO.get(nome_modelo, [])` é uma estratégia de segurança crucial.
        * Em vez de usar `ESTRUTURAS_MODELO[nome_modelo]` (que *travaria* o programa com um `KeyError` se o nome não existisse), ela usa `.get()`.
        * O segundo argumento, `[]` (uma lista vazia), é o valor padrão. Se o `main_app.py` pedir um modelo que não existe, ele simplesmente receberá uma lista vazia, criando um projeto em branco em vez de travar.

### 4. "Gambiarras" e Pontos de Atenção

* **A "Gambiarra" Central (Falta de Flexibilidade):**
    * A maior decisão de design deste arquivo é **hard-coding** (fixar no código) os modelos.
    * **Vantagem:** É extremamente simples, rápido de carregar (sem leitura de disco ou parsing de JSON) e impossível de ser corrompido pelo usuário.
    * **Desvantagem (A "Gambiarra"):** É totalmente inflexível. Como discutimos anteriormente (sobre "modelos personalizados"), o usuário final não pode criar, editar ou salvar seus próprios modelos de capítulos.
    * **Consequência:** Conforme indicado no comentário no topo do arquivo, a única maneira de adicionar um novo modelo (ex: "Relatório de Estágio") é o *desenvolvedor* (você) editar manualmente o dicionário `ESTRUTURAS_MODELO` e lançar uma nova versão do aplicativo.


## Documentação: `normas_abnt.py`

### 1\. Propósito Principal

O `MotorNormasABNT` é uma classe "helper" (auxiliar) de formatação. Seu único propósito é **centralizar e aplicar todas as regras de estilo da ABNT** (margens, fontes, espaçamento, recuos, cores) em um objeto `Document` da biblioteca `python-docx`.

Ele é o "cérebro" por trás da aparência do arquivo `.docx` final. Ele é instanciado pelo `gerador_docx.py` e recebe o `doc_abnt` (os dados) para que possa tomar decisões de formatação (como `is_artigo`).

### 2\. Tecnologias e Bibliotecas Utilizadas

  * **`python-docx` (Biblioteca Principal):** A fundação de todo o módulo.
      * **`Cm`, `Pt`, `RGBColor`:** Unidades de medida essenciais. O código define regras usando unidades ABNT (ex: `Cm(3)`) e unidades de fonte (ex: `Pt(12)`), e força a cor da fonte para preto (`RGBColor(0, 0, 0)`).
      * **`WD_PARAGRAPH_ALIGNMENT`:** Enumerações usadas para definir alinhamentos (Justificado, Centralizado, etc.).
  * **`python-docx.oxml` (`OxmlElement`, `qn`):** Esta é a estratégia mais avançada do módulo.
      * **Propósito:** A biblioteca `python-docx` não tem funções fáceis para *todos* os recursos do Word, como a formatação de bordas ABNT (apenas superior, inferior e cabeçalho).
      * **Como é usado:** O código "desce" para o nível do XML (Office Open XML) e constrói manualmente as tags XML (`<w:tblBorders>`, `<w:top>`, `<w:left>`) para forçar o Word a desenhar as bordas exatamente como a ABNT exige (`aplicar_estilo_tabela_abnt`).
  * **`documento.py`:** Importa o `DocumentoABNT` para que o motor possa ler as configurações (ex: `configuracoes.tipo_trabalho`).

### 3\. Arquitetura e Decisões de Design

#### 3.1. Design de Constantes (As "Regras Fixas")

A arquitetura central deste módulo é definir todas as regras da ABNT como constantes de classe no `__init__`.

```python
self.MARGEM_SUPERIOR = Cm(3)
self.FONTE_PADRAO = 'Times New Roman'
self.ESPAÇAMENTO_PADRAO = 1.5
self.RECUO_PRIMEIRA_LINHA = Cm(1.25)
# ... etc.
```

  * **Vantagem (A "Fonte da Verdade"):** Qualquer desenvolvedor (ou você) que precise alterar uma regra (ex: mudar o recuo de 1.25cm para 1.5cm) só precisa mexer em **um lugar**.
  * **Desvantagem (A "Gambiarra" de Fundo):** Como discutimos, isso "fixa" as regras. O usuário final não pode personalizar as margens. O programa não é um *formatador genérico*, mas sim um *formatador ABNT específico*.

#### 3.2. Configuração de Estilos Globais (`configurar_pagina_e_estilos`)

Esta é a função mais importante do módulo. Em vez de estilizar cada parágrafo manualmente, ela **configura os estilos nomeados** do Word.

  * **`doc.styles['Normal']`:** Ele redefine o estilo padrão do documento. Todo parágrafo futuro herdará `Times New Roman`, `12pt` e `espaçamento 1.5`.
  * **"Gambiarra" (Correção de Cor):** O loop `for i in range(1, 10): ... doc.styles[style_name].font.color.rgb = self.COR_FONTE_PADRAO` é uma **"gambiarra" defensiva**. O modelo padrão do `python-docx` (ou do Word) usa azul para títulos (Heading 1, 2, etc.). Este loop força todos os estilos de título a serem pretos, garantindo a conformidade com a ABNT.
  * **Criação de Estilos Customizados:** O código usa `doc.styles.add_style(...)` para criar estilos que não existem por padrão:
      * `CitacaoLonga`: Aplica o recuo de 4cm e fonte 10pt.
      * `Referencias`: Aplica espaçamento simples e sem recuo.

#### 3.3. Funções de Aplicação de Estilo (`aplicar_estilo_...`)

Estas são funções "helper" que aplicam os estilos criados:

  * **`aplicar_estilo_paragrafo_normal`:** Aplica o estilo "Normal", mas *também* define o recuo da primeira linha (`Cm(1.25)`) e a justificação.
  * **`aplicar_estilo_titulo_secao`:** Uma função inteligente que:
    1.  Verifica se é um artigo (sem caixa alta) ou TCC (caixa alta para Nível 1).
    2.  Chama `doc.add_heading(..., level=nivel)`. Isso é crucial. Ao usar `add_heading` em vez de `add_paragraph`, o `python-docx` automaticamente marca esses títulos para serem incluídos no Sumário (`TOC`).
  * **`aplicar_estilo_referencia` (A Estratégia do Negrito):**
      * A ABNT exige negrito no *título* da referência (ex: **Nome do Livro**).
      * O módulo `referencia.py` (que não vemos aqui) deve estar formatando a string com um marcador, como `**Título**`.
      * Esta função `split('**')` quebra a string (ex: `['SOBRENOME, N. ', 'Título do Livro', '. Local...']`).
      * Ela então itera por essa lista e aplica `run.bold = True` a cada *segunda* parte (índice ímpar). É uma estratégia de formatação muito inteligente e simples.

#### 3.4. Estratégia do XML da Tabela (`aplicar_estilo_tabela_abnt`)

Esta é a "gambiarra" mais avançada do arquivo. ABNT exige tabelas sem bordas laterais, apenas com bordas horizontais em cima, embaixo e no cabeçalho.

  * **O Problema:** `python-docx` não tem um comando `tabela.bordas = "ABNT"`.
  * **A Solução (OXML):**
    1.  `tabela._element.xpath('w:tblPr')`: "Pede" ao `python-docx` o elemento XML bruto (`<w:tblPr>`) que define as propriedades da tabela.
    2.  `tbl_borders.remove(border)`: O código apaga *todas* as regras de borda que o Word possa ter definido.
    3.  `OxmlElement(f'w:{border_name}')`: Ele constrói manualmente as tags XML.
    4.  `['top', 'bottom', 'insideH']`: Ele cria tags XML para essas bordas, definindo-as como `single` (visíveis).
    5.  `['left', 'right', 'insideV']`: Ele cria tags XML para as bordas laterais e verticais e as define como `nil` (nulas/invisíveis).

Isso é uma manipulação de baixo nível do XML do Word para forçar a formatação ABNT, contornando as limitações da biblioteca `python-docx`.


## Documentação: `referencia.py`

### 1. Propósito Principal

O `referencia.py` define a estrutura de dados para diferentes tipos de referências (Livros, Artigos, Sites) e fornece a lógica para:

1.  **Formatar Autores:** Converter nomes de entrada (ex: "Matheus da Silva") para o formato ABNT (ex: "SILVA, Matheus da").
2.  **Formatar Referências Completas:** Montar a string de referência final, aplicando a formatação ABNT correta para cada tipo (ex: `**negrito**` no título do livro, mas no nome da revista para artigos).
3.  **Ordenar Referências:** Fornecer uma "chave de ordenação" (o sobrenome do primeiro autor) para que o `DocumentoABNT` possa classificar a lista de referências em ordem alfabética.

### 2. Tecnologias e Bibliotecas Utilizadas

* **`dataclasses` (Python):** Usado para criar as classes `Livro`, `Artigo`, e `Site`.
    * **Decisão de Design:** Curiosamente, a classe *base* (`Referencia`) **não** é uma `@dataclass`. Ela é uma classe Python padrão com um `__init__` manual. As classes *filhas* (`Livro`, `Artigo`, `Site`) usam `@dataclass`, mas também **sobrescrevem o `__init__`**.
    * **"Gambiarra" / Ponto de Atenção:** Isso é uma **implementação incomum**. O `__init__` manual nas classes filhas (ex: `def __init__(self, ...): super().__init__(...)`) **anula completamente** o benefício do `@dataclass`. O `@dataclass` está, neste momento, apenas fornecendo métodos como `__repr__`, mas o `__init__` (que é o principal benefício) não está sendo usado. O código funcionaria *exatamente da mesma forma* se o `@dataclass` fosse removido.

* **`typing` (Não usado):** O código não usa `List`, `Optional`, etc., mas se beneficia da estrutura de `dataclass`.

### 3. Arquitetura e Decisões de Design

#### 3.1. Padrão de Herança (OOP)

O módulo usa um padrão de Programação Orientada a Objetos (OOP) claro:

1.  **Classe Base (`Referencia`):**
    * Define a interface comum que *todas* as referências devem ter: `autores`, `titulo`, `ano`.
    * Fornece a lógica de ordenação universal (`get_chave_ordenacao`).
    * Define um método `formatar()` que é `raise NotImplementedError`. Isso **força** as classes filhas (como `Livro`) a implementar sua própria lógica de formatação.

2.  **Classes Filhas (`Livro`, `Artigo`, `Site`):**
    * Elas herdam de `Referencia`.
    * Elas chamam `super().__init__(...)` para preencher os campos base.
    * Elas adicionam seus próprios campos específicos (ex: `local` e `editora` para `Livro`).
    * Elas **sobrescrevem** o método `formatar()` com a lógica de formatação específica da ABNT para aquele tipo.

#### 3.2. Estratégia: A Função `formatar_autores`

Esta é a lógica de formatação mais complexa do módulo.

* **Propósito:** Traduzir uma entrada de usuário "amigável" em uma string ABNT "correta".
* **Decisão de Design (O "Padrão Ponto-e-Vírgula"):** O código assume que o usuário separará múltiplos autores com um ponto-e-vírgula (`;`), como no `placeholderText` do `dialogs.py` (`"Autor 1; Autor 2"`).
* **Lógica (A Estratégia do Sobrenome):**
    1.  `autores_str.split(';')` divide os autores (ex: `['Matheus da Silva', 'João B. Costa']`).
    2.  `autor.split()` divide o nome (ex: `['Matheus', 'da', 'Silva']`).
    3.  `sobrenome = partes[-1].upper()` (ex: "SILVA")
    4.  `prenomes = " ".join(partes[:-1])` (ex: "Matheus da")
    5.  `f"{sobrenome}, {prenomes}"` (ex: "SILVA, Matheus da")
* **"Gambiarra" (Limitação):** Esta lógica é uma "gambiarra" que funciona para a maioria dos nomes brasileiros, mas falha em casos complexos de sobrenomes compostos (ex: "José da **Conceição Silva**") ou nomes com "Filho", "Neto" (ex: "João Costa **Filho**"). Ela sempre pegará apenas a *última* palavra como sobrenome. Para um TCC, essa "gambiarra" é 99% eficaz e aceitável.

#### 3.3. Estratégia: A Chave de Ordenação (`get_chave_ordenacao`)

* **Propósito:** Permitir que `DocumentoABNT.ordenar_referencias()` funcione.
* **Lógica:** Ela extrai *apenas* o primeiro autor, pega o sobrenome dele (a última palavra) e o retorna em maiúsculas.
* **"Gambiarra" (Fallback):** Se o campo `autores` estiver vazio (`if not primeiro_autor:`), a função (corretamente) usa o `self.titulo.upper()` como chave de ordenação, seguindo a regra da ABNT para fontes sem autoria.

#### 3.4. Estratégia: Formatação em Negrito (`**`)

* As funções `formatar()` (ex: `f"{autores_fmt}. **{self.titulo}**. ..."`
* **O Problema:** ABNT exige negrito em partes diferentes (título do livro, nome da revista).
* **A Solução:** Em vez de tentar inserir lógica de formatação complexa (que não pode ser salva em JSON), o módulo insere **marcadores `**`** (inspirados no Markdown).
* **Quem Resolve:** O `gerador_docx.py` (no `aplicar_estilo_referencia`) e o `gerador_preview.py` (no `_renderizar_referencias`) são responsáveis por encontrar esses `**` e aplicar a formatação de negrito real (`run.bold = True` ou `<strong>`). É a mesma estratégia de marcadores (placeholders) usada em `aba_conteudo.py`.


## Documentação: `stylesheet.py`

### 1. Propósito Principal

O propósito deste arquivo é definir uma **Folha de Estilo Global** em QSS (Qt Style Sheets, a versão do Qt para o CSS) para toda a aplicação.

Em vez de estilizar cada botão e cada janela individualmente nos arquivos Python (ex: `widget.setStyleSheet(...)`), este módulo centraliza todos os estilos em um único lugar. O `main_app.py` então carrega esta folha de estilo *uma única vez* usando `app.setStyleSheet(stylesheet.get_style_sheet())`, aplicando-a a toda a aplicação.

### 2. Tecnologias e Bibliotecas Utilizadas

* **QSS (Qt Style Sheets):** Esta é a tecnologia principal. É uma sintaxe baseada em CSS que permite estilizar widgets do PySide6/PyQt.
* **`os` (Biblioteca Padrão do Python):** Usado para uma estratégia crucial: encontrar o caminho absoluto do arquivo de ícone (`arrow_down.png`).
* **`python-docx .format()` (String Formatting):** Usado para injetar dinamicamente o caminho do ícone no texto QSS.

### 3. Arquitetura e Decisões de Design

#### 3.1. Design Centralizado

* **`_STYLE_SHEET_TEMPLATE`:** O estilo é definido em uma única string gigante (template).
    * **Vantagem:** Manutenção incrivelmente fácil. Se você quiser mudar a cor primária de azul para verde, você muda em *um* lugar (`QPushButton { background-color: ... }`) e todos os botões no aplicativo inteiro são atualizados.
* **`get_style_sheet()`:** Esta função é a única interface pública do módulo. Ela esconde a complexidade de formatar a string, fornecendo o QSS final e pronto para uso.

#### 3.2. Seletores de QSS (As "Regras de Estilo")

O QSS usa seletores (similares ao CSS da web) para aplicar regras:

1.  **Seletor de Tipo (Global):**
    * Ex: `QWidget { ... }`, `QPushButton { ... }`
    * Define a aparência *padrão* para todos os widgets daquele tipo em todo o app.

2.  **Seletor de ID (`#`):**
    * Ex: `QPushButton#GenerateBtn { ... }`
    * Aplica um estilo *específico* a um *único* widget. O `main_app.py` deve ter feito `self.generate_btn.setObjectName("GenerateBtn")` para que este seletor funcione. É usado para o botão "Gerar Documento .docx Final", tornando-o maior e mais destacado que os botões normais.
    * O mesmo é feito para `QWidget#ProjetoRecenteItem`, criando o visual de "cartão" na `tela_inicial.py`.

3.  **Seletor de Propriedade (`[...]` ou "Classe"):**
    * Ex: `QPushButton[cssClass="destructive"] { ... }`
    * Esta é a **estratégia mais importante** do arquivo. QSS não tem "classes" como o CSS da web. A "gambiarra" padrão é usar `setProperty("cssClass", "...")` nos widgets Python (como visto em `aba_conteudo.py`).
    * O QSS então seleciona esses widgets usando o seletor de *atributo/propriedade*.
    * **`destructive`:** Define o estilo do botão "Remover" (vermelho).
    * **`utility`:** Define o estilo de botões secundários (cinza claro), como "Editar", "Procurar", "Limpar Seleção".

4.  **Seletores de Pseudo-Estado (`:`):**
    * Ex: `QPushButton:hover { ... }`, `QTabBar::tab:selected { ... }`
    * Define como os widgets reagem a ações do usuário (passar o mouse, ser selecionado, estar desabilitado).

#### 3.3. Estratégia: O Ícone do QComboBox (A Seta)

Este é o hack mais complexo do arquivo. Por padrão, a seta do `QComboBox` é feia e difícil de estilizar.

* **O Problema:** O QSS não permite estilizar facilmente a seta (`::down-arrow`).
* **A Solução (Gambiarra de 3 Passos):**
    1.  **Esconder a Seta Real:** O código remove a seta padrão: `QComboBox::down-arrow { image: none; }`.
    2.  **Criar uma Falsa Seta:** Ele estiliza o "botão" do QComboBox (`QComboBox::drop-down`) para parecer um botão.
    3.  **Injetar o Ícone (A "Gambiarra" do .format):**
        * O QSS precisa de um caminho de arquivo para o ícone (ex: `url(C:/.../icons/arrow_down.png)`).
        * O Python não sabe qual será o caminho absoluto no computador do usuário.
        * **Solução:** O `_STYLE_SHEET_TEMPLATE` usa um placeholder (`url({ICON_URL_PATH})`). A função `get_style_sheet()` usa `_STYLE_SHEET_TEMPLATE.format(ICON_URL_PATH=ICON_URL_PATH)` para injetar o caminho absoluto (calculado no topo do arquivo) na string QSS antes de enviá-la para a aplicação.

#### 3.4. "Gambiarra": Escapando Chaves (`{{` e `}}`)

* **O Problema:** A estratégia do `.format()` (acima) entra em conflito com o QSS. O QSS usa chaves `{ ... }` para definir blocos de estilo. O Python *também* usa `{...}` para o `.format()`.
* **O Erro:** Ao chamar `_STYLE_SHEET_TEMPLATE.format(...)`, o Python vê as chaves do QSS (ex: `QWidget { ... }`) e pensa que são placeholders de formatação, causando um `ValueError: Single '}' encountered`.
* **A Correção (A "Gambiarra"):** O código **dobra todas as chaves** que são literais do QSS (ex: `QWidget {{ ... }}`). Isso "escapa" as chaves, dizendo ao Python para ignorá-las e tratá-las como texto normal, enquanto *apenas* formata a chave do ícone (`{ICON_URL_PATH}`).

### 4. Pontos de Atenção

* **Dependência de Ícone:** O arquivo `arrow_down.png` é um ativo externo. Se ele for deletado da pasta `assets/icons`, a seta do `QComboBox` desaparecerá.
* **Manutenção do Escapamento:** Qualquer desenvolvedor (você) que editar este arquivo QSS *deve* se lembrar de dobrar todas as chaves (`{{` e `}}`), exceto as usadas para formatação (`{ICON_URL_PATH}`). Se esquecer, o programa travará no `main_app.py` ao tentar carregar o stylesheet.

## Documentação: `tela_inicial.py`

### 1\. Propósito Principal

Este módulo define o `TelaInicial`, um `QDialog` que serve como "launcher" (lançador) do aplicativo. Sua responsabilidade é apresentar ao usuário as ações de inicialização fundamentais:

1.  **Criar um novo projeto:** Seja um projeto em branco ou baseado em um modelo (TCC, Artigo, etc.).
2.  **Abrir um projeto existente:** Seja da lista de "Projetos Recentes" ou procurando um arquivo `.abnf` no disco.
3.  **Gerenciar a Recuperação:** Lidar com arquivos de auto-save de sessões anteriores que travaram.

O `main_app.py` exibe esta tela e espera o usuário fazer uma escolha. A `TelaInicial` então se fecha e retorna a "ação" escolhida (ex: `"novo"`, `"abrir"`) e os "dados" dessa ação (ex: o nome do modelo ou o caminho do arquivo) para o `main_app.py`, que então decide qual janela abrir.

### 2\. Tecnologias e Bibliotecas Utilizadas

  * **`PySide6` (Qt for Python):** Usado para toda a interface.
      * `QDialog`: A classe base da janela.
      * `QHBoxLayout` / `QVBoxLayout`: Usados para criar a estrutura principal de 3 painéis (Ações, Recentes, Modelos).
      * `QListWidget`: Usado para exibir a lista de projetos recentes.
      * `QListWidgetItem`: O item padrão da lista.
      * `QScrollArea`: Usado no painel "Modelos" para garantir que, se muitos modelos forem adicionados, o painel ganhe uma barra de rolagem em vez de quebrar o layout.
  * **Módulos do Projeto:**
      * `gerenciador_config.py`: Usado para `get_projetos_recentes()` e `remover_projeto_recente()`.
      * `gerenciador_recuperacao.py`: Usado para `verificar_arquivos_recuperaveis()` e `limpar_recuperacao_pelo_caminho_direto()`.
      * `dialogs.py`: Importa o `DialogoRecuperacao` para exibi-lo caso o usuário clique em "Gerenciar Recuperação".
      * `modelos_trabalho.py`: Usado para `get_nomes_modelos()` para popular a lista de botões de modelos.

### 3\. Arquitetura e Decisões de Design

#### 3.1. Classe `ProjetoRecenteItem(QWidget)` - A Estratégia do Cartão

Esta é a estratégia de UI mais importante deste arquivo. Um `QListWidget` padrão só permite texto simples. Para criar o visual de "cartão" (com título em negrito e caminho do arquivo em cinza), o código usa um truque avançado:

1.  **Widget Customizado:** A classe `ProjetoRecenteItem` é um `QWidget` separado que define o layout do "cartão" (um `QVBoxLayout` com dois `QLabel`s).
2.  **`QListWidgetItem` como Container:** A função `popular_projetos_recentes` cria um `QListWidgetItem` (o item da lista), que é essencialmente um container vazio.
3.  **`setItemWidget` (A Mágica):** A linha `self.lista_recentes.setItemWidget(item, item_widget)` diz ao `QListWidget` para "desenhar o `item_widget` (nosso cartão) *dentro* do espaço do `item` (o container da lista)".
4.  **Seleção de ID (`setObjectName`):** O `item_widget` recebe `self.setObjectName("ProjetoRecenteItem")`. Isso permite que o `stylesheet.py` o estilize com seletores de ID (`QWidget#ProjetoRecenteItem`), dando a ele uma borda, fundo branco e efeitos de *hover*, o que seria impossível em um `QListWidgetItem` padrão.

#### 3.2. A Lógica de Retorno (`self.resultado`)

Este diálogo não *faz* nada; ele apenas *informa* ao `main_app.py` o que fazer. Ele usa a variável `self.resultado` para isso.

  * `self.resultado = (None, None)` (Padrão): Se o usuário fechar a janela, o `main_app` recebe `None` e encerra o aplicativo.
  * `on_novo_com_modelo(m)`: Define `self.resultado = ("novo", m)` (ex: `"novo"`, `"Artigo Científico"`).
  * `on_abrir_projeto()`: Define `self.resultado = ("abrir", caminho)` (ex: `"abrir"`, `"C:/.../meu_tcc.abnf"`).
  * `on_item_recente_clicado()`: Também define `self.resultado = ("abrir", caminho)`.
  * `on_gerenciar_recuperacao()`: Define `self.resultado = ("recuperar", lista_de_arquivos)`.

Quando qualquer uma dessas funções é chamada, ela imediatamente chama `self.accept()`. Isso fecha o `QDialog` (liberando o `if tela_inicial.exec():` no `main_app.py`) e permite que o `main_app.py` chame `tela_inicial.get_resultado()` para pegar a tupla `("ação", "dados")`.

#### 3.3. Estratégia: `lambda` em Loops (Painel de Modelos)

No painel "Modelos", o código cria vários botões em um loop `for`.

```python
for nome_modelo in get_nomes_modelos():
    # ...
    btn.clicked.connect(lambda checked=False, m=nome_modelo: self.on_novo_com_modelo(m))
```

  * **O Problema (Closures de Loop em Python):** Se você fizesse `lambda: self.on_novo_com_modelo(nome_modelo)`, o Python não "capturaria" o valor de `nome_modelo` *naquele momento*. Todos os botões acabariam chamando a função com o *último* valor de `nome_modelo` na lista (ex: "Tese de Doutorado").
  * **A Estratégia (`m=nome_modelo`):** A sintaxe `lambda ..., m=nome_modelo:` é uma estratégia clássica do Python. Ela força o `lambda` a avaliar e armazenar o valor de `nome_modelo` (na variável padrão `m`) *no momento em que o lambda é criado*.
  * **Resultado:** O botão "TCC" chama `on_novo_com_modelo("TCC")`, e o botão "Artigo" chama `on_novo_com_modelo("Artigo Científico")`, como esperado.

#### 3.4. Programação Defensiva (`on_item_recente_clicado`)

Esta função verifica se um arquivo recente ainda existe (`if os.path.exists(caminho):`).

  * **Cenário:** O usuário abre um projeto, depois o exclui no Windows Explorer.
  * **Resultado:** Se o usuário clicar no item "morto", o programa não trava. Em vez disso, ele mostra um `QMessageBox` informando o erro, chama `gerenciador_config.remover_projeto_recente()` para limpar a entrada inválida da lista, e então atualiza a UI (`self.popular_projetos_recentes()`). Este é um fluxo de tratamento de erro muito robusto e profissional.


Aqui está um título e uma breve descrição para o documento de levantamento de requisitos que acabamos de criar:

---

# Levantamento de Requisitos: Formatheus

**Descrição:** Este documento detalha os Requisitos Funcionais (RF) e os Requisitos Não Funcionais (RNF) da aplicação Formatheus. O objetivo é fornecer uma análise completa das funcionalidades do sistema (o que ele faz) e de suas qualidades e restrições operacionais (como ele faz), servindo como guia para o desenvolvimento, validação e testes do software.

Esta documentação descreve o que o sistema *faz* (funcionais) e quais são suas *qualidades* e *restrições* (não funcionais).

---

## 1. Requisitos Funcionais (RF)

Os Requisitos Funcionais descrevem as **ações e funcionalidades** que o sistema deve ser capaz de executar. Eles são as *features* vistas pelo usuário.

### RF-01: Gerenciamento de Projeto
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-001 | Iniciar Novo Projeto | O usuário deverá ser capaz de iniciar um novo projeto a partir de uma seleção de modelos (ex: TCC, Artigo). | `tela_inicial.py`, `main_app.py`, `modelos_trabalho.py` |
| RF-002 | Carregar Projeto | O usuário deverá ser capaz de carregar um projeto existente a partir de um arquivo `.abnf`. | `tela_inicial.py`, `main_app.py`, `gerenciador_projeto.py` |
| RF-003 | Salvar Projeto | O usuário deverá ser capaz de salvar o estado atual do seu trabalho no arquivo `.abnf` associado. | `main_app.py`, `gerenciador_projeto.py` |
| RF-004 | Salvar Como | O usuário deverá ser capaz de salvar o projeto atual em um novo arquivo `.abnf`. | `main_app.py` |
| RF-005 | Listar Projetos Recentes | O sistema deverá exibir uma lista de projetos abertos recentemente na tela inicial para acesso rápido. | `tela_inicial.py`, `gerenciador_config.py` |
| RF-006 | Validar Caminho Recente | O sistema deverá verificar se um projeto recente ainda existe no disco antes de tentar abri-lo. | `tela_inicial.py` |

### RF-02: Configuração do Documento
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-007 | Definir Metadados | O usuário deverá ser capaz de definir os dados pré-textuais do documento (Título, Autores, Instituição, Curso, etc.). | `main_app.py` (`_criar_aba_geral`), `documento.py` |
| RF-008 | Mudar Tipo de Trabalho | O usuário deverá ser capaz de alterar o "Tipo de Trabalho" (ex: TCC para Artigo) a qualquer momento, e o sistema deverá reestruturar os capítulos. | `main_app.py` (`_on_template_selecionado`) |
| RF-009 | Configurar Brasão | O usuário deverá ser capaz de selecionar uma imagem de brasão para a capa. | `main_app.py`, `dialogo_brasao.py` |
| RF-010 | Definir Posição do Brasão | O usuário deverá ser capaz de definir a posição do brasão (Nenhum, Acima, Lados, Apenas Esquerdo/Direito). | `main_app.py` |
| RF-011 | Cortar Brasão (Retangular) | O usuário deverá ser capaz de aplicar um corte retangular na imagem do brasão. | `dialogo_brasao.py` (`CropLabel`) |
| RF-012 | Cortar Brasão (Poligonal) | O usuário deverá ser capaz de aplicar um corte poligonal (à mão livre) na imagem do brasão. | `dialogo_brasao.py` (`CropLabel`) |

### RF-03: Edição de Conteúdo e Estrutura
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-013 | Criar Capítulos | O usuário deverá ser capaz de adicionar novos capítulos (tópicos) e sub-capítulos (subtópicos). | `aba_conteudo.py` |
| RF-014 | Editar Conteúdo Textual | O usuário deverá ser capaz de digitar e editar o texto (conteúdo) do capítulo selecionado. | `aba_conteudo.py` (`QTextEdit`) |
| RF-015 | Renomear Capítulos | O usuário deverá ser capaz de renomear capítulos diretamente na árvore de estrutura. | `aba_conteudo.py` |
| RF-016 | Reordenar Capítulos | O usuário deverá ser capaz de reordenar capítulos e sub-capítulos usando "Arrastar e Soltar" (Drag-and-Drop). | `aba_conteudo.py` (`ArvoreConteudo`) |
| RF-017 | Remover Capítulos | O usuário deverá ser capaz de remover um capítulo (e todos os seus sub-capítulos). | `aba_conteudo.py` |
| RF-018 | Inserir Quebra de Página | O usuário deverá ser capaz de inserir um marcador `{{QUEBRA_PAGINA}}` no texto. | `aba_conteudo.py` |
| RF-019 | Inserir Página em Branco | O usuário deverá ser capaz de inserir um marcador `{{PAGINA_EM_BRANCO}}` no texto. | `aba_conteudo.py` |
| RF-020 | Filtrar Estrutura | O usuário deverá ser capaz de filtrar a árvore de capítulos por título ou conteúdo. | `aba_conteudo.py` (`_filtrar_arvore`) |

### RF-04: Gerenciamento de Ativos (Tabelas, Figuras, Fórmulas)
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-021 | Criar/Editar Tabela | O usuário deverá ser capaz de criar e editar tabelas, definindo título, fonte, estilo de borda e centralização. | `aba_conteudo.py`, `dialogo_tabela.py` |
| RF-022 | Criar/Editar Figura | O usuário deverá ser capaz de carregar e editar figuras, definindo título, fonte e largura no documento. | `aba_conteudo.py`, `dialogo_figura.py` |
| RF-023 | Cortar Figura | O usuário deverá ser capaz de aplicar cortes (retangular e poligonal) nas figuras. | `dialogo_figura.py` (`CropLabel`) |
| RF-024 | Criar/Editar Fórmula | O usuário deverá ser capaz de criar e editar fórmulas usando um editor LaTeX com preview em tempo real (MathJax). | `aba_conteudo.py`, `DialogoFormula.py`, `latex_renderer.html` |
| RF-025 | Inserir Marcadores de Ativos | O usuário deverá ser capaz de inserir marcadores (placeholders) para tabelas, figuras e fórmulas no texto. | `aba_conteudo.py` |
| RF-026 | Filtrar Ativos | O usuário deverá ser capaz de filtrar as listas de ativos para mostrar todos ou apenas os usados no capítulo atual. | `aba_conteudo.py` (`atualizar_bancos_visuais`) |

### RF-05: Gerenciamento de Referências
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-027 | Adicionar Referência | O usuário deverá ser capaz de adicionar referências dos tipos "Livro", "Artigo" e "Site". | `main_app.py`, `dialogs.py` (`ReferenciaDialog`) |
| RF-028 | Formulário Dinâmico | A janela de referências deverá exibir campos de entrada diferentes com base no tipo selecionado. | `dialogs.py` (`update_form_visibility`) |
| RF-029 | Editar Referência | O usuário deverá ser capaz de editar uma referência existente. | `main_app.py` |
| RF-030 | Remover Referência | O usuário deverá ser capaz de remover uma referência existente. | `main_app.py` |

### RF-06: Geração de Saída (Preview e DOCX)
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-031 | Gerar Documento `.docx` | O sistema deverá gerar um arquivo `.docx` final com base em todos os dados e regras. | `main_app.py`, `gerador_docx.py` |
| RF-032 | Renderizar Capa e Folha de Rosto | O `.docx` deverá conter a capa e a folha de rosto formatadas com os metadados e brasões. | `gerador_docx.py`, `normas_abnt.py` |
| RF-033 | Renderizar Sumário (TOC) | O `.docx` deverá conter um sumário funcional com números de página corretos. | `gerador_docx.py` (`_atualizar_sumario_com_word`) |
| RF-034 | Renderizar Capítulos (DOCX) | O `.docx` deverá renderizar todos os capítulos e subcapítulos com numeração e estilos ABNT. | `gerador_docx.py` |
| RF-035 | Quebra de Página de Capítulo | O `.docx` deverá iniciar cada capítulo de Nível 1 (1, 2, 3...) em uma nova página. | `gerador_docx.py` |
| RF-036 | Renderizar Ativos (DOCX) | O `.docx` deverá substituir os marcadores por tabelas, figuras (PNG) e fórmulas (PNG) renderizadas. | `gerador_docx.py` |
| RF-037 | Renderizar Referências (DOCX) | O `.docx` deverá renderizar a lista de referências em ordem alfabética no final do documento. | `gerador_docx.py`, `referencia.py` |
| RF-038 | Gerar Pré-visualização (HTML) | O sistema deverá exibir uma pré-visualização em HTML que simule o documento final. | `main_app.py`, `gerador_preview.py` |
| RF-039 | Simular Paginação (HTML) | O preview deverá simular as páginas A4 (21x29.7cm) e as margens ABNT (3/2/3/2 cm) usando CSS. | `gerador_preview.py` |
| RF-040 | Simular Quebras (HTML) | O preview deverá simular quebras de página para capítulos de Nível 1 e comandos manuais (`{{QUEBRA_PAGINA}}`). | `gerador_preview.py` |
| RF-041 | Simular Sumário (HTML) | O preview deverá gerar um sumário com números de página *estimados* e links de âncora clicáveis. | `gerador_preview.py` |

### RF-07: Segurança e Recuperação
| ID | Requisito | Descrição | Módulo(s) Responsável(is) |
| :--- | :--- | :--- | :--- |
| RF-042 | Auto-Save (Recuperação) | O sistema deverá salvar automaticamente o trabalho do usuário em um arquivo de recuperação (`.abnf.recovery`) em intervalos definidos. | `main_app.py` (`autosave_timer`), `gerenciador_recuperacao.py` |
| RF-043 | Restaurar Sessão | O sistema deverá detectar arquivos de recuperação ao iniciar e oferecer ao usuário a opção de restaurá-los ou descartá-los. | `main_app.py`, `dialogs.py` (`DialogoRecuperacao`) |
| RF-044 | Backup (Versão) | O sistema deverá, a cada salvamento manual, criar um backup (`.abnf.bak`) da versão anterior do arquivo. | `main_app.py`, `gerenciador_recuperacao.py` |
| RF-045 | Limpeza de Backups | O sistema deverá manter apenas um número máximo de backups (ex: 10), excluindo os mais antigos. | `gerenciador_recuperacao.py` (`_limpar_backups_antigos`) |

---

## 2. Requisitos Não Funcionais (RNF)

Os Requisitos Não Funcionais descrevem as **qualidades, restrições e padrões operacionais** do sistema. Eles definem *como* o sistema deve ser, em vez de *o que* ele deve fazer.

### RNF-01: Usabilidade e Interface
| ID | Requisito | Descrição |
| :--- | :--- | :--- |
| RNF-001 | Intuitividade | A interface deve ser intuitiva para usuários com conhecimento das normas ABNT, mas não necessariamente com conhecimento técnico avançado. |
| RNF-002 | Feedback Visual | O sistema deve fornecer feedback claro para ações do usuário (ex: `*` no título ao modificar, cursor de espera ao salvar). |
| RNF-003 | Confirmação Destrutiva | O sistema deve exigir confirmação do usuário antes de ações destrutivas (ex: "Remover Tópico?", "Descartar Recuperação?"). |
| RNF-004 | Idioma | A interface do usuário, incluindo mensagens de erro e instruções, deve ser primariamente em Português (pt-BR). |

### RNF-02: Desempenho
| ID | Requisito | Descrição |
| :--- | :--- | :--- |
| RNF-005 | Fluidez de Edição | A digitação no editor de texto (`QTextEdit`) deve permanecer 100% fluida, sem "gaguejar", independentemente do tamanho do documento. (Conseguido via `textChanged` salvando apenas em memória). |
| RNF-006 | Atualização de Preview (Debounce) | A pré-visualização (uma operação "pesada") não deve ser executada a cada tecla. Ela deve ser executada após um "debounce" (atraso) de 750ms após o usuário parar de digitar. |
| RNF-007 | Atualização de Preview (Não-Bloqueante) | A geração do preview não deve travar a interface do usuário. (Conseguido pelo `QTimer`). |
| RNF-008 | Medição de Texto (Preview) | A simulação de paginação do preview deve ser precisa, medindo a largura real das palavras (via `Pillow`) em vez de "adivinhar" (via `CARACTERES_POR_LINHA`). |

### RNF-03: Confiabilidade e Robustez
| ID | Requisito | Descrição |
| :--- | :--- | :--- |
| RNF-009 | Proteção contra Perda de Dados | O sistema não deve perder o trabalho do usuário em caso de travamento do aplicativo ou desligamento do SO. (Conseguido pelo Auto-Save em `%LOCALAPPDATA%`). |
| RNF-010 | Proteção contra Erro Humano | O sistema deve proteger o usuário de salvar alterações indesejadas, fornecendo backups automáticos (`.abnf.bak`) a cada salvamento manual. |
| RNF-011 | Portabilidade de Projeto | O formato de arquivo `.abnf` (Zip) deve ser 100% portátil. Um usuário deve poder mover um único arquivo para outro computador (com o Formatheus) e abri-lo com todas as imagens, fórmulas e dados intactos. (Conseguido via `gerenciador_projeto.py` usando caminhos relativos). |
| RNF-012 | Tratamento de Erro de Arquivo | O sistema deve lidar graciosamente com arquivos ausentes (ex: fontes não encontradas, imagens deletadas, projetos recentes movidos) sem travar, exibindo mensagens de erro informativas. |

### RNF-04: Restrições de Implementação e "Gambiarras"
| ID | Requisito | Descrição |
| :--- | :--- | :--- |
| RNF-013 | **Restrição (Windows): Sumário** | A funcionalidade de atualização automática do Sumário (`_atualizar_sumario_com_word`) é **dependente do Windows** e **requer o Microsoft Word** instalado (via `pywin32`). Em outros sistemas, o sumário será gerado sem números de página. |
| RNF-014 | **Restrição (Windows): Fonte do Preview** | A medição exata de texto no `gerador_preview.py` é **dependente do Windows**, pois assume que a fonte `times.ttf` está localizada em `C:/Windows/Fonts/`. Falhará no macOS/Linux. |
| RNF-015 | Restrição (Dependência Web) | A renderização de fórmulas (`DialogoFormula`) depende de uma conexão de internet na *primeira* vez que é executada para baixar a biblioteca `MathJax` de um CDN. |
| RNF-016 | Restrição (Dependência PySide6) | A aplicação requer o pacote `PySide6-WebEngineWidgets` (que às vezes requer instalação separada) para o preview e o editor de fórmulas. |
| RNF-017 | Dívida Técnica (DRY) | As classes `CropLabel` (em `dialogo_brasao.py` e `dialogo_figura.py`) estão duplicadas. Uma alteração em uma deve ser replicada manualmente na outra. |

Com certeza. O capítulo de "Metodologia" é onde você explica *como* o seu TCC (o software Formatheus) foi construído, desde a concepção até a implementação, justificando as suas escolhas.

O capítulo de "Arquitetura" (que detalhamos) foca no **"O Quê?"** (Quais são os blocos?). A "Metodologia" foca no **"Como?"** e no **"Por quê?"** (Como esses blocos foram construídos e por que você escolheu essas ferramentas?).

Aqui está uma estrutura detalhada para o seu capítulo de Metodologia, usando todo o conhecimento que documentamos sobre o seu programa.

---

# METODOLOGIA DE DESENVOLVIMENTO

### 2.1. Introdução

Este capítulo detalha a metodologia empregada para a concepção, projeto e desenvolvimento da aplicação *Formatheus*. O objetivo foi construir uma ferramenta de software robusta, capaz de gerenciar todo o ciclo de vida da escrita acadêmica, desde a edição de texto até a geração de documentos finais (`.docx`) e pré-visualizações em tempo real (`HTML`), em estrita conformidade com as normas ABNT.

A metodologia pode ser dividida em quatro pilares:
1.  **Abordagem de Desenvolvimento** (O processo de gerenciamento).
2.  **Levantamento de Requisitos** (A definição do problema).
3.  **Seleção de Tecnologias** (As ferramentas escolhidas e suas justificativas).
4.  **Metodologia de Implementação** (As soluções técnicas para os problemas complexos).

### 2.2. Abordagem de Desenvolvimento

Para este projeto, foi adotado um modelo de **Desenvolvimento Iterativo e Incremental**, que se assemelha à Prototipagem Evolutiva.

Ao invés de um modelo "Cascata" (Waterfall) rígido, onde todos os requisitos são definidos antes do início da codificação, a abordagem iterativa permitiu que o software fosse construído em ciclos:

1.  **Ciclo 1 (Base):** Implementação da estrutura de dados (`documento.py`), o editor de texto (`aba_conteudo.py`) e a geração de um `.docx` simples (`gerador_docx.py`).
2.  **Ciclo 2 (Preview):** Adição do complexo `gerador_preview.py` para fornecer feedback visual instantâneo ao usuário.
3.  **Ciclo 3 (Recursos Avançados):** Adição de funcionalidades complexas, como o `DialogoFormula` (com renderização LaTeX) e as ferramentas de corte (`CropLabel`).
4.  **Ciclo 4 (Robustez):** Implementação dos sistemas de segurança (`gerenciador_recuperacao.py`).

Essa abordagem permitiu que *feedbacks* (como os bugs de paginação que encontramos) fossem corrigidos e refinados em cada ciclo, levando a um produto final mais estável.

### 2.3. Levantamento de Requisitos

A primeira etapa do projeto consistiu em definir as necessidades dos usuários (estudantes, pesquisadores). O resultado foi o documento de **Requisitos Funcionais (RF)** e **Não Funcionais (RNF)** que detalhamos anteriormente.

* **Requisitos Funcionais Chave:** Incluíram o gerenciamento de projeto (`.abnf`), a edição de capítulos, o gerenciamento de ativos (figuras, tabelas, fórmulas), a geração de preview em tempo real e a exportação final para `.docx` com regras ABNT.
* **Requisitos Não Funcionais Chave:** Incluíram a *precisão* da simulação (RNF-008), a *portabilidade* do projeto (RNF-011) e a *robustez* contra perda de dados (RNF-009, RNF-010).

### 2.4. Seleção de Tecnologias (Justificativa da "Stack")

A escolha das ferramentas foi um pilar central da metodologia, focando em desempenho, robustez e na capacidade de resolver problemas complexos específicos:

* **Linguagem: `Python`**
    * **Justificativa:** Linguagem de alto nível, com vasta biblioteca padrão (usada para `os`, `json`, `zipfile`, `tempfile`) e um ecossistema maduro para as bibliotecas necessárias (PySide6, Pillow, python-docx).

* **Interface Gráfica (GUI): `PySide6` (Qt 6)**
    * **Justificativa:** Um framework *cross-platform* robusto para aplicações desktop. Foi escolhido por sua rica biblioteca de componentes (QWidgets) e, crucialmente, por incluir o módulo `QtWebEngineWidgets`.

* **Formato de Projeto (`.abnf`): `zipfile` + `json`**
    * **Justificativa:** Para atender ao requisito de portabilidade (RNF-011), foi projetado um formato de arquivo customizado. O `.abnf` é uma "artemanha" padrão da indústria (um arquivo `.zip` renomeado) que contém o `documento.json` (o "cérebro" com os dados) e todas as mídias (imagens, fórmulas), garantindo que o projeto seja um arquivo único e autocontido.

* **Renderização Híbrida: `QWebEngineView`**
    * **Justificativa:** Esta foi uma decisão de arquitetura chave. Renderizar um documento A4 paginado com fluxo de texto justificado em Qt nativo (`QTextDocument`) é extremamente complexo e limitado.
    * **Solução:** A metodologia foi **híbrida**. Usamos o `QWebEngineView` (um navegador Chromium) para renderizar um preview em `HTML/CSS`, que é a tecnologia *certa* para layout de texto e página.

* **Renderização de Fórmulas: `MathJax` (JavaScript)**
    * **Justificativa:** Em vez de "reinventar a roda", a metodologia foi integrar a melhor ferramenta de renderização LaTeX do mercado. O `QWebEngineView` permitiu carregar o `latex_renderer.html`, que importa o `MathJax` de um CDN.

* **Geração de Documento: `python-docx`**
    * **Justificativa:** A biblioteca padrão para criar e manipular arquivos `.docx` programaticamente, sem depender de uma instalação do Microsoft Word (exceto para o sumário).

* **Processamento de Imagem e Texto: `Pillow (PIL)`**
    * **Justificativa:** Usada para duas tarefas críticas:
        1.  **Imagens:** Processamento de backend para as ferramentas de corte (`img.crop`, `ImageDraw.polygon`).
        2.  **Texto:** A "artemanha" central do `gerador_preview.py`. Foi usada para carregar a fonte (`ImageFont.truetype`) e *medir* a largura exata de cada palavra (`font_medidor.getbbox`), permitindo uma simulação de paginação precisa.

* **Atualização do Sumário: `pywin32`**
    * **Justificativa (Gambiarra):** A biblioteca `python-docx` *não pode* atualizar campos dinâmicos (como um Sumário). A única solução programática foi usar `pywin32` para automatizar o MS Word (em segundo plano) e forçá-lo a preencher os números de página do sumário.
    * **Mitigação:** O código é "defensivo" e só tenta executar esta etapa se `WIN32_AVAILABLE` for `True`, não travando em outros sistemas.

### 2.5. Metodologia de Implementação (Solução dos Desafios)

A metodologia de implementação focou em resolver os desafios mais complexos do projeto através de "artemanhas" e padrões de design específicos:

* **Desafio 1: Sincronização do Preview (O Problema do "Vazamento" e "Desperdício")**
    * **Problema:** O simulador (Python) e o renderizador (CSS) não concordavam sobre a altura do conteúdo, causando vazamento de texto ou margens inferiores gigantes.
    * **Metodologia (Medição Exata):** A solução foi abandonar a "adivinhação" (`CARACTERES_POR_LINHA`). A metodologia de `gerador_preview.py` foi refatorada para:
        1.  **Sincronizar Réguas:** O Python (`ALTURA_CONTEUDO_PAGINA = 24.7`) e o CSS (`padding: 3cm 2cm 2cm 3cm;`) foram forçados a usar as mesmas medidas de página.
        2.  **Medir Texto:** `_calcular_altura_paragrafo` usa `Pillow` para medir a largura exata de cada palavra em `Times New Roman 12pt` e calcular o número exato de linhas.
        3.  **Medir Mídia:** `_get_image_aspect_ratio` (com `PIL`) e `_get_svg_aspect_ratio` (com `re`) medem a proporção real de figuras e fórmulas para calcular suas alturas exatas.
        4.  **Quebra de Palavra Longa:** A lógica foi robustecida para lidar com o caso "AAAAA..." (palavras sem espaço), quebrando-as à força.

* **Desafio 2: Edição Avançada de Imagem (Corte Poligonal)**
    * **Problema:** `PIL` não suporta corte poligonal.
    * **Metodologia (Máscara Alfa):** A solução (em `dialogo_figura.py` e `dialogo_brasao.py`) foi a técnica de máscara:
        1.  Uma máscara preta (`Image.new("L")`) do tamanho da imagem é criada.
        2.  O polígono do usuário é desenhado em branco (`ImageDraw.polygon`) na máscara.
        3.  A imagem original é "colada" em uma nova imagem transparente, usando a máscara (`img.paste(mask=mask)`). Isso faz com que apenas os pixels "brancos" (o polígono) sejam mantidos.

* **Desafio 3: Comunicação Híbrida (Python <-> JavaScript)**
    * **Problema:** Como fazer o `DialogoFormula.py` (Python) obter o `.svg` renderizado pelo `latex_renderer.html` (JavaScript)?
    * **Metodologia (Download Falso):** A solução foi uma "coreografia" de eventos:
        1.  Python chama `window.prepareAndTriggerDownload()` (JS).
        2.  JS cria um `Blob` (arquivo em memória) e simula um clique em um link de download.
        3.  Python (PySide6) intercepta o sinal `downloadRequested`.
        4.  Python salva o "download" (o `.svg`) em uma pasta temporária.
        5.  Python (Qt) usa `QSvgRenderer` para converter esse `.svg` em `.png`.

* **Desafio 4: Segurança de Dados (Robustez)**
    * **Problema:** O usuário pode perder dados por travamentos ou erro humano.
    * **Metodologia (Três Camadas):**
        1.  **Auto-Save (Falha do App):** O `gerenciador_recuperacao.py` salva um `.abnf.recovery` em `%LOCALAPPDATA%`. A "artemanha" de usar uma pasta do sistema (em vez da pasta do projeto) protege os dados mesmo se o projeto estiver em um pen drive que seja removido.
        2.  **Backup (Erro Humano):** O `gerenciador_recuperacao.py` salva um `.abnf.bak` com timestamp na pasta do projeto a cada "Salvar" manual, criando um histórico de versões.
        3.  **Portabilidade (Transferência):** O `gerenciador_projeto.py` salva caminhos de imagem *relativos* dentro do `.abnf` (zip), mas os "reidrata" para caminhos *absolutos* (apontando para uma pasta `tempfile`) ao carregar.

### 2.6. Metodologia de Testes

Para garantir a qualidade do software, uma abordagem de testes multi-nível foi empregada:

1.  **Testes de Unidade (Implícitos):** Cada módulo foi testado individualmente. (Ex: Testar se `referencia.py` formatava corretamente o nome "SILVA, Matheus da").
2.  **Testes de Integração:** Focados na "conversa" entre os módulos. (Ex: Testar se os marcadores `{{...}}` criados pelo `aba_conteudo.py` eram corretamente lidos e substituídos pelo `gerador_docx.py` e `gerador_preview.py`).
3.  **Testes Funcionais (Casos de Uso):** Testes de ponta-a-ponta. (Ex: "1. Criar novo TCC. 2. Adicionar brasão. 3. Escrever a introdução. 4. Adicionar uma figura com corte poligonal. 5. Gerar o .docx. 6. Verificar se o .docx e o preview estão idênticos").
4.  **Testes de Estresse e Regressão:**
    * **Estresse:** Testar o simulador de preview com casos extremos (ex: a "palavra infinita" `AAAAA...`).
    * **Regressão:** Após corrigir um bug (ex: o "vazamento" de texto), verificar se a correção não introduziu um bug oposto (ex: o "desperdício" de espaço).