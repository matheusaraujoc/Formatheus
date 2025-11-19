Esta é a documentação técnica dedicada exclusivamente aos dois pilares centrais da infraestrutura do Formatheus: **O Sistema de Versionamento Inteligente** e o **Protocolo de Segurança HMAC**.

---

# 📘 Documentação Técnica: Infraestrutura de Distribuição e Segurança
**Projeto:** Formatheus
**Status:** Production Ready (v2.4)

---

## PARTE 1: Sistema de Controle de Versão e Distribuição

Este sistema foi projetado para garantir que o usuário esteja sempre na versão mais estável, otimizando o fluxo de entrada para evitar downloads redundantes na primeira instalação via instalador.

### 1. Arquitetura de Dados

O controle de versão depende da sincronização entre o estado local do cliente e a "Fonte da Verdade" no servidor.

| Componente | Localização | Descrição |
| :--- | :--- | :--- |
| **Local Config** | `launcher_config.json` | Armazena a chave `app_version`. **Padrão inicial:** `"0.0.0"` (indicando instalação limpa). |
| **Meta-Dados** | Firestore (`app_meta/latest_release`) | Documento mestre contendo: `version` (ex: "1.0.2"), `release_notes` (texto), `is_mandatory` (bool). |
| **Binários** | Cloudflare R2 | Armazenamento de objetos (S3-compatible) contendo os arquivos `.zip` (ex: `app_v1.0.2.zip`). |
| **Comparador** | Biblioteca `packaging` | Utilizada para comparação semântica de versões (garante que `1.10.0` > `1.9.0`). |

### 2. Lógica de Fluxo (Launcher)

Ao iniciar, o Launcher consulta a Cloud Function `check_for_update`. Com base na resposta e no estado local, o sistema decide entre três caminhos críticos:

#### Cenário A: Otimização de Instalador (First Run)
*Ocorre quando o usuário acabou de instalar o programa usando o instalador offline.*
1.  **Condição:** A versão no JSON é `"0.0.0"` **E** os arquivos executáveis do app já existem na pasta `/app`.
2.  **Lógica:** O sistema entende que o pacote já contém os binários.
3.  **Ação:**
    * Ignora o download.
    * Atualiza silenciosamente o `launcher_config.json` com a versão recebida do servidor (ex: muda de "0.0.0" para "1.0.0").
    * Inicia a aplicação imediatamente.
4.  **Resultado:** Experiência de "clicar e abrir" sem espera.

#### Cenário B: Atualização Necessária
*Ocorre quando uma nova versão é publicada.*
1.  **Condição:** A versão local é numericamente menor que a versão remota (ex: `1.0.0 < 1.0.1`).
2.  **Ação:** Exibe a interface de atualização.
    * **Se `is_mandatory=true`:** Exibe apenas o botão "Atualizar Agora". Bloqueia o acesso ao app.
    * **Se `is_mandatory=false`:** Exibe botões "Atualizar" e "Pular". O botão "Pular" inicia o app na versão antiga.
3.  **Processo de Download:**
    * Solicita URL assinada (segura) ao backend via `get_download_url`.
    * Baixa o `.zip` em *stream* (sem carregar tudo na memória) para uma pasta temporária.
    * Limpa a pasta `/app` antiga e extrai o novo conteúdo.
    * Atualiza o `launcher_config.json`.

#### Cenário C: Sistema Atualizado
1.  **Condição:** Versão local é igual ou maior que a remota.
2.  **Ação:** Inicia a aplicação imediatamente.

---

## PARTE 2: Sistema de Segurança (Protocolo HMAC Dinâmico)

Este sistema impede a execução não autorizada do executável principal (`main_app`), garantindo que todas as validações de licença e atualizações do Launcher sejam respeitadas. Substitui o método inseguro de "chave estática".

### 1. O Conceito: "The Handshake"
O sistema utiliza criptografia **HMAC-SHA256** para criar um token de autenticação efêmero (temporário). O Launcher atua como o "Gerador" e o Main App como o "Validador".

### 2. Variáveis Críticas

* **SALT (Segredo Compartilhado):**
    * Valor: `b"OWIYVQUXJ64IJETQPXT1UZZ16YBNI8"`
    * Função: Uma string de bytes de alta entropia hardcoded em ambos os binários. É a base da segurança.
* **Janela de Tempo (Tolerância):**
    * Valor: `5 minutos`.
    * Função: Impede ataques de repetição (*Replay Attacks*) onde um invasor tenta reutilizar um token antigo válido.

### 3. Fluxo de Execução Seguro

#### Etapa 1: Geração (No `launcher.py`)
Imediatamente antes de iniciar o processo filho, o Launcher executa:
1.  Captura o Timestamp UTC atual (`T`).
2.  Gera o Token: `Hash = HMAC_SHA256(SALT, T)`.
3.  Cria uma cópia do ambiente do sistema: `env_dict = os.environ.copy()`.
4.  Injeta duas variáveis neste dicionário:
    * `FORMATHEUS_TOKEN`: O Hash gerado.
    * `FORMATHEUS_TIMESTAMP`: O tempo `T`.
