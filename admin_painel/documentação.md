Aqui está a documentação atualizada e completa do Painel de Administrador.

Esta versão (v2.0) inclui as adições críticas para o **gerenciamento de datas de expiração** e a **exibição de dias restantes**.

-----

## 📄 Documentação Técnica: Painel de Administrador (Formatheus) - v2.0

### 1\. Visão Geral

#### 1.1. Objetivo

O **Painel de Administrador** é o centro de controle do sistema de licenciamento do Formatheus. É um aplicativo de desktop (PySide6) **interno e privado**, destinado exclusivamente a você e sua equipe.

**Ele NUNCA deve ser distribuído aos seus clientes.**

#### 1.2. Funções Principais

  * **Autenticação Segura:** Garante que apenas administradores autorizados (definidos no Firebase Authentication) possam acessar o painel.
  * **Gerenciamento de Planos:** Lê os planos de licença (limites de máquinas e **duração em dias**) que você define no Firestore.
  * **Criação de Licenças:** Gera chaves de licença únicas (`FMT-XXXX-XXXX`) e **calcula e salva automaticamente a data de expiração** (`expires_at`) com base no plano selecionado.
  * **Consulta de Licenças:** Exibe, pesquisa e filtra todas as licenças de clientes existentes, incluindo **data de expiração e dias restantes**, com códigos de cores para status.
  * **Gerenciamento de Status:** Permite "Ativar" ou "Desativar" uma licença com um clique.
  * **Funcionalidades de Suporte:** Permite copiar chaves e e-mails facilmente (clique com o botão direito) para o suporte ao cliente.

#### 1.3. Tecnologias Utilizadas

  * **Python 3**
  * **PySide6:** Para toda a interface gráfica.
  * **qdarktheme:** Para o estilo da interface.
  * **Firebase Admin SDK (`firebase-admin`):** Para comunicação segura e autenticada com o Firestore (leitura e escrita).
  * **Firebase Authentication (API REST):** Para verificar com segurança o e-mail e a *senha* do administrador.
  * **Requests:** Para fazer a chamada da API REST de login.

-----

### 2\. Arquitetura do Projeto

O painel é dividido em módulos, cada um com uma responsabilidade clara:

  * **`admin_utils.py` (O "Canivete Suíço")**

      * **Propósito:** Armazena funções utilitárias compartilhadas para evitar erros de "Importação Circular".
      * **Funções:**
          * `resource_path()`: Garante que os arquivos (ícones, JSONs de config) sejam encontrados, funcione o script no modo de desenvolvimento ou compilado em `.exe`.
          * `load_admin_config()` / `save_admin_config()`: Gerencia o arquivo `admin_app_config.json` para a função "Lembrar e-mail".

  * **`firebase_admin_manager.py` (O "Cérebro")**

      * **Propósito:** Isola *toda* a lógica de back-end. Nenhuma outra parte do código (UI) "fala" diretamente com o Firebase.
      * **Funções:**
          * `__init__()`: Inicializa o Firebase Admin SDK usando a chave `admin_service_account.json`.
          * `admin_login()`: **Valida a senha** do admin usando a API REST do Firebase (lendo a `apiKey` do `admin_api_config.json`).
          * `get_all_plans()`: **Lê** a coleção `plans` do Firestore para popular os menus de seleção.
          * `get_all_licenses()`: **Lê** a coleção `licenses` para popular a tabela principal.
          * `create_license(email, plan_id, expiration_date)`: **Escreve** um novo documento de licença. Agora aceita um `expiration_date` opcional e o salva no campo `expires_at` do Firestore.
          * `toggle_license_status()`: **Atualiza** o campo `status` de uma licença existente.

  * **`admin_login.py` (O "Portão de Entrada")**

      * **Propósito:** É o **arquivo principal (`__main__`)** que você executa.
      * **Fluxo:**
        1.  Inicia o `QApplication`.
        2.  Mostra a `AdminLoginWindow`.
        3.  Carrega o e-mail salvo (se houver) de `admin_app_config.json`.
        4.  Ao clicar em "Entrar", chama `firebase_admin_manager.admin_login()`.
        5.  Se o login for bem-sucedido, ele salva o e-mail (se "Lembrar" estiver marcado) e abre o `AdminDashboardWindow`.
        6.  Gerencia o loop de "Sair" (Logout) através de um código de saída (`exit_code == 99`), que o permite voltar à tela de login.

  * **`dialog_nova_licenca.py` (O "Formulário")**

      * **Propósito:** Um `QDialog` para criar uma nova licença.
      * **Fluxo:**
        1.  Chama `firebase_admin_manager.get_all_plans()` para preencher o `QComboBox`.
        2.  **Nova Lógica:** Contém um `QDateEdit` (calendário) para a data de expiração.
        3.  **Nova Lógica:** Possui o slot `on_plan_changed()`. Quando um plano é selecionado, ele lê o campo `duration_days` do plano (ex: 365) e **calcula automaticamente a data de expiração** (Hoje + 365 dias).
        4.  **Nova Lógica:** O campo de data é **desabilitado** se o plano for vitalício (não possuir `duration_days`), sendo preenchido com `31/12/2099`.
        5.  Chama `firebase_admin_manager.create_license()` passando a data de expiração (ou `None` se for vitalício).
        6.  Copia a chave gerada para a área de transferência.

  * **`admin_dashboard.py` (O "Painel Principal")**

      * **Propósito:** A janela `QMainWindow` principal que exibe os dados após o login.
      * **Funções:**
          * **Nova UI:** A tabela agora tem **8 colunas**, incluindo "Data Expiração" e "Dias Restantes".
          * **Nova Lógica:** Utiliza uma classe helper, `NumericTableWidgetItem`, para permitir a **ordenação correta por data e dias** (clicando no cabeçalho da coluna).
          * **Nova Lógica:** `carregar_licencas()` agora faz a matemática de datas (`datetime.now(timezone.utc) - expires_at`).
          * **Nova Lógica:** Aplica **cores de formatação** na coluna "Dias Restantes" (Vermelho para expirado, Laranja para \<30 dias, Verde para OK).
          * Abre o `DialogoNovaLicenca` ao clicar no botão "Criar...".
          * Fornece o menu de "Sair" (Logout) e o menu de clique direito (Copiar).

