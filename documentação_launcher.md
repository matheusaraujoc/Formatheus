Esta é a documentação técnica completa do sistema de licenciamento e inicialização do Formatheus, detalhando a arquitetura e o fluxo de dados entre o back-end (Cloud Functions) e o cliente (Launcher).

---

## 📄 Documentação: Sistema de Licenciamento e Launcher (v2.0)

### 1. Visão Geral e Filosofia

O sistema é projetado em torno de um modelo de **Launcher "Porteiro"** e um **Back-end "Cérebro"**. O objetivo é criar uma experiência de usuário fluida (inicialização rápida, uso offline) enquanto se mantém um controle de licenciamento robusto e seguro no servidor.

* **O Back-end (`functions/`)**: É o cérebro. É a **única** parte do sistema que tem permissão para ler ou escrever no banco de dados. Ele é o "porteiro" que valida tudo.
* **O Launcher (`laucher.py`)**: É o único executável que o cliente roda. Ele **não tem** acesso ao banco de dados. Ele apenas faz perguntas ao Back-end. Sua principal responsabilidade é gerenciar um "ingresso" offline (`license.lease`).
* **O Modelo "Lease" (Ingresso Offline)**: Para evitar custos e permitir o uso offline, o Launcher não contata o servidor a cada inicialização. Após uma ativação bem-sucedida, o servidor emite um "lease" (um arquivo criptografado) com validade de **7 dias**. O Launcher pode reutilizar esse ingresso por 7 dias sem precisar de internet. Após 7 dias, ele é forçado a se reconectar ao servidor para renovar o ingresso e verificar se a licença não foi revogada.

---

## ☁️ 2. O Back-end: Cloud Functions (`functions/main.py`)

Esta é a parte do sistema que roda na nuvem do Google. Ela é 100% segura e inacessível ao usuário final.

### 2.1. Propósito
Servir como o único intermediário (API) entre o cliente e o banco de dados (Firestore). O cliente *nunca* tem permissão para ler ou escrever no Firestore diretamente.

### 2.2. Tecnologias
* **Firebase Functions:** Para hospedar o código Python na nuvem.
* **Firebase Admin SDK:** Para dar ao nosso código permissão de administrador para ler/escrever no Firestore.
* **Python:** A linguagem de lógica.

### 2.3. Arquivos Principais

* **`main.py`**: Contém o código das duas funções.
* **`requirements.txt`**: Define as dependências do servidor (`firebase-admin`, `firebase-functions`).

### 2.4. Funções (Endpoints)

Usamos **Funções "Callable"** (`@https_fn.on_call()`), que são endpoints HTTP seguros projetados para serem chamados diretamente por outros aplicativos.

#### `activate_device(data, context)`
Esta é a função principal, servindo tanto para a **primeira ativação** quanto para **verificações de rotina**.

* **Entrada (o que o Launcher envia):**
    * `license_key`: A chave do usuário (ex: `FMT-XXXX`).
    * `device_id`: O UUID da máquina do usuário.
    * `hostname`: O nome do computador (ex: "DESKTOP-MATHEUS").

