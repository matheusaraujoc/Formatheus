## 📄 Documentação Técnica: Painel de Administrador (Formatheus)

### 1\. Visão Geral

#### 1.1. Objetivo

O **Painel de Administrador** é o centro de controle do sistema de licenciamento do Formatheus. É um aplicativo de desktop (PySide6) **interno e privado**, destinado exclusivamente a você e sua equipe.

**Ele NUNCA deve ser distribuído aos clientes.**

#### 1.2. Funções Principais

  * **Autenticação Segura:** Garante que apenas administradores autorizados (definidos no Firebase Authentication) possam acessar o painel.
  * **Gerenciamento de Planos:** Lê os planos de licença (limites de máquinas, etc.) que você define no Firestore.
  * **Criação de Licenças:** Gera chaves de licença únicas (`FMT-XXXX-XXXX`) e as salva no Firestore.
  * **Consulta de Licenças:** Exibe, pesquisa e filtra todas as licenças de clientes existentes.
  * **Gerenciamento de Status:** Permite "Ativar" ou "Desativar" uma licença com um clique.
  * **Funcionalidades de Suporte:** Permite copiar chaves e e-mails facilmente para o suporte ao cliente.

#### 1.3. Tecnologias Utilizadas

  * **Python 3**
  * **PySide6:** Para toda a interface gráfica.
  * **qdarktheme:** Para o estilo da interface.
  * **Firebase Admin SDK (`firebase-admin`):** Para comunicação segura e autenticada com o Firestore (leitura e escrita).
  * **Firebase Authentication (API REST):** Para verificar com segurança o e-mail e a *senha* do administrador.

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
          * `create_license()`: **Escreve** um novo documento de licença na coleção `licenses`.
          * `toggle_license_status()`: **Atualiza** o campo `status` de uma licença existente.

  * **`admin_login.py` (O "Portão de Entrada")**

      * **Propósito:** É o **arquivo principal (`__main__`)** que você executa.
      * **Fluxo:**
        1.  Inicia o `QApplication`.
        2.  Mostra a `AdminLoginWindow`.
        3.  Carrega o e-mail salvo (se houver) de `admin_app_config.json`.
        4.  Ao clicar em "Entrar", chama `firebase_admin_manager.admin_login()`.
        5.  Se o login for bem-sucedido, ele salva o e-mail (se "Lembrar" estiver marcado) e abre o `AdminDashboardWindow`.
        6.  Gerencia o loop de "Sair" (Logout), que reinicia o processo.

  * **`admin_dashboard.py` (O "Painel Principal")**

      * **Propósito:** A janela `QMainWindow` principal que exibe os dados após o login.
      * **Funções:**
          * Exibe todas as licenças em um `QTableWidget`.
          * Chama `carregar_licencas()` para popular e atualizar a tabela.
          * Filtra a tabela (localmente) com o `search_input`.
          * Abre o `DialogoNovaLicenca` ao clicar no botão "Criar...".
          * Fornece o menu de "Sair" (Logout) e o menu de clique direito (Copiar).

  * **`dialog_nova_licenca.py` (O "Formulário")**

      * **Propósito:** Um `QDialog` para criar uma nova licença.
      * **Fluxo:**
        1.  Chama `firebase_admin_manager.get_all_plans()` para preencher o `QComboBox`.
        2.  Valida o e-mail e o plano.
        3.  Chama `firebase_admin_manager.create_license()` para salvar no Firestore.
        4.  Copia a chave gerada para a área de transferência.

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

5.  **Configurar Planos no Firestore:**

      * Vá ao Console do Firebase \> Firestore Database.
      * Crie a coleção `plans`.
      * Adicione documentos para cada plano (ex: ID `annual` com campos `name: "Plano Anual"` e `machine_limit: 1`).

6.  **Executar:**

      * `python admin_login.py`

-----

### 4\. Manutenção e Solução de Problemas

  * **"FileNotFoundError: admin\_service\_account.json"**

      * **Causa:** O arquivo `.json` da Conta de Serviço não está na pasta `admin_painel` ou está com o nome errado.
      * **Solução:** Siga o Passo 3.3.

  * **"Erro de configuração: Chave de API não encontrada"**

      * **Causa:** O arquivo `admin_api_config.json` não foi criado ou está com o nome errado.
      * **Solução:** Siga o Passo 3.3.

  * **"E-mail ou senha inválidos"**

      * **Causa 1:** O e-mail/senha digitados estão errados.
      * **Causa 2:** O usuário não foi cadastrado no **Firebase Authentication** (Passo 3.4).
      * **Causa 3:** O método de login "E-mail/senha" não está *ativado* no Firebase Authentication.

  * **"O campo 'Plano' está vazio ou com erro"**

      * **Causa:** A coleção `plans` está vazia ou não existe no Firestore.
      * **Solução:** Siga o Passo 3.5 e crie os documentos dos planos manualmente.

  * **Como adicionar um novo plano (ex: "Semestral")**

    1.  Vá ao Console do Firebase \> Firestore Database.
    2.  Na coleção `plans`, clique em "Adicionar documento".
    3.  ID do documento: `semestral`
    4.  Campos: `name` (string) = `Plano Semestral`, `machine_limit` (number) = `1`.
    5.  **Pronto.** Na próxima vez que você abrir o `DialogoNovaLicenca`, o "Plano Semestral" aparecerá automaticamente no menu.

  * **Como ver quais máquinas um cliente está usando?**

    1.  No `admin_dashboard.py`, procure a licença do cliente.
    2.  No Console do Firebase \> Firestore, vá para `licenses/{CHAVE_DO_CLIENTE}`.
    3.  Olhe o campo `active_devices`. Ele mostrará um mapa com os IDs e nomes das máquinas ativas. (Atualmente, o painel só mostra a *contagem* de dispositivos, mas o back-end está pronto para isso).

### 5\. Compilação (Distribuição para sua Equipe)

Quando você quiser criar um `.exe` do painel para sua equipe usar sem precisar instalar Python:

1.  Instale o PyInstaller: `pip install pyinstaller`
2.  Rode o comando de compilação (a partir da pasta `ABNTHelper`):

<!-- end list -->

```bash
pyinstaller --onefile --windowed --name "FormatheusAdmin" ^
 --icon="admin_painel/admin_assets/icons/formatheus_admin.ico" ^
 --add-data "admin_painel/admin_service_account.json;." ^
 --add-data "admin_painel/admin_api_config.json;." ^
 --add-data "admin_painel/admin_assets;admin_assets" ^
 admin_painel/admin_login.py
```

  * `--onefile`: Cria um único `.exe`.
  * `--windowed`: Remove o console (janela preta) ao executar.
  * `--icon`: Define o ícone do arquivo `.exe`.
  * `--add-data`: **Crucial.** Este comando copia seus arquivos `.json` e sua pasta de ícones *para dentro* do `.exe`, permitindo que o `resource_path` os encontre.

O arquivo `FormatheusAdmin.exe` (na pasta `dist`) é o seu painel. **Ele é tão secreto quanto suas senhas**, pois contém sua chave de serviço.