-----

### 3\. Setup e Instalação (Para um Novo Admin)

Se um novo membro da equipe precisar rodar o painel, ele deve seguir estes passos:

1.  **Clonar o Projeto:**

      * `git clone [URL_DO_SEU_REPOSITORIO]`
      * Navegar para a pasta `admin_painel`.

2.  **Instalar Dependências:**

      * `pip install pyside6 qdarktheme firebase-admin requests`

3.  **Configurar Chaves do Firebase (Obrigatório):**

      * **Chave de Serviço (Secreta):**
          * Vá ao Console do Firebase \> ⚙️ \> Configurações do Projeto \> Contas de Serviço.
          * Clique em "Gerar nova chave privada".
          * Renomeie o `.json` baixado para **`admin_service_account.json`**.
          * Coloque este arquivo dentro da pasta `admin_painel`.
      * **Chave da API Web (Pública, mas sensível):**
          * Vá ao Console do Firebase \> ⚙️ \> Configurações do Projeto \> Geral.
          * Em "Seus apps", selecione seu App da Web (ou crie um).
          * Copie o valor da `apiKey`.
          * Crie um arquivo chamado **`admin_api_config.json`** na pasta `admin_painel`.
          * Cole a chave lá dentro: `{"apiKey": "SUA_CHAVE_AQUI"}`

4.  **Configurar Acesso do Admin:**

      * Vá ao Console do Firebase \> Authentication \> Users.
      * Clique em **"Add user"**.
      * Cadastre o e-mail e a senha que este admin usará para logar no painel.

5.  **Configurar Planos no Firestore (CRÍTICO):**

      * Vá ao Console do Firebase \> Firestore Database.
      * Crie a coleção `plans`.
      * **Plano com Duração (Ex: Anual):**
          * ID do documento: `annual`
          * Campo 1: `name` (string) -\> `Plano Anual`
          * Campo 2: `machine_limit` (number) -\> `1`
          * Campo 3: **`duration_days`** (number) -\> **`365`**
      * **Plano Vitalício (Ex: Equipe/Testes):**
          * ID do documento: `lifetime_team`
          * Campo 1: `name` (string) -\> `Plano de Equipe (Vitalício)`
          * Campo 2: `machine_limit` (number) -\> `5`
          * *(Note a **ausência** do campo `duration_days`. Isso é o que o identifica como vitalício).*

6.  **Executar:**

      * `python admin_login.py`

-----