5.  **Ponto Crítico:** Executa o app passando o ambiente modificado explicitamente:
    `subprocess.Popen(..., env=env_dict)`

#### Etapa 2: Validação (No `main_app.py`)
Ao ser iniciado, **antes** de carregar qualquer interface gráfica (`QApplication`), o App executa a função `run_hmac_security_check()`:

1.  **Leitura:** Busca as variáveis `FORMATHEUS_TOKEN` e `FORMATHEUS_TIMESTAMP` no ambiente.
2.  **Verificação 1 (Existência):** Se as variáveis não existem, exibe erro fatal ("Inicie pelo Launcher") e encerra (`sys.exit`).
3.  **Verificação 2 (Tempo):** Converte o Timestamp recebido. Se a diferença entre `Agora (UTC)` e `T` for maior que 5 minutos, exibe erro ("Token Expirado") e encerra.
4.  **Verificação 3 (Integridade):**
    * O App pega o seu próprio SALT e o `T` recebido.
    * Recalcula o Hash localmente.
    * Compara `Hash_Recebido == Hash_Calculado` usando `hmac.compare_digest` (para evitar ataques de timing).
    * Se divergirem, exibe erro ("Adulteração Detectada") e encerra.
5.  **Limpeza:** Se aprovado, remove as variáveis da memória do processo para dificultar a leitura por dump de memória.

### 4. Modo de Desenvolvimento (Bypass)

Para facilitar a depuração sem a necessidade de compilar ou rodar o launcher a cada teste:

* **Flag:** `DISABLE_LAUNCHER_CHECK` (no topo do `main_app.py`).
* **TRUE:** Desativa completamente a verificação de segurança.
* **FALSE:** Ativa a segurança máxima (Obrigatório para Build de Produção).

---

## Resumo da Interação



1.  **Launcher:** Verifica Versão -> (Se OK) -> Gera HMAC -> Injeta no ENV -> Abre Main.
2.  **Main:** Lê ENV -> Valida HMAC -> (Se OK) -> Carrega Interface.
3.  **Resultado:** É impossível abrir o programa clicando diretamente no executável principal ou usando um token antigo, forçando o fluxo de atualização e licença.

Esta é a documentação técnica dedicada exclusivamente aos dois pilares centrais da infraestrutura do Formatheus: **O Sistema de Versionamento Inteligente** e o **Protocolo de Segurança HMAC**.

---

# 📘 Documentação Técnica: Infraestrutura de Distribuição e Segurança
**Projeto:** Formatheus
**Status:** Production Ready (v2.4)

---

## PARTE 1: Sistema de Controle de Versão e Distribuição

Este sistema foi projetado para garantir que o usuário esteja sempre na versão mais estável, otimizando o fluxo de entrada para evitar downloads redundantes na primeira instalação via instalador.

### 1. Arquitetura de Dados

O controle de versão depende da sincronização entre o estado local do cliente e a "Fonte da Verdade" no servidor.

| Componente | Localização | Descrição |
| :--- | :--- | :--- |
| **Local Config** | `launcher_config.json` | Armazena a chave `app_version`. **Padrão inicial:** `"0.0.0"` (indicando instalação limpa). |
| **Meta-Dados** | Firestore (`app_meta/latest_release`) | Documento mestre contendo: `version` (ex: "1.0.2"), `release_notes` (texto), `is_mandatory` (bool). |
| **Binários** | Cloudflare R2 | Armazenamento de objetos (S3-compatible) contendo os arquivos `.zip` (ex: `app_v1.0.2.zip`). |
| **Comparador** | Biblioteca `packaging` | Utilizada para comparação semântica de versões (garante que `1.10.0` > `1.9.0`). |

### 2. Lógica de Fluxo (Launcher)

Ao iniciar, o Launcher consulta a Cloud Function `check_for_update`. Com base na resposta e no estado local, o sistema decide entre três caminhos críticos:

#### Cenário A: Otimização de Instalador (First Run)
*Ocorre quando o usuário acabou de instalar o programa usando o instalador offline.*
1.  **Condição:** A versão no JSON é `"0.0.0"` **E** os arquivos executáveis do app já existem na pasta `/app`.
2.  **Lógica:** O sistema entende que o pacote já contém os binários.
3.  **Ação:**
    * Ignora o download.
    * Atualiza silenciosamente o `launcher_config.json` com a versão recebida do servidor (ex: muda de "0.0.0" para "1.0.0").
    * Inicia a aplicação imediatamente.
4.  **Resultado:** Experiência de "clicar e abrir" sem espera.

