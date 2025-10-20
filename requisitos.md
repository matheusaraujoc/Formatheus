Coisas a fazer no programa:

1- Editar Referências -- feito

2- Tabelas -- feito

3- Mover os tópicos de lugar(para cima ou para baixo na aba de conteúdo) -- feito

4- Adicionar Imagens, inclusive em diferentes formatos(JPG, PNG, WEBP, etc) -- Feito

5- Sistema de prévias dentro do programa

6- Opção de mover tópicos de lugar, seja uma ferramenta onde o usuário ativa
e desativa, para evitar mover acidentalmente um tópico -- feito

7- Criar, salvar e carregar projetos. Por exemplo um usuário pode criar mais de um projeto
salvar eles e carregar os que tão salvos, inclusive podendo compartilhar o arquivo de salvamento
com outros usuários para eles carregarem o projeto na máquina deles. Vamos ver
a viabilidade de criarmos um formato nosso próprio de arquivo, esse formato de arquivo
vai armazenar dados e imagens dentro dele como se fosse uma pasta, semelhante ao que o PSD do photoshop faz.
Obs: o nome de extensão usado será o .abnf -- feito

8- Deve ter a possibilidade de adicionar um titulo ao projeto. -- pedente, estou pensando se implemento

8- O banco de tabelas e o banco de figuras deve ser "global" para o projeto, atualmente elas ficam separadas por tópico -- feito

9 - Adicionar o brasão da faculdade e/ou do estado na capa(mas primeiro conferir se as regras ABNT permite)

10- Tela inicial que irá mostrar os últimos projetos salvos, com os botões abrir, novo, carregar. E se o usuário clicar em um dos projetos
que aparece no painel ele irá direto para edição desse projeto. Semelhante ao photoshop e coreldrawn por exemplo. E nessa tela terá a opção do usuario
já iniciar o projeto com o modelo que ele quer, TCC, Tese, etc. Semelhante a tela de escolha de resoluções do photoshop.
obs: Deve ser criado um novo arquivo para essa funcionalidade

Texto reformulado: Agora vamos fazer uma tela inicial que irá mostrar os últimos projetos salvos, com os botões abrir, novo, carregar. E se o usuário clicar em um dos projetos

que aparece no painel ele irá direto para edição desse projeto. Semelhante ao photoshop e coreldrawn por exemplo. E nessa tela terá a opção do usuario

já iniciar o projeto com o modelo que ele quer, TCC, Tese, etc. Semelhante a tela de escolha de resoluções do photoshop. Quando o usuário salvar o projeto o programa irá armazenar o caminho que o projeto foi salvo assim ele pode abrir o projeto pela interface semelhante a que outros programas fazem, caso o usuário mude o projeto de caminho ou apague e tente abrir pela interface o programa vai avisar que o projeto não foi encontrado e ele irá sumir da tela inicial, semelhante ao que os programas profissionais fazem. -- Feito

obs: Deve ser criado um novo arquivo para essa funcionalidade

11- Sistema de backup automatico contra perda de dados e sistema de recuperação de arquivos semelhante ao do corel drawn -- Feito

12- Regra diferente de formatação para artigo cientifico -- Feito

13- Ferramenta de busca na aba de preview -- Feito

14- Quando for selecionado o modelo de artigo, as perguntas da tela inicial devem corresponder ao modelo e não ficar fixo no padrão de tcc, mestrado, doutorado

15- Ferramenta de busca na aba conteudo -- Feito

16- Ter a opção de colocar a aba de prévia aberta direto do lado direito do editor e que ela recarregue automatico a cada modificação do projeto -- Feito, precisa de alguns refinamentos mas está funcional

17- Filtrar imagens e tabelas por tópico nos bancos -- Feito

18- Prévia da imagem no editor de figuras -- Feito

19- Personalização de tipos de fonte e cores dos tópicos na exportação em doc

20- Exportação de PDF direta do programa

21- Impressão Direta do Programa

22- Opção de Voltar a tela inicial para entrar em outro projeto pela interface -- feito