* **Fluxo de Lógica:**
    1.  A função recebe a chamada e valida os dados de entrada.
    2.  Inicia uma **Transação do Firestore**. (Isso garante que a operação seja "tudo ou nada", prevenindo que dois dispositivos peguem o último slot de licença ao mesmo tempo).
    3.  Busca o documento da licença: `licenses/{license_key}`.
    4.  **Verifica Falhas (em ordem):**
        * A licença existe? (Se não, retorna `not-found`).
        * O `status` é `"active"`? (Se não, retorna `permission-denied`).
        * A data `expires_at` é *anterior* a `hoje`? (Se sim, retorna `permission-denied: Esta licença expirou`).
    5.  **Verifica o Dispositivo:**
        * O `device_id` já está no mapa `active_devices`?
        * **SIM (Verificação de Rotina):** Apenas atualiza o `last_seen` para agora. Retorna `{"status": "success", "real_expiry": "..."}`.
    6.  **Verifica o Limite (Novo Dispositivo):**
        * Lê o `plan_id` da licença (ex: `annual`).
        * Lê o documento `plans/annual` para pegar o `machine_limit` (ex: 1).
        * Compara o limite com o número atual de dispositivos (ex: `len(active_devices)`).
    7.  **Toma a Decisão:**
        * **CENÁRIO A (Vaga disponível):** `current_count < limit`.
            * Adiciona o novo `device_id` e `hostname` ao mapa `active_devices`.
            * Retorna `{"status": "success", "message": "Dispositivo ativado.", "real_expiry": "..."}`.
        * **CENÁRIO B (Limite Atingido):** `current_count >= limit`.
            * **Não** modifica o banco de dados.
            * Retorna `{"status": "limit_reached", "devices": [...]}` (com a lista de dispositivos já ativos para o usuário escolher).
    8.  **A Resposta de Sucesso:** O campo `real_expiry` (data de expiração real) é crucial. Ele é enviado de volta ao cliente para que ele possa criar seu *lease* offline.

#### `replace_device(data, context)`
Função chamada apenas quando o usuário escolhe *qual* dispositivo antigo desativar.

* **Entrada:**
    * `license_key`, `new_device_id`, `new_hostname`
    * `old_device_id`: O UUID do dispositivo a ser removido.
* **Fluxo de Lógica:**
    1.  Valida os dados de entrada.
    2.  Busca o documento da licença.
    3.  Verifica se o `old_device_id` realmente existe no mapa (como segurança).
    4.  Executa uma atualização no Firestore que **remove o `old_device_id`** e **adiciona o `new_device_id`** ao mapa `active_devices`.
    5.  Retorna `{"status": "success", "real_expiry": "..."}`.

---

### 💻 3. O Cliente: Launcher (`laucher.py`)

Este é o executável do cliente. Ele é o "portão" que decide se o `main_app.py` (o programa real) pode ser executado.

### 3.1. Propósito
Gerenciar a ativação da licença, o "lease" offline, as atualizações do aplicativo e, finalmente, iniciar o programa.

### 3.2. Tecnologias
* **PySide6:** Para a UI (janela de ativação/atualização).
* **`requests`:** Para chamar as Cloud Functions.
* **`pycryptodomex`:** Para criptografar e descriptografar o `license.lease`.
* **`uuid`:** Para gerar o `device_id` único.

### 3.3. Arquivos Helper

O `laucher.py` não faz tudo sozinho. Ele usa dois "ajudantes":

* **`firebase_client.py`:**
    * **Função:** `call_firebase_function(name, data)`
    * **Propósito:** É o único arquivo que contém as **URLs** das Cloud Functions. Ele formata a requisição `requests.post` no padrão que as funções `onCall` esperam (ex: `{"data": {...}}`) e interpreta a resposta (ex: `response.json()["result"]`). Lida com todos os erros de rede (Timeout, HTTP, etc.).

* **`lease_manager.py`:**
    * **Função:** `write_lease(expiry_date, device_id)` e `read_lease(device_id)`.
    * **Propósito:** Gerencia o `license.lease` (o ingresso offline).
    * **Criptografia:** A chave de criptografia é gerada usando `PBKDF2` (uma função de derivação de chave) a partir de uma combinação do `device_id` do usuário e uma "pimenta" (`PEPPER`) secreta embutida no código.
    * **Importante:** Isso significa que o `license.lease` de um usuário **não pode** ser copiado e usado no computador de outro usuário, pois o `device_id` será diferente, a chave de descriptografia falhará e o `read_lease()` retornará `None`.
    * **Função:** `check_lease_validity(lease_data)`
    * **Propósito:** Contém a lógica de verificação offline. Define a validade do lease (ex: `LEASE_DURATION_DAYS = 7`).