### 4\. Manutenção e Solução de Problemas

  * **"FileNotFoundError: admin\_service\_account.json"**

      * **Causa:** O arquivo `.json` da Conta de Serviço não está na pasta `admin_painel` ou está com o nome errado.
      * **Solução:** Siga o Passo 3.3.

  * **"E-mail ou senha inválidos"**

      * **Causa 1:** O e-mail/senha digitados estão errados.
      * **Causa 2:** O usuário não foi cadastrado no **Firebase Authentication** (Passo 3.4).
      * **Causa 3:** A `apiKey` no `admin_api_config.json` está errada.

  * **"O campo 'Plano' está vazio ou com erro"**

      * **Causa:** A coleção `plans` está vazia ou não existe no Firestore.
      * **Solução:** Siga o Passo 3.5 e crie os documentos dos planos manualmente.

  * **Como adicionar um novo plano (ex: "Mensal")**

    1.  Vá ao Console do Firebase \> Firestore Database.
    2.  Na coleção `plans`, clique em "Adicionar documento".
    3.  ID do documento: `monthly`
    4.  Campos:
          * `name` (string) = `Plano Mensal`
          * `machine_limit` (number) = `1`
          * **`duration_days`** (number) = **`30`**
    5.  **Pronto.** Na próxima vez que você abrir o `DialogoNovaLicenca`, o "Plano Mensal" aparecerá automaticamente e já calculará os 30 dias de expiração.

  * **"A coluna 'Dias Restantes' está errada ou 'Expirado'"**

      * **Causa:** Isso pode ser um problema de Fuso Horário (Timezone). O script `admin_dashboard.py` compara a data de expiração com a data/hora atual em **UTC** (`datetime.now(timezone.utc)`).
      * **Solução:** Isso é o comportamento esperado. O Firebase salva os Timestamps em UTC por padrão, e o script os compara em UTC. Isso garante que uma licença expire ao mesmo tempo para todos no mundo, independentemente do fuso horário do admin.

  * **Como ver os detalhes de uma licença (máquinas, data exata, etc.)?**

    1.  No Console do Firebase \> Firestore, vá para `licenses/{CHAVE_DO_CLIENTE}`.
    2.  Lá você verá todos os campos que o script salvou:
          * `active_devices`: O mapa de máquinas ativas.
          * `expires_at`: O timestamp exato de quando a licença expira.
          * `status`: `active` ou `inactive`.

-----

### 5\. Compilação (Distribuição para sua Equipe)

Quando você quiser criar um `.exe` do painel:

1.  Instale o PyInstaller: `pip install pyinstaller`
2.  Rode o comando de compilação (a partir da pasta `ABNTHelper`):

<!-- end list -->

```bash
pyinstaller --onefile --windowed --name "FormatheusAdmin" ^
 --icon="admin_painel/admin_assets/icons/formatheus_admin.ico" ^
 --add-data "admin_painel/admin_service_account.json;." ^
 --add-data "admin_painel/admin_api_config.json;." ^
 --add-data "admin_painel/admin_utils.py;." ^
 --add-data "admin_painel/firebase_admin_manager.py;." ^
 --add-data "admin_painel/dialog_nova_licenca.py;." ^
 --add-data "admin_painel/admin_dashboard.py;." ^
 --add-data "admin_painel/admin_assets;admin_assets" ^
 admin_painel/admin_login.py
```

  * **`--onefile`**: Cria um único `.exe`.
  * **`--windowed`**: Remove o console (janela preta) ao executar.
  * **`--add-data`**: **Crucial.** Este comando copia seus arquivos `.json`, os outros scripts `.py` (que agora são dependências) e sua pasta de ícones *para dentro* do `.exe`, permitindo que o `resource_path` os encontre.

Aqui está a **versão 2.0** do manual de setup.

Esta versão foi atualizada para incluir a lógica de **duração dos planos** e **datas de expiração**, que são essenciais para o funcionamento dos novos recursos que implementamos no Painel de Administrador (como o cálculo de dias restantes).

-----

## 📄 Manual de Setup (v2.0): Backend de Licenciamento (Firebase)

### Fase 1: Criação do Projeto Firebase

O primeiro passo é criar o "contêiner" na nuvem que abrigará seu banco de dados e suas regras.