#### Cenário B: Atualização Necessária
*Ocorre quando uma nova versão é publicada.*
1.  **Condição:** A versão local é numericamente menor que a versão remota (ex: `1.0.0 < 1.0.1`).
2.  **Ação:** Exibe a interface de atualização.
    * **Se `is_mandatory=true`:** Exibe apenas o botão "Atualizar Agora". Bloqueia o acesso ao app.
    * **Se `is_mandatory=false`:** Exibe botões "Atualizar" e "Pular". O botão "Pular" inicia o app na versão antiga.
3.  **Processo de Download:**
    * Solicita URL assinada (segura) ao backend via `get_download_url`.
    * Baixa o `.zip` em *stream* (sem carregar tudo na memória) para uma pasta temporária.
    * Limpa a pasta `/app` antiga e extrai o novo conteúdo.
    * Atualiza o `launcher_config.json`.

#### Cenário C: Sistema Atualizado
1.  **Condição:** Versão local é igual ou maior que a remota.
2.  **Ação:** Inicia a aplicação imediatamente.

---

## PARTE 2: Sistema de Segurança (Protocolo HMAC Dinâmico)

Este sistema impede a execução não autorizada do executável principal (`main_app`), garantindo que todas as validações de licença e atualizações do Launcher sejam respeitadas. Substitui o método inseguro de "chave estática".

### 1. O Conceito: "The Handshake"
O sistema utiliza criptografia **HMAC-SHA256** para criar um token de autenticação efêmero (temporário). O Launcher atua como o "Gerador" e o Main App como o "Validador".

### 2. Variáveis Críticas

* **SALT (Segredo Compartilhado):**
    * Valor: `b"OWIYVQUXJ64IJETQPXT1UZZ16YBNI8"`
    * Função: Uma string de bytes de alta entropia hardcoded em ambos os binários. É a base da segurança.
* **Janela de Tempo (Tolerância):**
    * Valor: `5 minutos`.
    * Função: Impede ataques de repetição (*Replay Attacks*) onde um invasor tenta reutilizar um token antigo válido.

### 3. Fluxo de Execução Seguro

#### Etapa 1: Geração (No `launcher.py`)
Imediatamente antes de iniciar o processo filho, o Launcher executa:
1.  Captura o Timestamp UTC atual (`T`).
2.  Gera o Token: `Hash = HMAC_SHA256(SALT, T)`.
3.  Cria uma cópia do ambiente do sistema: `env_dict = os.environ.copy()`.
4.  Injeta duas variáveis neste dicionário:
    * `FORMATHEUS_TOKEN`: O Hash gerado.
    * `FORMATHEUS_TIMESTAMP`: O tempo `T`.
5.  **Ponto Crítico:** Executa o app passando o ambiente modificado explicitamente:
    `subprocess.Popen(..., env=env_dict)`

#### Etapa 2: Validação (No `main_app.py`)
Ao ser iniciado, **antes** de carregar qualquer interface gráfica (`QApplication`), o App executa a função `run_hmac_security_check()`:

1.  **Leitura:** Busca as variáveis `FORMATHEUS_TOKEN` e `FORMATHEUS_TIMESTAMP` no ambiente.
2.  **Verificação 1 (Existência):** Se as variáveis não existem, exibe erro fatal ("Inicie pelo Launcher") e encerra (`sys.exit`).
3.  **Verificação 2 (Tempo):** Converte o Timestamp recebido. Se a diferença entre `Agora (UTC)` e `T` for maior que 5 minutos, exibe erro ("Token Expirado") e encerra.
4.  **Verificação 3 (Integridade):**
    * O App pega o seu próprio SALT e o `T` recebido.
    * Recalcula o Hash localmente.
    * Compara `Hash_Recebido == Hash_Calculado` usando `hmac.compare_digest` (para evitar ataques de timing).
    * Se divergirem, exibe erro ("Adulteração Detectada") e encerra.
5.  **Limpeza:** Se aprovado, remove as variáveis da memória do processo para dificultar a leitura por dump de memória.

### 4. Modo de Desenvolvimento (Bypass)

Para facilitar a depuração sem a necessidade de compilar ou rodar o launcher a cada teste:

* **Flag:** `DISABLE_LAUNCHER_CHECK` (no topo do `main_app.py`).
* **TRUE:** Desativa completamente a verificação de segurança.
* **FALSE:** Ativa a segurança máxima (Obrigatório para Build de Produção).

---

## Resumo da Interação



1.  **Launcher:** Verifica Versão -> (Se OK) -> Gera HMAC -> Injeta no ENV -> Abre Main.
2.  **Main:** Lê ENV -> Valida HMAC -> (Se OK) -> Carrega Interface.
3.  **Resultado:** É impossível abrir o programa clicando diretamente no executável principal ou usando um token antigo, forçando o fluxo de atualização e licença.