### 3.4. Arquivos de Configuração Locais

O Launcher gerencia dois arquivos na máquina do usuário:

1.  **`launcher_config.json` (O "Registro Permanente")**
    * Armazena dados que não devem ser perdidos.
    * `device_id`: O UUID único desta máquina.
    * `license_key`: A chave `FMT-XXXX` (salva após a primeira ativação).
    * `app_version`: A versão do `main_app` instalada (ex: "1.0.0").

2.  **`license.lease` (O "Ingresso Temporário")**
    * É um arquivo **binário criptografado**. Não pode ser lido por humanos.
    * Armazena as datas:
        * `last_check`: A data da última verificação online bem-sucedida.
        * `real_expiry`: A data de expiração real do plano (vinda do servidor).

### 3.5. O Fluxo de Execução (`main()` no `laucher.py`)

Esta é a lógica principal do programa, executada em fases.

* **Fase 1: Verificação de Licença (Offline-First)**
    1.  `launcher_config = get_launcher_config()` (Lê o JSON)
    2.  `device_id = get_or_create_device_id(config)` (Gera o ID da máquina, se for a 1ª vez)
    3.  `lease_data = lease_manager.read_lease(device_id)` (Tenta ler o ingresso)
    4.  **Se `lease_data` for encontrado:**
        * Chama `lease_manager.check_lease_validity(lease_data)`.
        * **Retorno `ok`:** Sucesso. O usuário pode entrar. Define `is_activated = True` e `ui_mode = "update"`. (Vai para a Fase 3)
        * **Retorno `expired`:** Licença expirou. Define `ui_mode = "show_error"` e `error_message = "Sua licença expirou..."`. (Vai para a Fase 4)
        * **Retorno `stale`:** Ingresso offline venceu (ex: 7 dias se passaram). Define `ui_mode = "verify_online"`. (Vai para a Fase 2)
    5.  **Se `lease_data` for `None` (não encontrado, apagado ou corrompido):**
        * Verifica o `config.json` pela `license_key` (que foi salva na primeira ativação).
        * **Se a chave existir:** O usuário é legítimo, mas o ingresso está faltando. Define `ui_mode = "verify_online"`. (Vai para a Fase 2)
        * **Se a chave NÃO existir:** O usuário é novo. Define `ui_mode = "activate"`. (Vai para a Fase 4)

* **Fase 2: Verificação Online (Se `ui_mode == "verify_online"`)**
    1.  Chama `firebase_client.call_firebase_function("activate_device", ...)`.
    2.  **Se `status == "success"`:**
        * A licença é válida e o lease foi renovado.
        * Chama `lease_manager.write_lease(response['real_expiry'], device_id)` para criar um novo ingresso de 7 dias.
        * Define `is_activated = True` e `ui_mode = "update"`.
    3.  **Se `status == "limit_reached"`:**
        * O usuário precisa desativar uma máquina.
        * Define `is_activated = False` e `ui_mode = "replace_device"`.
        * Salva a `response` (que contém a lista de máquinas) para a UI.
    4.  **Se `status == "error"`:**
        * A licença foi revogada, expirou, etc.
        * Define `ui_mode = "show_error"` e `error_message = response['message']`.

* **Fase 3: Verificação de Atualização (O "Caminho Feliz")**
    1.  Este passo **só** acontece se `is_activated == True`.
    2.  Chama `check_for_update(app_version)`.
    3.  **Se NÃO houver `update_info` E NÃO for `is_first_run` (o app já está instalado e atualizado):**
        * **`subprocess.Popen(main_app.py)`** (Inicia o programa real).
        * **`sys.exit(0)`** (Fecha o launcher silenciosamente).
        * *Este é o fluxo de 99% das vezes: o usuário clica, e o programa abre em 1 segundo.*
    4.  Se houver uma atualização ou se o app estiver faltando (`is_first_run`), o fluxo continua para a Fase 4.