1.  **Criar a Conta:**

      * Acesse [firebase.google.com](https://firebase.google.com).
      * Faça login com sua conta do Google e clique em **"Começar"**.

2.  **Criar o Projeto:**

      * Clique em **"+ Adicionar projeto"**.
      * Dê um nome ao seu projeto (ex: `Formatheus-Licenciamento`).
      * Na tela "Google Analytics", você pode **desativar** o "Ativar o Google Analytics neste projeto". Ele não é necessário para o sistema de licenças.
      * Clique em **"Criar projeto"** e aguarde a conclusão.

-----

### Fase 2: Configuração do Banco de Dados (Firestore)

Aqui é onde as licenças e os planos serão armazenados.

1.  **Acessar o Firestore:**

      * No menu "Build" (Construir) à esquerda do seu novo projeto, clique em **Cloud Firestore**.
      * Clique no botão **"Criar banco de dados"**.

2.  **Modo de Segurança:**

      * Selecione **"Iniciar em modo de produção"**. Isso garante que seu banco de dados comece bloqueado (ninguém pode ler ou escrever) até que você defina as regras corretas.

3.  **⚠️ Definir a Localização (Importante\!)**

      * O Firebase perguntará onde você quer hospedar seu banco de dados.
      * Selecione a região **`southamerica-east1` (São Paulo)**.
      * **AVISO:** Esta escolha é **PERMANENTE**. Você não pode alterá-la depois. Escolher São Paulo garante a menor latência (velocidade) para seus clientes no Brasil.
      * Clique em **"Ativar"**.

4.  **Criar a Coleção `plans` (Passo Manual):**

      * Seu banco de dados agora existe, mas está vazio. O Painel Admin precisa *ler* os planos que você vende. Você deve criá-los manualmente.
      * Clique em **"+ Iniciar coleção"**.
      * **ID da Coleção:** Digite **`plans`** (exatamente assim, em minúsculas).
      * Clique em "Próximo".

5.  **Criar os Planos (Documentos):**

      * Agora você precisa adicionar os planos que seu Painel Admin irá ler.

    #### Exemplo A: Plano com Duração (Anual)

    1.  **ID do documento:** Digite **`annual`**
    2.  **Campo 1:**
          * ID do campo: `name`
          * Tipo: `string`
          * Valor: `Plano Anual`
    3.  Clique em **"+ Adicionar campo"**.
    4.  **Campo 2:**
          * ID do campo: `machine_limit`
          * Tipo: `number`
          * Valor: `1`
    5.  Clique em **"+ Adicionar campo"**.
    6.  **Campo 3 (NOVO):**
          * ID do campo: **`duration_days`**
          * Tipo: `number`
          * Valor: **`365`**
    7.  Clique em **"Salvar"**.

    #### Exemplo B: Plano Vitalício (Equipe/Testes)

    1.  Com a coleção `plans` selecionada, clique em **"+ Adicionar documento"**.
    2.  **ID do documento:** `lifetime_team`
    3.  **Campo 1:** `name` (string) -\> `Plano Equipe (Vitalício)`
    4.  **Campo 2:** `machine_limit` (number) -\> `5`
    5.  Clique em **"Salvar"**.

    > **Importante:** Para planos vitalícios, **não** adicione o campo `duration_days`. A *ausência* desse campo é o que diz ao Painel Admin que o plano é vitalício, fazendo com que o calendário de expiração seja desabilitado.

    #### Exemplo C: Plano com Duração (Mensal)

    1.  Clique em **"+ Adicionar documento"**.
    2.  **ID do documento:** `monthly`
    3.  **Campo 1:** `name` (string) -\> `Plano Mensal`
    4.  **Campo 2:** `machine_limit` (number) -\> `1`
    5.  **Campo 3:** `duration_days` (number) -\> `30`
    6.  Clique em **"Salvar"**.

-----

### Fase 3: Configuração da Autenticação (Login do Admin)

Aqui, você define *quais* usuários (você e sua equipe) têm permissão para usar o Painel Admin.

1.  **Acessar o Authentication:**

      * No menu "Build" (Construir), clique em **Authentication**.
      * Clique em **"Começar"**.

2.  **Ativar o Método de Login:**

      * Clique na aba **"Sign-in method"** (Método de login).
      * Na lista, clique em **"E-mail/senha"**.
      * Ative o primeiro switch (**Ativado**) e clique em **"Salvar"**.

3.  **Criar seu Usuário Admin:**

      * Clique na aba **"Users"** (Usuários).
      * Clique em **"+ Adicionar usuário"**.
      * **E-mail:** Digite o e-mail que você usará para logar no Painel Admin (ex: `admin@formatheus.com`).
      * **Senha:** Crie uma senha forte (esta será a senha que você digitará na tela de login do Painel Admin).
      * Clique em **"Adicionar usuário"**.

-----

### Fase 4: Aplicação das Regras de Segurança

Agora, vamos dizer ao Firestore quem pode ler e escrever em suas coleções.

1.  Volte para o **Cloud Firestore** (no menu "Build").
2.  Clique na aba **"Regras"**.
3.  **Apague todo o texto** que está lá (o `allow read, write: if false;`).
4.  **Copie e cole** as regras abaixo no editor:

<!-- end list -->

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {

    // Função que define um "Admin" como qualquer usuário logado
    // que tenha um e-mail verificado (o que exclui o login anônimo
    // do seu launcher).
    function isAdmin() {
      return request.auth != null && request.auth.token.email_verified == true;
    }

    // --- COLEÇÃO 'licenses' ---
    match /licenses/{licenseKey} {
      // O Admin pode ler a lista toda.
      // O cliente (launcher) só pode pedir (get) uma chave específica.
      allow get: if request.auth != null; 
      allow list: if isAdmin();            
      
      // Apenas o Admin pode criar, atualizar ou deletar licenças.
      allow write: if isAdmin();
    }

    // --- COLEÇÃO 'plans' ---
    match /plans/{planId} {
      // Todos (Admin e cliente) podem ler os planos.
      allow read: if request.auth != null;
      
      // Apenas o Admin pode criar ou alterar planos.
      allow write: if isAdmin();
    }
  }
}
```

5.  Clique em **"Publicar"**.

-----

### Fase 5: Obtenção das Chaves para o Painel Admin

Seu backend está pronto. Agora, você precisa das duas "chaves" para o seu código Python (`admin_painel`) se conectar a ele.

#### 5.1. Chave 1: A "Chave Mestra" (Service Account)

Esta é a chave super-secreta que dá ao seu painel controle total.

1.  No Console do Firebase, clique no ícone de engrenagem ⚙️ ao lado de "Visão geral do projeto".
2.  Clique em **"Configurações do projeto"**.
3.  Clique na aba **"Contas de serviço"**.
4.  Clique no botão **"Gerar nova chave privada"** e confirme.
5.  O Firebase fará o download de um arquivo `.json` (ex: `formatheus-licenciamento-firebase-adminsdk-....json`).
6.  **AÇÃO:** Mova este arquivo para sua pasta `admin_painel` e renomeie-o **exatamente** para: **`admin_service_account.json`**.
      * **⚠️ SEGURANÇA:** NUNCA envie este arquivo para o GitHub. Adicione `*.json` ao seu arquivo `.gitignore`.

#### 5.2. Chave 2: A "Chave da Porta" (Web API Key)

Esta é a chave "pública" que o seu painel usa para *tentar* fazer o login (verificar a senha).

1.  Nas **"Configurações do projeto"** (onde você já está), clique na aba **"Geral"**.

2.  Role para baixo até "Seus apps".

3.  Clique no ícone **`</>`** (WebApp) para registrar um novo aplicativo web (se você ainda não tiver um).

      * **Apelido do app:** Digite `Painel Admin` (o nome não afeta o código).
      * **NÃO** marque a opção "Configurar o Firebase Hosting".
      * Clique em **"Registrar app"**.

4.  O Firebase mostrará um objeto `firebaseConfig`.

5.  **Copie** o valor do campo **`apiKey`** (é uma string longa).

6.  **AÇÃO:** Na sua pasta `admin_painel`, crie um novo arquivo chamado **`admin_api_config.json`**.

7.  Abra este arquivo e cole a chave no seguinte formato:

    ```json
    {
      "apiKey": "SUA-CHAVE-DE-API-COPIADA-COLE-AQUI"
    }
    ```

### 🏁 Conclusão

Se você seguiu todos os passos, seu backend do Firebase está 100% configurado para a v2.0 do Painel Admin.

**Checklist Final:**

  * [ ] O Firestore está criado na região `southamerica-east1` (São Paulo).
  * [ ] A coleção `plans` existe e tem pelo menos um plano com `duration_days` (ex: `annual`) e um plano sem ele (ex: `lifetime_team`).
  * [ ] O Authentication tem o método "E-mail/senha" ativado.
  * [ ] Pelo menos um usuário admin foi criado na aba "Users" do Authentication.
  * [ ] As Regras do Firestore foram copiadas e publicadas.
  * [ ] O arquivo `admin_service_account.json` está na pasta `admin_painel`.
  * [ ] O arquivo `admin_api_config.json` está na pasta `admin_painel` e contém sua `apiKey`.

Se tudo isso estiver certo, você já pode executar `python admin_login.py` e o seu painel de administrador funcionará, calculando as datas de expiração automaticamente.