23- Na tela inicial adicionar uma opção de criar projeto "guiado"(procurar um nome melhor), para o usuário fazer todas as configurações do projeto de forma muito intuitiva, para usuários leigos, o programa vai fazer perguntas referente ao projeto e o usuário vai responder. Exemplo: "Qual o nome do seu orientador?", "Qual instituição você estuda" e dê um exemplo de como responder. Semelhante a tela de configuração da cortana no windows, onde aparecem os textos com uma animação discreta e intuitiva que seja amigável para o usuário leigo.

24- Opção de adicionar brasão da instituição e do estado, com personalização lado direito, esquerdo ou superior -- feito parcialmente

Agora queremos que os brasões apareçam tanto da tela de preview quanto no documento final gerado em docx

25- Em formulas com números com pontos, o programa deve cobrir isso. (ex: 1.1)

26- Agora os brasões as vezes vem com imagens com fundo, ou o brasão é pequeno e area da imagem é grande, oque faz com que o brasão fique de tamanho diferente, um exemplo uma imagem com uma borda branca grande e outra com a borda pequena transparente, quando joga essa imagem na capa, mesmo que coloque do mesmo tamanho, elas ainda ficaram com tamanhos diferentes visualmente, pois a medida se aplica a borda também. Quero que quando o usuário selecionar uma imagem para colocar no brasão a parte de tratamento da imagem seja mais robusta, fazendo um recorte automatico de bordas excedentes da imagem e tirando o fundo se for possível. Eu pensei em uma solução utilizando as bibliotecas python rembg + pillow para fazer isso. Se a solução com rembg ficar muito pesada, ela pode ser repensada e retirada do projeto.

27- Unificar todas as regras de normas ABNT no arquivo normas_abnt.py, pois atualmente tem códigos com regras próprias e isso vai dificultar a manutenção

28- Criar um corretor de palavras erradas e concordância, mas ele não corrige nada automatico, ele não vai ser intrusivo. Ele vai sugerir pro usuário onde deve ser corrigido. Semelhante ao word.

Correções:

Quando cria a tabela e ela está sem nome, gera um erro da tabela não poder ser
salva sem nome e a caixa de edição da tabela fecha, isso não deve acontecer
a mensagem de erro deve aparecer e a caixa de edição da tabela deve continuar aberta
para evitar que o usuário perca o conteúdo que estava trabalhando. -- Corrigido

O distanciamento do inicio de paragrafo não está sendo respeitado, conforme as normas ABNT exigem. -- Corrigido

A formatação do arquivo em docx --  Corrgido

Sumario não está mostrando as referencias na previa --  Corrigido

Tabela final em docx não está centralizando os conteúdos das colunas apenas os titulos

Corrigir o tempo de criar o save, continua de minuto em minuto mesmo tendo mudado no gerenciador_config -- Feito

Criar um sistema com o latex usando a tecnica em html para adicionar as formulas latex semelhante ao sistema de figuras e tabelas

Problema de resolução, a parte da prévia está ficando cortada pois foi adicionado um novo campo de adição de formulas

Eu quero saber se as formulas criadas e processadas estão sendo salvas também no arquivo abnf e se as imagens do brasão também estão sendo salvas e se o arquivo de recuperação foi ajustado para as formulas e o brasão. Tudo do projeto deve ser salvo no arquivo abnf do projeto.

Ajustar os tamanhos de imagens para os 

Erro no auto save referente ao brasões: [00:48:52] TIMER PERIÓDICO DISPARADO! Executando auto-save...
ERRO CRÍTICO no auto-save: AttributeError("'Configuracoes' object has no attribute 'caminho_brasao_esquerdo'") -- Corrigido

Conferir o tamanho das formulas pequenas no arquivo, aparentemente estão com erro

Critico e urgente:

Não está sendo possível salvar o projeto abnf pois da um erro com os brasões
"Erro ao Salvar Não foi possível salvar o projeto:
O objeto 'Configurações' não possui o atributo 'caminho_brasao_esquerdo'" -- Corrigido

Possivel erro: Observar, o arquivo de recuperação parece não salvar as formulas, tabelas e imagens

ERRO DO PARAGRAFO PSSANDO DO LIMITE DA FOLHA -- Ainda não corrigido, corrigido a parte de quebra de linha, mas o limite interior continua com erro

Corrigir capa e contra capa doc