* **Fase 4: Carregar a Interface Gráfica (O "Caminho Lento")**
    1.  Se o `sys.exit(0)` não foi chamado, o launcher precisa da intervenção do usuário.
    2.  `carregar_modulos_ui()` é chamado (importa o pesado `PySide6`).
    3.  Se `ui_mode == "show_error"`, mostra o `QMessageBox.critical` com o `error_message` e encerra.
    4.  A `LauncherWindow` é criada e o `ui_mode` é passado para ela (`activate`, `replace_device`, `install` ou `update`).
    5.  A classe `LauncherWindow` então usa seu método `_build_ui()` para mostrar os widgets corretos (mostrar o campo de chave se `ui_mode == "activate"`, ou o botão "Instalar" se `ui_mode == "install"`).
    6.  O usuário interage com a UI (ex: clica em "Ativar").
    7.  A UI chama as funções de *handle* (ex: `handle_activation()`).
    8.  `handle_activation()` chama o `firebase_client`, e se for bem-sucedido, salva a licença e o *lease* e muda a `ui_mode` para `install`.
    9.  O usuário então clica em "Instalar", que chama `handle_install_update()`.
    10. O launcher (simula) o download, fecha-se, e o `main_app` é finalmente iniciado.

    Aqui estão os dois manuais detalhados que você solicitou.

O primeiro é um **Manual de Uso** para sua equipe.
O segundo é um **Manual de Instalação/Setup** para um novo desenvolvedor.

-----

-----

## 👨‍💼 Manual de Uso: Painel de Administrador Formatheus

Este manual é destinado aos administradores e à equipe de suporte. Ele explica como usar o `FormatheusAdmin.exe` (o painel) para gerenciar as licenças dos clientes no dia a dia.

### 1\. 🚀 Primeiro Acesso (Login)

Ao iniciar o programa (`FormatheusAdmin.exe`), você verá a tela de login.

1.  **E-mail:** Digite o e-mail de administrador que foi cadastrado no Firebase (ex: `admin@formatheus.com`).
2.  **Senha:** Digite a senha associada a este e-mail.
3.  **Lembrar e-mail:**
      * **Marcado:** O programa salvará seu e-mail (mas não sua senha) em um arquivo `admin_app_config.json`. Na próxima vez que você abrir, o campo de e-mail já estará preenchido.
      * **Desmarcado:** O e-mail não será salvo.
4.  Clique em **"Entrar"**.

### 2\. 📊 A Tela Principal (Dashboard)

Após o login, você verá o dashboard. Esta é sua visão geral de todas as licenças de clientes.

#### Colunas da Tabela

  * **Chave (ID):** O ID da licença (ex: `FMT-XXXX-....`).
  * **E-mail:** O e-mail do cliente associado à licença.
  * **Plano:** O ID do plano (ex: `annual`, `lifetime_3`).
  * **Status:** Mostra se a licença está `Active` (Verde) ou `Inactive` (Vermelho).
  * **Dispositivos:** Quantas máquinas estão *atualmente* usando esta licença.
  * **Data Expiração:** A data em que o plano expira (ou "Vitalício").
  * **Dias Restantes:** Um cálculo de quantos dias faltam para a expiração.
      * **Verde:** Mais de 30 dias.
      * **Laranja:** Menos de 30 dias (aviso de renovação).
      * **Vermelho:** Expirado.
  * **Ações:** Botões para gerenciar a licença.

#### Botões Principais

  * **Criar Nova Licença:** Abre o diálogo para gerar uma nova chave para um cliente.
  * **Recarregar Lista:** Força o painel a buscar os dados mais recentes do Firebase (útil se outro admin tiver feito alterações).
  * **Filtrar:** Uma barra de busca que filtra a tabela em tempo real por Chave ou E-mail.

### 3\. 🆕 Como Criar uma Nova Licença (Fluxo Manual)

Este é o fluxo para vender uma licença manualmente.

1.  No dashboard, clique no botão **"Criar Nova Licença"**.
2.  A janela "Criar Nova Licença" aparecerá.
3.  **Preencha o E-mail do Cliente:** (ex: `cliente.novo@gmail.com`).
4.  **Selecione o Plano:**
      * O menu "Plano" é carregado **diretamente do Firebase** (da coleção `plans`).
      * **Se você selecionar um plano com duração (ex: "Plano Anual (Limite: 1)")**: O campo "Data de Expiração" será preenchido automaticamente (ex: Hoje + 365 dias). Você pode alterar essa data se necessário.
      * **Se você selecionar um plano vitalício (ex: "Plano Equipe (Vitalício)")**: O campo "Data de Expiração" será **desabilitado** e preenchido com "31/12/2099", pois ele não expira.
5.  Clique em **"Ok"**.

#### O que Acontece:

  * O painel chama o `firebase_admin_manager` para gerar uma chave única (ex: `FMT-DF5B-8A1C-9E0D`).
  * A licença é salva no Firestore com a data de expiração correta.
  * Um pop-up de **Sucesso** aparece, exibindo a chave gerada.
  * A chave **já foi copiada automaticamente** para sua área de transferência (CTRL+V).
  * Agora você só precisa **colar** essa chave em um e-mail e enviá-la ao seu cliente.

### 4\. 🛠️ Como Gerenciar Licenças Existentes

#### A. Desativar ou Reativar uma Licença

(Usado para reembolsos, cancelamentos ou testes).

1.  Encontre a licença que você deseja alterar (use o filtro se necessário).
2.  Na coluna **"Ações"**, clique no botão:
      * **"Desativar" (Botão Vermelho):** Se a licença estiver `Active`.
      * **"Reativar" (Botão Padrão):** Se a licença estiver `Inactive`.
3.  Confirme a ação.
4.  O status da licença será atualizado no Firebase. Na próxima vez que o cliente abrir o `laucher.py` e o "lease" dele expirar, o programa será bloqueado.

#### B. Copiar Chave ou E-mail (Suporte)

(Usado quando um cliente perde a chave).

1.  Encontre a licença do cliente na tabela.
2.  **Clique com o botão direito** em qualquer lugar da linha daquele cliente.
3.  Um menu de contexto aparecerá.
4.  Clique em **"Copiar Chave: FMT-..."** ou **"Copiar E-mail: ..."**.
5.  O dado será copiado para sua área de transferência.

### 5\. 🚪 Sair do Painel

Você tem duas opções no menu **"Arquivo"**:

1.  **Sair (Logout):** Esta é a opção **recomendada**. Ela limpa seu e-mail salvo (do "Lembrar e-mail") e leva você de volta à tela de login. Use isso se estiver em um computador compartilhado.
2.  **Fechar Programa:** Encerra o aplicativo. Se você marcou "Lembrar e-mail", seu e-mail estará lá na próxima vez que você abrir.

-----

-----

## 🛠️ Manual de Instalação: Ambiente de Desenvolvimento

Este manual é para um **novo desenvolvedor da equipe** que acabou de clonar o repositório "cru" e precisa configurar todo o ambiente (Back-end e Front-end do Admin) do zero em uma nova máquina.

### Visão Geral da Arquitetura

O sistema tem duas partes que precisam de configuração:

1.  **Firebase (Back-end):** O banco de dados (Firestore), a autenticação (Auth) e as funções (Cloud Functions) que rodam na nuvem.
2.  **Admin Painel (Front-end):** O programa PySide6 local (`admin_painel/`) que você usa para gerenciar o back-end.

-----

### Fase 1: Configuração do Backend (Firebase)

Este é o passo mais importante. Você só precisa fazer isso uma vez por projeto.

#### 1.1. Acessar o Projeto Firebase

  * Faça login no [Firebase](https://firebase.google.com) e selecione o projeto (ex: `Formatheus-Licenciamento`).

#### 1.2. Configurar o Banco de Dados (Firestore)

  * **Local:** `Build` \> `Cloud Firestore`
  * **Ação:**
    1.  Clique em **"Criar banco de dados"**.
    2.  Selecione **"Iniciar em modo de produção"** (Inicia bloqueado).
    3.  Selecione a localização **`southamerica-east1` (São Paulo)**. (Esta escolha é permanente\!).
    4.  Clique em **"Ativar"**.

#### 1.3. Criar os Planos (Manual)

  * O Painel Admin precisa *ler* os planos. Você deve criá-los manualmente.
  * **Ação:**
    1.  Em `Cloud Firestore`, clique em **"+ Iniciar coleção"**.
    2.  ID da Coleção: **`plans`**
    3.  Clique em **"Adicionar documento"** (Ex: Plano Anual).
          * ID do documento: `annual`
          * Campo 1 (string): `name` = `Plano Anual`
          * Campo 2 (number): `machine_limit` = `1`
          * Campo 3 (number): `duration_days` = `365`
    4.  Clique em **"Salvar"**.
    5.  Adicione outro documento (Ex: Plano Vitalício).
          * ID do documento: `lifetime_team`
          * Campo 1 (string): `name` = `Plano Equipe (Vitalício)`
          * Campo 2 (number): `machine_limit` = `5`
          * *(Não adicione `duration_days` para planos vitalícios)*
    6.  Clique em **"Salvar"**.

#### 1.4. Configurar a Autenticação (Auth)

  * **Local:** `Build` \> `Authentication`
  * **Ação:**
    1.  Clique em **"Começar"**.
    2.  Vá para a aba **"Sign-in method"**.
    3.  Clique em **"E-mail/senha"** e **Ative** o primeiro switch. Salve.
    4.  Vá para a aba **"Users"**.
    5.  Clique em **"Adicionar usuário"**.
    6.  Digite o e-mail e a senha que **você, desenvolvedor,** usará para logar no `AdminLoginWindow`.

#### 1.5. Aplicar as Regras de Segurança

  * **Local:** `Build` \> `Cloud Firestore` \> Aba **"Regras"**.

  * **Ação:**

    1.  Apague todo o conteúdo.
    2.  Copie e cole as regras abaixo (elas protegem suas coleções, permitindo que apenas admins escrevam dados).

    <!-- end list -->

    ```javascript
    rules_version = '2';
    service cloud.firestore {
      match /databases/{database}/documents {

        function isAdmin() {
          return request.auth != null && request.auth.token.email_verified == true;
        }

        match /licenses/{licenseKey} {
          allow get: if request.auth != null; 
          allow list: if isAdmin();            
          allow write: if isAdmin();
        }

        match /plans/{planId} {
          allow read: if request.auth != null;
          allow write: if isAdmin();
        }
      }
    }
    ```

    3.  Clique em **"Publicar"**.

-----

### Fase 2: Obtenção das Chaves Secretas (Crítico)

O seu painel admin local precisa de duas chaves para se conectar ao Firebase.

#### 2.1. Chave 1: Chave de Serviço (A Chave Mestra)

  * **Local:** ⚙️ (Configurações do projeto) \> **"Contas de serviço"**.
  * **Ação:**
    1.  Clique em **"Gerar nova chave privada"**.
    2.  Um arquivo `.json` será baixado.
    3.  Renomeie este arquivo para **`admin_service_account.json`**.
    4.  Mova este arquivo para dentro da pasta `admin_painel` do seu repositório.

#### 2.2. Chave 2: Chave da API Web (A Chave da Porta)

  * **Local:** ⚙️ (Configurações do projeto) \> **"Geral"**.
  * **Ação:**
    1.  Role até "Seus apps". Se não houver app da Web (`</>`), crie um (nome: `Admin Panel`).
    2.  Clique no seu app da Web.
    3.  No objeto `firebaseConfig`, copie o valor da **`apiKey`**.
    4.  Na pasta `admin_painel`, crie um novo arquivo: **`admin_api_config.json`**.
    5.  Abra este arquivo e cole a chave neste formato:
        ```json
        {
          "apiKey": "SUA-CHAVE-COPIADA-AQUI"
        }
        ```
    6.  **IMPORTANTE:** Adicione `*.json` ao seu arquivo `.gitignore` global para nunca enviar essas chaves ao repositório.

-----

### Fase 3: Configuração do Ambiente Local (Python / Admin Panel)

Agora vamos rodar o painel admin na sua máquina.

1.  **Clonar o Repositório:** (Se ainda não o fez)
    `git clone [URL_DO_SEU_REPOSITORIO]`

2.  **Criar Ambiente Virtual (Recomendado):**

    ```bash
    cd ABNTHelper # Vá para a raiz do projeto
    python -m venv venv_admin
    .\venv_admin\Scripts\activate
    ```

3.  **Instalar Dependências Python (Painel Admin):**

    ```bash
    pip install pyside6 qdarktheme firebase-admin requests pycryptodomex
    ```

    *(`pycryptodomex` é para o `lease_manager.py` do launcher, mas é bom tê-lo no ambiente).*

4.  **Rodar o Painel Admin:**

      * Certifique-se de que os arquivos `.json` (da Fase 2) estão na pasta `admin_painel`.
      * Execute o "portão de entrada":
        ```bash
        python admin_painel/admin_login.py
        ```
      * O login deve aparecer. Use o e-mail/senha que você criou na Fase 1.4.

-----

### Fase 4: Configuração e Deploy das Cloud Functions (Backend)

O Painel Admin funciona, mas o *launcher do cliente* falhará, pois as Cloud Functions (`activate_device`, `replace_device`) ainda não estão na nuvem.

1.  **Instalar Firebase Tools (Globalmente):**

      * (Requer [Node.js](https://nodejs.org/en) instalado).
      * `npm install -g firebase-tools`

2.  **Fazer Login no Firebase:**

      * `firebase login`
      * Siga as instruções no navegador.

3.  **Inicializar o Projeto (Se necessário):**

      * Se o arquivo `firebase.json` **não** existir na raiz (`ABNTHelper`), rode `firebase init functions`.
      * Selecione "Use an existing project", escolha seu projeto.
      * Selecione `Python`.
      * **NÃO** sobrescreva (`Overwrite?`) nenhum arquivo se ele perguntar.

4.  **Instalar Dependências das Funções (Separado):**

      * As Cloud Functions têm seu próprio ambiente virtual. Precisamos instalar as bibliotecas *lá*.
      * Navegue até a pasta `functions`:
        ```bash
        cd functions
        ```
      * Execute o pip *de dentro* do venv das funções:
        ```bash
        .\venv\Scripts\python.exe -m pip install -r requirements.txt
        ```
      * (Se `requirements.txt` estiver incompleto, certifique-se de que ele contenha `firebase-admin` e `firebase-functions`).

5.  **Fazer o Deploy (Publicar):**

      * Volte para a pasta raiz (`ABNTHelper`):
        ```bash
        cd ..
        ```
      * Execute o comando de deploy:
        ```bash
        firebase deploy --only functions
        ```
      * Aguarde a conclusão. O terminal mostrará "Successful create operation" para as suas funções.

### 🏁 Setup Completo

Seu ambiente está pronto. O Painel Admin (`admin_login.py`) funciona localmente, e as Cloud Functions (`activate_device`) estão online na nuvem, prontas para receber chamadas do `laucher.py` do cliente.

## Comandos Uteis

cd ..

pip install -r requirements.txt

.\venv\Scripts\activate

cd functions