# Prompt para o Codex — Projeto Real com Aplicativo, Painel Administrativo e Drone Funcional

Copie todo o conteúdo abaixo e envie ao Codex com a pasta raiz do repositório aberta no VS Code.

---

Você está trabalhando no repositório do projeto acadêmico **Drone de Entregas via Coordenadas**.

O projeto não é apenas uma simulação. O objetivo final é demonstrar um fluxo funcional com:

- aplicativo Android real para o cliente;
- backend e banco de dados reais;
- painel administrativo separado;
- seleção real do ponto de entrega por coordenadas;
- aprovação humana do pedido;
- geração de missão compatível com Mission Planner e ArduPilot;
- envio da missão para a Pixhawk 6C;
- execução real do voo em ambiente controlado;
- telemetria real;
- entrega e retorno ao ponto de origem.

Em sua grande parte do projeto deve ser funcional e integrado.

Somente os seguintes elementos permanecerão simulados:

- catálogo de produtos, que utilizará dados acadêmicos de demonstração;
- pagamento, que será apenas registrado como escolha simulada e nunca processará dinheiro real.

Não produza apenas uma explicação. Crie, altere, configure, documente e teste os arquivos do repositório.

---

## 1. Protocolo obrigatório

Antes de modificar qualquer arquivo:

1. Leia integralmente `AGENTS_atualizado.md`.
2. Leia os documentos existentes em `docs/`.
3. Inspecione a estrutura atual do repositório.
4. Preserve arquivos e decisões úteis.
5. Identifique conflitos entre o escopo antigo e este novo escopo.
6. Atualize `AGENTS_atualizado.md`, `docs/ARCHITECTURE.md`, `docs/REQUIREMENTS.md` e os demais documentos para refletir:
   - painel administrativo separado;
   - hardware real;
   - Mission Planner;
   - Pixhawk 6C;
   - autorização humana;
   - execução real em ambiente controlado.
7. Não substitua o monólito modular por microsserviços.
8. Não adicione Redis, Celery, MQTT ou Kubernetes.
9. Use Python 3.13 no backend e no componente de integração.
10. Antes de implementar, apresente um plano curto por fases e prossiga sem pedir confirmação, salvo bloqueio técnico real.

> Não remova o ArduPilot SITL. Ele continua obrigatório para testes e regressão antes de executar no hardware real. Porém, o SITL não é o resultado final do projeto.

---

## 2. Fluxo real obrigatório

O sistema deve implementar este fluxo:

```text
Cliente abre o aplicativo Android
        ↓
Realiza login ou cadastro
        ↓
Seleciona produto de demonstração
        ↓
Seleciona o ponto exato de entrega no mapa
        ↓
Escolhe uma forma de pagamento simulada
        ↓
Confirma o pedido
        ↓
Pedido fica aguardando aprovação administrativa
        ↓
Administrador entra no painel separado
        ↓
Administrador analisa pedido, mapa e coordenadas
        ↓
Administrador aprova ou rejeita o pedido
        ↓
Backend cria uma missão em estado de preparação
        ↓
Missão é gerada em formato compatível com Mission Planner
        ↓
Administrador ou operador revisa a rota no Mission Planner
        ↓
Sistema consulta o estado real da Pixhawk e do drone
        ↓
Administrador realiza uma segunda autorização: autorizar voo
        ↓
Missão é enviada para a Pixhawk por MAVLink
        ↓
Drone executa a missão real
        ↓
Telemetria é enviada ao backend
        ↓
Cliente e administrador acompanham o voo
        ↓
Drone chega ao destino
        ↓
Entrega é confirmada ou mecanismo de carga é acionado
        ↓
Drone retorna ao ponto de origem
        ↓
Pedido e missão são concluídos
```

---

## 3. Regra de autorização em duas etapas

O sistema deve possuir duas aprovações distintas.

### 3.1 Aprovação do pedido

O administrador analisa:

- cliente;
- produto;
- localização;
- latitude;
- longitude;
- instruções;
- ponto no mapa;
- distância estimada;
- status do sistema;
- observações.

Ações:

- aprovar pedido;
- rejeitar pedido;
- informar motivo da rejeição.

A aprovação do pedido permite preparar a missão, mas não permite iniciar o voo.

### 3.2 Autorização do voo

Depois que a missão for criada e revisada, o administrador ou operador deve autorizar explicitamente o envio e a execução.

Antes dessa autorização, o sistema deve exibir:

- conexão com a Pixhawk;
- heartbeat;
- modo de voo;
- estado de armamento;
- GPS;
- quantidade de satélites;
- estado do EKF;
- tensão ou percentual de bateria;
- origem;
- destino;
- distância estimada;
- altitude configurada;
- status da missão;
- resultado das verificações pré-voo;
- confirmação de que a área está controlada.

A autorização do pedido e a autorização do voo não podem ser o mesmo botão ou o mesmo endpoint.

---

## 4. Arquitetura obrigatória

```text
Aplicativo Flutter do cliente
        ↓ REST / WebSocket
Backend FastAPI
        ↓
PostgreSQL + PostGIS
        ↑
Painel administrativo React
        ↓
Serviço de missões
        ↓
Drone Gateway / Mission Control
        ↓
Mission Planner + MAVLink
        ↓
Pixhawk 6C + ArduPilot
        ↓
Drone real
```

### Responsabilidades

#### Aplicativo Flutter

- cadastro;
- login;
- produtos de demonstração;
- carrinho;
- mapa;
- seleção do ponto;
- pagamento simulado;
- pedido;
- acompanhamento;
- visualização dos estados.

#### Painel administrativo

- autenticação administrativa;
- fila de pedidos;
- mapa e coordenadas;
- aprovação e rejeição;
- preparação da missão;
- visualização da missão;
- download ou exportação da missão;
- estado real do drone;
- checklist;
- autorização do voo;
- acompanhamento da telemetria;
- comando administrativo de abortamento ou RTL, respeitando as regras de segurança;
- histórico de eventos.

#### Backend

- autenticação;
- autorização por função;
- produtos;
- pedidos;
- pontos;
- regras;
- estados;
- missões;
- aprovações;
- auditoria;
- telemetria;
- comunicação com mobile, admin e gateway.

#### Drone Gateway / Mission Control

- comunicação local com o backend;
- comunicação MAVLink;
- conexão com SITL e Pixhawk;
- leitura do estado do veículo;
- upload da missão;
- confirmação do upload;
- execução após autorização válida;
- telemetria;
- eventos;
- tratamento de falhas;
- RTL e abortamento controlado.

#### Mission Planner

- revisão visual da rota;
- monitoramento;
- configuração da Pixhawk;
- calibração;
- verificação de mensagens;
- análise de logs;
- acompanhamento da missão real.

---

## 5. Stack tecnológica

### Mobile

- Flutter;
- Dart;
- Android.

### Painel administrativo

- React;
- TypeScript;
- Vite;
- React Router;
- cliente HTTP;
- WebSocket;
- biblioteca de mapas compatível com o provedor escolhido.

### Backend

- Python 3.13;
- FastAPI;
- Pydantic v2;
- SQLAlchemy 2.x;
- Alembic;
- PostgreSQL;
- PostGIS;
- Pytest;
- Ruff.

### Integração

- Python 3.13;
- `pymavlink`;
- ArduPilot;
- ArduPilot SITL;
- Mission Planner;
- Pixhawk 6C;
- rádio de telemetria ou conexão configurada.

### Infraestrutura

- Docker;
- Docker Compose;
- Git;
- GitHub;
- scripts PowerShell;
- WSL 2 para SITL, quando necessário.

---

## 6. Estrutura do repositório

Crie ou ajuste:

```text
drone-delivery/
├── AGENTS_atualizado.md
├── README.md
├── .editorconfig
├── .env.example
├── .gitignore
├── compose.yaml
├── Makefile
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── REQUIREMENTS.md
│   ├── BUSINESS_RULES.md
│   ├── APPLICATIONS.md
│   ├── API.md
│   ├── DATABASE.md
│   ├── DESIGN_SYSTEM.md
│   ├── LOCATION_SELECTION.md
│   ├── MAPS_INTEGRATION.md
│   ├── ADMIN_FLOW.md
│   ├── MISSION_PLANNER_INTEGRATION.md
│   ├── DRONE_PROTOCOL.md
│   ├── HARDWARE.md
│   ├── SECURITY.md
│   ├── PREFLIGHT_CHECKLIST.md
│   ├── TEST_PLAN.md
│   ├── DEVELOPMENT.md
│   ├── DEMO_PLAN.md
│   ├── design_reference/
│   │   ├── README.md
│   │   ├── home.png
│   │   ├── pagamento.png
│   │   ├── detalhes-compra.png
│   │   └── tela-login.png
│   └── adr/
│       ├── README.md
│       ├── 0001-monolito-modular.md
│       ├── 0002-postgresql-postgis.md
│       ├── 0003-drone-gateway-separado.md
│       ├── 0004-sitl-antes-do-hardware.md
│       ├── 0005-painel-admin-separado.md
│       └── 0006-autorizacao-em-duas-etapas.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── database/
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── users/
│   │   │   ├── admins/
│   │   │   ├── products/
│   │   │   ├── delivery_points/
│   │   │   ├── orders/
│   │   │   ├── approvals/
│   │   │   ├── missions/
│   │   │   ├── vehicles/
│   │   │   ├── telemetry/
│   │   │   └── system_events/
│   │   └── main.py
│   ├── migrations/
│   ├── scripts/
│   ├── tests/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── README.md
│
├── drone_gateway/
│   ├── app/
│   │   ├── clients/
│   │   ├── core/
│   │   ├── mavlink/
│   │   ├── mission_planner/
│   │   ├── missions/
│   │   ├── safety/
│   │   ├── telemetry/
│   │   └── main.py
│   ├── tests/
│   ├── pyproject.toml
│   └── README.md
│
├── mobile/
│   ├── android/
│   ├── assets/
│   │   ├── fonts/
│   │   ├── icons/
│   │   ├── images/
│   │   └── logos/
│   ├── lib/
│   │   ├── app/
│   │   ├── core/
│   │   ├── design_system/
│   │   │   ├── tokens/
│   │   │   ├── theme/
│   │   │   ├── components/
│   │   │   └── design_catalog/
│   │   ├── features/
│   │   ├── shared/
│   │   └── main.dart
│   ├── test/
│   │   ├── design_system/
│   │   ├── features/
│   │   └── golden/
│   ├── pubspec.yaml
│   └── README.md
│
├── admin_web/
│   ├── src/
│   │   ├── app/
│   │   ├── design-system/
│   │   │   ├── tokens/
│   │   │   ├── theme/
│   │   │   ├── components/
│   │   │   └── catalog/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── dashboard/
│   │   │   ├── orders/
│   │   │   ├── approvals/
│   │   │   ├── missions/
│   │   │   ├── vehicles/
│   │   │   └── telemetry/
│   │   ├── services/
│   │   ├── routes/
│   │   └── main.tsx
│   ├── public/
│   ├── tests/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── README.md
│
├── infrastructure/
│   ├── docker/
│   └── postgres/
│
└── scripts/
    ├── bootstrap.ps1
    ├── start_backend.ps1
    ├── start_admin.ps1
    ├── start_mobile.ps1
    ├── start_gateway.ps1
    ├── start_sitl.sh
    ├── test_all.ps1
    └── seed_demo.ps1
```

Não crie arquivos vazios apenas para representar a estrutura.

---

## 7. Documentação obrigatória

Atualize ou crie documentos coerentes.

### `README.md`

Inclua:

- objetivo;
- partes reais e simuladas;
- fluxo completo;
- stack;
- estrutura;
- pré-requisitos;
- instalação;
- execução;
- testes;
- hardware;
- aviso de segurança;
- links.

### `docs/ARCHITECTURE.md`

Inclua:

- aplicativo do cliente;
- painel administrativo;
- backend;
- banco;
- Mission Planner;
- gateway;
- Pixhawk;
- drone;
- autorização em duas etapas;
- fluxos;
- estados;
- segurança;
- falhas;
- ambientes;
- hardware real.

### `docs/REQUIREMENTS.md`

Inclua requisitos funcionais e não funcionais para:

- cliente;
- administrador;
- aprovação;
- missão;
- hardware;
- telemetria;
- segurança;
- retorno;
- auditoria.

Adicione critérios de aceite e rastreabilidade.

### `docs/DESIGN_SYSTEM.md`

Antes de criar as telas finais, analise as imagens de referência fornecidas:

- `home.png`;
- `pagamento.png`;
- `detalhes compra.png` ou `detalhes-compra.png`;
- `Tela de login.png` ou `tela-login.png`.

Se os arquivos estiverem disponíveis no repositório ou anexados ao ambiente, copie-os para `docs/design_reference/` com nomes padronizados. Se não estiverem acessíveis, não invente uma identidade visual definitiva: prepare a estrutura do design system e registre a ausência das referências.

O documento deve registrar:

- análise visual de cada tela;
- identidade da marca;
- paleta semântica;
- tipografia;
- escala de espaçamento;
- raios de borda;
- sombras;
- tamanhos de ícones;
- estados de interação;
- componentes reutilizáveis;
- regras de composição;
- responsividade;
- acessibilidade;
- equivalência entre componentes Flutter e React;
- regras para adicionar novos componentes;
- exemplos de uso;
- inventário de assets;
- diferenças permitidas entre aplicativo do cliente e painel administrativo;
- checklist de revisão visual.

O documento deve ser fonte de verdade do design. Nenhuma tela nova deve criar cores, tamanhos, sombras ou estilos isolados sem primeiro verificar os tokens e componentes existentes.

### `docs/LOCATION_SELECTION.md`

Documente detalhadamente o fluxo em duas etapas para escolha da localização:

1. localização aproximada;
2. seleção do ponto exato;
3. confirmação e validação;
4. armazenamento das coordenadas finais;
5. visualização administrativa;
6. comportamento em falhas de permissão, GPS e pesquisa;
7. critérios de aceite;
8. testes;
9. regras de acessibilidade e usabilidade.

O documento deve explicar que o endereço pesquisado é apenas uma referência para centralizar o mapa. A latitude e a longitude finais são definidas somente depois que o cliente posiciona manualmente o marcador no ponto exato de entrega.

### `docs/MAPS_INTEGRATION.md`

Documente:

- Google Maps como provedor principal;
- configuração do mapa no Flutter;
- modo de visualização por satélite;
- permissão de localização;
- localização aproximada do dispositivo;
- barra de pesquisa de endereço;
- autocomplete de endereços;
- geocodificação;
- geocodificação reversa;
- marcador arrastável;
- movimentação e zoom da câmera;
- restrições e proteção das chaves;
- tratamento de limites, erros e indisponibilidade;
- validação no backend;
- política de logs sem expor dados desnecessários;
- alternativa de desenvolvimento quando a API não estiver configurada.

### `docs/ADMIN_FLOW.md`

Documente:

- login administrativo;
- fila;
- análise;
- aprovação;
- rejeição;
- revisão da missão;
- autorização do voo;
- acompanhamento;
- abortamento;
- auditoria.

### `docs/MISSION_PLANNER_INTEGRATION.md`

Documente:

- como a missão é criada;
- formato de exportação;
- arquivo compatível com Mission Planner;
- revisão;
- upload;
- telemetria;
- limites da automação da interface;
- integração por MAVLink;
- procedimento real.

### `docs/HARDWARE.md`

Documente os componentes reais:

- Pixhawk 6C;
- ArduPilot;
- GPS;
- telemetria;
- ESCs;
- motores;
- bateria;
- receptor e rádio;
- mecanismo de entrega;
- conexões;
- limitações;
- checklist de bancada.

Não invente pinagens ou parâmetros não confirmados.

### `docs/PREFLIGHT_CHECKLIST.md`

Crie checklist real para:

- estrutura;
- hélices;
- bateria;
- GPS;
- EKF;
- bússola;
- telemetria;
- geofence;
- RTL;
- área;
- carga;
- autorização;
- abortamento.

### `docs/DEMO_PLAN.md`

A demonstração principal deve incluir o drone real.

SITL e vídeo ficam como contingência.

---

## 7A. Design System baseado nas imagens de referência

As quatro imagens fornecidas são referências obrigatórias para o aplicativo do cliente. Elas não devem ser inseridas como telas estáticas nem usadas como imagem de fundo para simular a interface. Reconstrua a interface com widgets e componentes reais.

### 7A.1 Análise visual obrigatória

Registre em `docs/DESIGN_SYSTEM.md` esta leitura inicial e refine-a após medir as imagens:

#### Identidade geral
- Interface limpa, leve e comercial.
- Fundo branco ou cinza muito claro.
- Azul como cor principal para navegação, ações e seleção.
- Laranja como cor de destaque para promoções e ação de compra.
- Azul-grafite para títulos e textos importantes.
- Cinza azulado para textos secundários, ícones e bordas.
- Verde para sucesso, verificação e valores positivos.
- Amarelo/dourado para avaliações, ofertas e indicadores.
- Cartões brancos com borda fina, raio médio e sombra discreta.
- Espaçamento generoso e hierarquia visual clara.
- Ícones simples, arredondados e consistentes.

#### Tela de login
- Logotipo centralizado na parte superior.
- Formulários largos com ícone, rótulo e dica.
- Botão primário azul ocupando grande parte da largura.
- Ações secundárias discretas.
- Muito espaço em branco.
- Layout vertical centralizado e de baixa densidade.

#### Tela inicial
- Banner promocional grande e arredondado.
- Grade de categorias/produtos em duas colunas.
- Cartões com imagem destacada e título na parte inferior.
- Navegação inferior com três ações principais.
- Azul ativo e cinza inativo.
- Laranja reservado ao conteúdo promocional.

#### Detalhes do produto
- Imagem hero no topo.
- Título, avaliação, preço e informações principais em blocos.
- Linhas de informação com ícone reutilizável.
- Seções separadas por divisores discretos.
- Avaliações com estrelas e barras de progresso.
- Conteúdo rolável e hierarquia tipográfica forte.

#### Pagamento
- Barra superior com voltar e título.
- Métodos de pagamento em cartões selecionáveis.
- Indicador visual de seleção.
- Campos agrupados.
- Resumo financeiro em cartão.
- Botão de confirmação laranja em largura total.
- Como o pagamento é simulado, não colete nem persista dados reais de cartão.

### 7A.2 Tokens visuais iniciais

Crie tokens, sem espalhar valores literais pelas telas. Os valores abaixo são referências iniciais e podem ser refinados após amostragem das imagens:

```text
brand.blue.primary       ≈ #3478D4
brand.blue.dark          ≈ #243247
brand.orange.primary     ≈ #FF7A00
brand.orange.dark        ≈ #F05A00
surface.background       ≈ #FAFAFC
surface.card             ≈ #FFFFFF
surface.subtle           ≈ #F3F6FB
text.primary             ≈ #2D384C
text.secondary           ≈ #737E94
border.default           ≈ #E2E6EE
state.success            ≈ #2FAF88
state.warning            ≈ #FFC028
state.error              ≈ #D64545
state.info               ≈ #3478D4
```

Regras:

- Confirme contraste antes de fechar a paleta.
- Defina variantes `hover`, `pressed`, `disabled`, `focus` e `selected`.
- Não use laranja para toda ação. Azul é o primário geral; laranja é destaque comercial e confirmação contextual.
- No painel administrativo, reserve vermelho para abortamento, falha e ações destrutivas.
- Use verde somente para estados realmente positivos.
- Não codifique cor de status diretamente em telas; utilize um mapeamento semântico central.

### 7A.3 Tipografia

A tipografia deve seguir uma família sans-serif geométrica e arredondada semelhante à referência. Utilize uma família licenciada e empacotada no projeto, preferencialmente `Poppins`, ou outra aprovada no documento.

Defina tokens para:

```text
display
headlineLarge
headlineMedium
titleLarge
titleMedium
bodyLarge
bodyMedium
bodySmall
labelLarge
labelMedium
caption
priceLarge
```

Regras:

- Evite tamanhos literais espalhados.
- Textos devem suportar escala do sistema.
- Valores monetários e estados importantes devem possuir estilos próprios.
- Não transforme todo texto em negrito.
- Preserve legibilidade em telas pequenas.

### 7A.4 Espaçamento, bordas e sombras

Adote escala consistente, por exemplo:

```text
space.1 = 4
space.2 = 8
space.3 = 12
space.4 = 16
space.5 = 20
space.6 = 24
space.8 = 32
space.10 = 40
space.12 = 48
```

Raios sugeridos:

```text
radius.small  = 8
radius.medium = 12
radius.large  = 16
radius.xlarge = 24
radius.pill   = 999
```

Crie níveis de sombra reutilizáveis:

```text
shadow.none
shadow.subtle
shadow.card
shadow.overlay
```

Não crie variações quase idênticas para cada tela.

### 7A.5 Componentes reutilizáveis do Flutter

Crie componentes reutilizáveis, com APIs simples e composição em vez de cópia. Inclua, quando realmente usados:

```text
AppScaffold
AppTopBar
AppBottomNavigation
AppLogo
AppSectionTitle
PrimaryButton
AccentButton
SecondaryButton
DangerButton
IconActionButton
AppTextField
AppPasswordField
SearchField
FormFieldContainer
AppCard
SelectableCard
ProductCard
CategoryCard
PromotionBanner
ProductHero
InfoRow
RatingStars
RatingSummary
RatingDistributionBar
ReviewTile
PriceText
PriceSummaryCard
PaymentMethodTile
SelectionIndicator
StatusChip
MissionStatusTimeline
OrderStatusCard
TelemetrySummaryCard
MapSelectionCard
EmptyState
ErrorState
LoadingState
AppDivider
ConfirmationDialog
DestructiveConfirmationDialog
```

Não crie todos cegamente. Crie os componentes quando houver uso real, mas reutilize-os em todas as telas equivalentes.

### 7A.6 Componentes reutilizáveis do painel React

O painel administrativo deve usar a mesma identidade visual, mas com maior densidade e foco operacional.

Crie componentes reutilizáveis equivalentes:

```text
AppShell
AdminSidebar
AdminTopBar
PageHeader
SectionHeader
Button
IconButton
TextField
PasswordField
Select
Checkbox
Radio
Card
StatCard
StatusBadge
AlertBanner
DataTable
FilterBar
Pagination
Modal
ConfirmDialog
DangerConfirmDialog
Tabs
Timeline
MapPanel
OrderSummaryCard
MissionSummaryCard
VehicleHealthCard
TelemetryCard
PreflightChecklist
ApprovalPanel
FlightAuthorizationPanel
EmptyState
ErrorState
LoadingState
Toast
```

Regras:

- Componentes genéricos ficam em `admin_web/src/design-system/components`.
- Componentes ligados a um domínio específico ficam dentro da feature correspondente.
- Não duplique componentes genéricos em features.
- Use propriedades e composição, não componentes gigantes com dezenas de condições.
- Não use classes CSS globais sem padrão.
- Centralize tokens em CSS variables ou TypeScript e documente a escolha.

### 7A.7 Classes e tokens obrigatórios no Flutter

Implemente classes centrais semelhantes a:

```dart
AppColors
AppTypography
AppSpacing
AppRadii
AppShadows
AppIconSizes
AppDurations
AppBreakpoints
AppTheme
```

Não use diretamente nas telas:

```dart
Color(0xFF...)
EdgeInsets.all(...)
BorderRadius.circular(...)
TextStyle(...)
BoxShadow(...)
Duration(milliseconds: ...)
```

quando o valor representar um padrão do sistema. Use tokens ou componentes.

Exceções específicas devem ser raras, justificadas e documentadas.

### 7A.8 Reutilização entre telas

Antes de criar uma tela, o Codex deve:

1. identificar padrões já presentes;
2. verificar o catálogo de componentes;
3. reutilizar componentes existentes;
4. ampliar um componente por composição quando necessário;
5. criar novo componente somente quando houver responsabilidade visual clara;
6. adicionar o novo componente ao `DESIGN_SYSTEM.md`;
7. incluir testes ou exemplos;
8. evitar abstração prematura de elementos usados uma única vez.

O objetivo não é alcançar “100% de classes”, mas eliminar duplicação real e manter uma linguagem visual consistente.

### 7A.9 Catálogo de componentes

Crie um catálogo apenas para desenvolvimento:

#### Flutter
- Tela `DesignCatalogScreen`.
- Disponível somente em modo de desenvolvimento.
- Demonstre tokens, botões, campos, cartões, estados, avaliações, status, loading e erros.

#### React
- Rota de desenvolvimento `/design-system` ou catálogo isolado.
- Não deve ficar acessível sem proteção em build de demonstração/produção.
- Demonstre os mesmos tokens e componentes.

### 7A.10 Assets

- Utilize o logotipo fornecido pelo usuário.
- Não redesenhe o logotipo sem solicitação.
- Não misture bibliotecas de ícones com estilos visuais incompatíveis.
- Centralize caminhos de assets.
- Imagens de produto são dados de demonstração.
- Comprima assets sem perda visual relevante.
- Adicione texto alternativo no painel web.
- No Flutter, use `semanticLabel` quando aplicável.

### 7A.11 Responsividade e acessibilidade

- O aplicativo deve funcionar em larguras comuns de Android.
- O painel deve funcionar em desktop e tablet.
- Defina breakpoints reutilizáveis.
- Alvos de toque devem possuir tamanho adequado.
- Não dependa apenas de cor para estado.
- Campos devem ter rótulo, erro e foco visível.
- Suporte textos maiores sem sobreposição.
- Teste contraste.
- Não fixe alturas de texto que cortem conteúdo.

### 7A.12 Fidelidade às referências

- Preserve identidade, hierarquia e composição.
- Não copie erros ortográficos presentes nas imagens.
- Não invente avaliações, lojas ou promoções como regras reais do sistema.
- Os textos e produtos são dados de demonstração.
- A tela de pagamento deve deixar claro que é uma simulação.
- Não armazene número, validade, CVV ou nome real de cartão.
- Use os screenshots como referência visual, não como especificação de segurança ou regra de negócio.

### 7A.13 Validação visual

Inclua:

- testes de widget/componentes;
- golden tests Flutter para telas e componentes estáveis;
- testes de snapshot apenas quando agregarem valor no React;
- comparação manual com as referências;
- checklist no `DESIGN_SYSTEM.md`;
- captura das telas finais para documentação.

Nenhum golden test deve ser atualizado automaticamente apenas para esconder regressão.

---

## 7B. Seleção da localização exata no mapa

A escolha da localização deve reproduzir uma experiência semelhante à Uber, mas adaptada para entrega por drone.

O cliente não deve apenas digitar um endereço e aceitar automaticamente a coordenada retornada. O endereço serve para encontrar a região aproximada. O ponto final da entrega deve ser escolhido manualmente pelo cliente.

### 7B.1 Provedor e modo visual

Utilize a API do Google Maps como provedor principal.

A tela de seleção deve abrir, por padrão, em:

```text
MapType.satellite
```

ou configuração equivalente do SDK utilizado.

Regras:

- mostrar imagem de satélite desde a etapa de ajuste fino;
- permitir zoom e movimentação do mapa;
- permitir alternar temporariamente para modo híbrido apenas se isso ajudar a exibir nomes de ruas, mas o modo padrão final deve ser satélite;
- não utilizar mapa terrestre como única visualização para confirmar o ponto;
- manter controles essenciais legíveis sobre o mapa;
- respeitar os termos e atribuições do provedor.

### 7B.2 Fluxo em duas etapas

#### Etapa 1 — Encontrar a região aproximada

Ao abrir a tela:

1. Solicitar permissão de localização do dispositivo.
2. Se a permissão for concedida:
   - obter a localização aproximada atual;
   - centralizar o mapa nessa região;
   - não confirmar automaticamente esse ponto como destino;
   - mostrar aviso de que a posição inicial é apenas aproximada.
3. Se a permissão for negada:
   - manter a tela funcional;
   - abrir a pesquisa de endereço;
   - explicar que o cliente ainda pode informar outro local manualmente.
4. Mostrar uma barra de pesquisa fixa no topo.
5. A barra deve aceitar:
   - rua;
   - número;
   - bairro;
   - cidade;
   - CEP;
   - nome de lugar reconhecido pelo provedor.
6. Utilizar autocomplete de endereços.
7. Quando o cliente selecionar ou confirmar um resultado:
   - converter o endereço em coordenadas aproximadas;
   - centralizar a câmera nessa região;
   - avançar para a segunda etapa.

O cliente pode pesquisar um endereço distante da posição atual. Não limite a pesquisa à localização do dispositivo. A área de atendimento será validada separadamente pelo backend.

#### Etapa 2 — Escolher o ponto exato

Depois da confirmação do endereço ou uso da localização atual:

1. Exibir o mapa em visão de satélite.
2. Exibir um pequeno marcador visual no formato de seta ou pin.
3. O marcador deve poder ser arrastado manualmente.
4. O cliente pode:
   - arrastar o marcador;
   - mover o mapa;
   - aproximar;
   - afastar;
   - reposicionar a câmera.
5. Enquanto o marcador estiver sendo movido:
   - atualizar latitude e longitude em memória;
   - não salvar definitivamente ainda;
   - mostrar estado visual de seleção.
6. Ao soltar o marcador:
   - obter as coordenadas exatas;
   - executar geocodificação reversa apenas para exibir uma referência textual;
   - mostrar latitude e longitude com precisão suficiente;
   - atualizar o resumo do ponto.
7. O marcador final deve representar o local onde o pacote será entregue, não o centro do endereço pesquisado.
8. Exibir uma área de precisão ou círculo visual configurável ao redor do marcador.
9. Mostrar instrução clara:

```text
Arraste o marcador até o ponto exato onde o pacote deverá ser entregue.
Escolha uma área aberta, segura e livre de árvores, fios, coberturas,
animais e pessoas não envolvidas na operação.
```

10. O cliente deve pressionar `Confirmar ponto de entrega`.
11. Antes da confirmação final, abrir um resumo contendo:
    - mapa em satélite;
    - marcador;
    - endereço de referência;
    - latitude;
    - longitude;
    - instruções;
    - confirmação de segurança.
12. Somente depois dessa confirmação o ponto pode ser vinculado ao pedido.

### 7B.3 Experiência semelhante à Uber

A interface deve seguir este comportamento:

```text
Mapa aberto
    ↓
Localização aproximada atual ou pesquisa de endereço
    ↓
Mapa centraliza na região
    ↓
Cliente confirma a região
    ↓
Modo de ajuste fino em satélite
    ↓
Cliente arrasta o pequeno marcador/seta
    ↓
Coordenadas são atualizadas
    ↓
Cliente confirma o ponto exato
```

A implementação deve possuir indicador de etapas:

```text
1. Encontrar região
2. Ajustar ponto exato
```

Não misture as duas etapas em uma única confirmação silenciosa.

### 7B.4 Componentes Flutter reutilizáveis

Crie componentes reutilizáveis para esse fluxo:

```text
LocationSearchBar
AddressAutocompleteList
MapLoadingOverlay
MapErrorState
LocationPermissionCard
ApproximateLocationNotice
SatelliteMapView
DraggableDeliveryMarker
DeliveryAccuracyCircle
MapCrosshair
MapZoomControls
CurrentLocationButton
DeliveryPointSummaryCard
CoordinatesDisplay
DeliveryInstructionsField
DeliverySafetyChecklist
LocationStepIndicator
ConfirmDeliveryPointButton
LocationConfirmationSheet
```

Regras:

- componentes genéricos do mapa ficam no design system ou `shared`;
- regras do ponto de entrega ficam na feature `delivery_point`;
- não coloque chamadas diretas à API dentro de widgets visuais;
- utilize controller/service/repository para localização, Places e geocodificação;
- mantenha estados de carregamento, erro, permissão negada e sem resultado;
- evite um único widget gigante para toda a tela.

### 7B.5 Organização sugerida no Flutter

```text
mobile/lib/features/delivery_point/
├── data/
│   ├── datasources/
│   ├── models/
│   └── repositories/
├── domain/
│   ├── entities/
│   ├── repositories/
│   └── use_cases/
├── presentation/
│   ├── controllers/
│   ├── screens/
│   ├── states/
│   └── widgets/
└── delivery_point_feature.dart
```

Crie abstrações como:

```text
LocationService
PlacesSearchService
GeocodingService
MapCameraController
DeliveryPointRepository
```

Não permita que a tela dependa diretamente da implementação concreta do Google Maps.

### 7B.6 Dados que devem ser armazenados

O ponto deve guardar, no mínimo:

```text
id
user_id
searched_address
address_reference
selection_source
approximate_latitude
approximate_longitude
final_latitude
final_longitude
location
instructions
user_confirmed_safe_area
map_provider
map_type
accuracy_meters
created_at
updated_at
```

Valores recomendados para `selection_source`:

```text
CURRENT_LOCATION
ADDRESS_SEARCH
SAVED_POINT
MANUAL_MAP_SELECTION
```

Regras:

- `final_latitude` e `final_longitude` são a referência real da missão;
- `approximate_latitude` e `approximate_longitude` servem apenas para rastreabilidade;
- `searched_address` não substitui coordenadas;
- o tipo PostGIS deve ser criado a partir das coordenadas finais;
- não reutilizar automaticamente um ponto antigo sem nova confirmação;
- o backend deve validar as faixas de latitude e longitude.

### 7B.7 Validações do backend

Ao receber o ponto final:

1. validar latitude entre `-90` e `90`;
2. validar longitude entre `-180` e `180`;
3. validar se o cliente confirmou o ponto;
4. validar se a seleção passou pela segunda etapa;
5. validar área de atendimento;
6. calcular distância entre origem e destino;
7. rejeitar pontos acima da distância máxima configurada;
8. rejeitar coordenadas inexistentes ou incompletas;
9. registrar endereço apenas como referência;
10. armazenar o ponto PostGIS final;
11. retornar uma resposta clara quando o local não puder ser atendido.

A validação administrativa deve mostrar:

- posição inicial aproximada;
- endereço pesquisado;
- ponto final escolhido;
- distância entre endereço aproximado e ponto final;
- distância entre a base e o destino;
- mapa em visão de satélite;
- instruções;
- resultado das validações.

### 7B.8 Painel administrativo

No detalhe do pedido, mostre:

- mapa em satélite;
- marcador do ponto final;
- marcador opcional do endereço aproximado;
- marcador da base;
- linha simples entre base e destino apenas como referência visual;
- latitude e longitude finais;
- endereço pesquisado;
- instruções;
- distância;
- indicação de que o ponto foi escolhido manualmente;
- confirmação de segurança do cliente.

O administrador não deve alterar silenciosamente o ponto do cliente.

Se o administrador considerar o local inadequado:

- rejeitar o pedido com motivo; ou
- solicitar que o cliente selecione um novo ponto.

Uma alteração administrativa de coordenadas, caso seja implementada futuramente, exige auditoria, justificativa e nova confirmação.

### 7B.9 Segurança das chaves e APIs

- Não grave chave da API diretamente no código Dart.
- Configure chaves pelos mecanismos próprios da plataforma Android.
- Restrinja a chave ao pacote Android e às APIs necessárias.
- Não exponha chaves administrativas ou de servidor no aplicativo.
- Use variáveis de ambiente para serviços executados no backend.
- Não registre a chave nos logs.
- Não versione arquivos locais contendo segredos.
- Documente a configuração em `docs/MAPS_INTEGRATION.md`.

### 7B.10 Comportamentos de falha

Trate:

- permissão negada;
- localização desativada;
- GPS sem resposta;
- ausência de internet;
- nenhum resultado de pesquisa;
- erro de geocodificação;
- limite da API;
- mapa não carregado;
- marcador fora da área permitida;
- coordenadas inválidas;
- falha ao salvar;
- sessão expirada.

A tela deve permitir nova tentativa sem perder desnecessariamente os dados do pedido.

### 7B.11 Critérios de aceite

O fluxo será aceito quando:

1. o mapa abrir na região aproximada do cliente, quando permitido;
2. a pesquisa aceitar um endereço distante;
3. a confirmação do endereço centralizar o mapa;
4. a segunda etapa abrir em satélite;
5. o marcador puder ser reposicionado;
6. latitude e longitude mudarem conforme o marcador;
7. o endereço textual não substituir o ponto final;
8. o cliente confirmar explicitamente o ponto;
9. o backend armazenar as coordenadas finais;
10. o administrador visualizar o ponto final;
11. o pedido utilizar essas coordenadas para preparar a missão;
12. erros e permissões negadas forem tratados.

### 7B.12 Testes

Adicione testes para:

#### Flutter
- permissão concedida;
- permissão negada;
- pesquisa de endereço;
- endereço sem resultado;
- mudança da etapa 1 para a etapa 2;
- mapa em satélite;
- movimento do marcador;
- atualização de coordenadas;
- confirmação;
- bloqueio sem confirmação;
- erro da API;
- restauração do estado.

#### Backend
- faixas válidas;
- faixas inválidas;
- ausência de coordenadas finais;
- seleção sem segunda etapa;
- ponto dentro da cobertura;
- ponto fora da cobertura;
- cálculo de distância;
- propriedade do usuário;
- persistência PostGIS.

#### Admin
- exibição do ponto;
- diferença entre endereço aproximado e ponto final;
- rejeição por local inadequado;
- solicitação de novo ponto;
- impossibilidade de edição silenciosa.

## 8. Modelo de acesso e usuários

Adicione funções:

```text
CUSTOMER
ADMIN
```

Regras:

- cliente acessa apenas seus pedidos;
- administrador acessa todos os pedidos;
- somente administrador aprova ou rejeita;
- somente administrador prepara missão;
- somente administrador autorizado pode autorizar voo;
- ações administrativas devem gerar auditoria;
- o primeiro administrador deve ser criado por seed controlado ou comando CLI;
- não permita cadastro público como administrador.

---

## 9. Estados do pedido

Utilize estados claros:

```text
DRAFT
PENDING_ADMIN_APPROVAL
APPROVED
REJECTED
MISSION_PREPARING
MISSION_READY
WAITING_FLIGHT_AUTHORIZATION
MISSION_UPLOADING
IN_TRANSIT
AT_DESTINATION
DELIVERED
RETURNING
COMPLETED
CANCELLED
FAILED
```

Regras:

- pedido novo confirmado pelo cliente entra em `PENDING_ADMIN_APPROVAL`;
- somente administrador pode mudar para `APPROVED` ou `REJECTED`;
- `REJECTED` exige motivo;
- missão só pode ser criada para pedido `APPROVED`;
- aprovação do pedido não inicia o voo;
- voo só inicia após `WAITING_FLIGHT_AUTHORIZATION`;
- somente autorização administrativa explícita permite upload e execução;
- estados terminais não podem ser alterados sem procedimento registrado.

---

## 10. Estados da missão

```text
DRAFT
PENDING_VALIDATION
GENERATED
EXPORTED_TO_MISSION_PLANNER
UNDER_REVIEW
READY_FOR_AUTHORIZATION
AUTHORIZED
UPLOADING
UPLOADED
EXECUTING
DESTINATION_REACHED
DELIVERY_CONFIRMED
RETURNING
COMPLETED
ABORTED
FAILED
```

Regras:

- missão pertence a um pedido aprovado;
- uma missão ativa por pedido;
- `GENERATED` significa que waypoints foram criados;
- `EXPORTED_TO_MISSION_PLANNER` significa que existe arquivo compatível ou transferência preparada;
- `UNDER_REVIEW` aguarda conferência;
- `READY_FOR_AUTHORIZATION` exige verificações válidas;
- `AUTHORIZED` exige administrador autenticado e auditoria;
- autorização deve possuir prazo curto ou uso único;
- upload deve ser idempotente;
- missão executada não pode ser reenviada;
- telemetria real controla os estados após início.

---

## 11. Banco de dados

Inclua:

### User
- id;
- role;
- name;
- email;
- phone;
- password_hash;
- active;
- timestamps.

### Product
- dados simulados;
- preço;
- disponibilidade.

### DeliveryPoint
- endereço pesquisado;
- endereço de referência;
- origem da seleção;
- latitude e longitude aproximadas;
- latitude e longitude finais;
- tipo PostGIS criado pelas coordenadas finais;
- rótulo;
- instruções;
- precisão estimada;
- modo de mapa;
- confirmação do usuário;
- confirmação de área segura.

### Order
- cliente;
- status;
- valores simulados;
- forma de pagamento simulada;
- ponto;
- timestamps.

### OrderItem
- snapshot do nome;
- preço;
- quantidade.

### AdminDecision
- pedido;
- administrador;
- decisão;
- motivo;
- timestamp.

### Mission
- pedido;
- origem;
- destino;
- altitude;
- distância;
- estado;
- arquivo de missão;
- timestamps.

### MissionWaypoint
- ordem;
- comando;
- coordenadas;
- altitude;
- parâmetros.

### FlightAuthorization
- missão;
- administrador;
- status;
- data;
- validade;
- uso;
- checklist associado.

### Vehicle
- identificador;
- nome;
- sistema;
- status;
- última comunicação.

### VehicleHealthSnapshot
- heartbeat;
- GPS;
- satélites;
- EKF;
- bateria;
- modo;
- armamento;
- timestamp.

### TelemetryLog
- missão;
- posição;
- altitude;
- velocidade;
- bateria;
- GPS;
- modo;
- armamento;
- timestamp.

### SystemEvent
- ator;
- pedido;
- missão;
- veículo;
- tipo;
- severidade;
- mensagem;
- metadados;
- timestamp.

Use UUID, UTC, `Decimal`, constraints e migrações.

---

## 12. Endpoints iniciais

### Cliente

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me

GET  /api/v1/products
GET  /api/v1/products/{product_id}

GET  /api/v1/maps/places/search
GET  /api/v1/maps/geocode
GET  /api/v1/maps/reverse-geocode
POST /api/v1/delivery-points/validate
POST /api/v1/delivery-points
GET  /api/v1/delivery-points

POST /api/v1/orders
GET  /api/v1/orders
GET  /api/v1/orders/{order_id}
POST /api/v1/orders/{order_id}/submit
POST /api/v1/orders/{order_id}/cancel
```

### Administrador

```text
GET  /api/v1/admin/orders
GET  /api/v1/admin/orders/{order_id}
POST /api/v1/admin/orders/{order_id}/approve
POST /api/v1/admin/orders/{order_id}/reject

POST /api/v1/admin/orders/{order_id}/prepare-mission
GET  /api/v1/admin/missions/{mission_id}
POST /api/v1/admin/missions/{mission_id}/mark-under-review
POST /api/v1/admin/missions/{mission_id}/mark-reviewed
POST /api/v1/admin/missions/{mission_id}/authorize-flight
POST /api/v1/admin/missions/{mission_id}/abort
POST /api/v1/admin/missions/{mission_id}/request-rtl

GET  /api/v1/admin/vehicles
GET  /api/v1/admin/vehicles/{vehicle_id}/health
GET  /api/v1/admin/events
```

### Gateway

```text
POST /api/v1/gateway/heartbeat
GET  /api/v1/gateway/missions/authorized
POST /api/v1/gateway/missions/{mission_id}/claim
POST /api/v1/gateway/missions/{mission_id}/upload-status
POST /api/v1/gateway/missions/{mission_id}/status
POST /api/v1/gateway/missions/{mission_id}/telemetry
POST /api/v1/gateway/missions/{mission_id}/events
```

### WebSocket

```text
WS /api/v1/ws/orders/{order_id}
WS /api/v1/ws/admin/operations
```

---

## 13. Integração com Mission Planner

Implemente uma abordagem realista em etapas.

### Etapa inicial funcional

O backend deve gerar uma missão com:

- origem;
- decolagem;
- destino;
- espera;
- entrega;
- retorno;
- pouso.

O sistema deve exportar uma versão compatível com Mission Planner, como arquivo de waypoints, e armazenar:

- hash;
- versão;
- data;
- missão;
- administrador que solicitou;
- estado.

O painel admin deve permitir:

- visualizar a missão;
- visualizar waypoints;
- baixar o arquivo;
- marcar como aberta no Mission Planner;
- registrar revisão;
- autorizar o voo somente após a revisão.

### Integração MAVLink real

O `drone_gateway` deve:

- conectar à Pixhawk por configuração;
- aguardar heartbeat;
- identificar o veículo;
- consultar missão autorizada;
- validar autorização;
- validar checklist e estado;
- fazer upload da missão;
- confirmar contagem e conteúdo;
- registrar sucesso ou falha;
- iniciar somente após autorização válida;
- transmitir telemetria;
- não repetir uma missão já consumida.

O Mission Planner permanece aberto como estação de monitoramento e revisão.

Não tente automatizar cliques ou manipular a interface do Mission Planner de forma frágil. Prefira arquivo compatível, MAVLink e procedimentos documentados.

---

## 14. Regras para hardware real

O projeto deve suportar:

```env
MAVLINK_MODE=simulation
```

e:

```env
MAVLINK_MODE=real
```

### Modo real

O modo real deve exigir:

- variável explícita;
- conexão configurada;
- administrador autenticado;
- missão autorizada;
- checklist aprovado;
- heartbeat;
- estado válido;
- GPS adequado;
- bateria mínima;
- origem conhecida;
- distância permitida;
- geofence;
- RTL configurado;
- operador responsável.

Não execute armamento ao iniciar o gateway.

Não execute voo por health check.

Não altere parâmetros críticos automaticamente.

Não esconda mensagens de pre-arm.

O código pode preparar e executar a missão real, mas somente por ação administrativa explícita e após as verificações.

---

## 15. Painel administrativo

Crie uma aplicação web separada usando React, TypeScript e Vite.

O painel deve compartilhar os tokens de marca definidos em `docs/DESIGN_SYSTEM.md`, mas adaptar densidade, layout e componentes para operação administrativa. Não copie diretamente o layout mobile para desktop. Reutilize os componentes definidos em `admin_web/src/design-system/` e evite estilos locais duplicados.

### Telas

1. Login administrativo.
2. Dashboard.
3. Pedidos pendentes.
4. Detalhe do pedido.
5. Mapa do destino.
6. Aprovação ou rejeição.
7. Preparação da missão.
8. Revisão dos waypoints.
9. Estado do drone.
10. Checklist pré-voo.
11. Autorização do voo.
12. Telemetria ao vivo.
13. Eventos e falhas.
14. Histórico de pedidos e missões.

### Dashboard

Mostre:

- pedidos pendentes;
- pedidos aprovados;
- missões esperando revisão;
- missões esperando autorização;
- drone conectado ou desconectado;
- bateria;
- GPS;
- modo;
- última comunicação;
- missões em execução;
- alertas.

### Segurança

- rotas protegidas;
- função `ADMIN`;
- token seguro;
- sem segredos no front-end;
- confirmação reforçada para autorizar voo;
- modal com resumo da missão;
- proibição de duplo clique ou envio duplicado;
- auditoria de cada ação.

---

## 16. Aplicativo Flutter

Antes das telas finais:

1. analise as quatro imagens fornecidas;
2. crie `docs/DESIGN_SYSTEM.md`;
3. implemente tokens, tema e componentes reutilizáveis;
4. crie o catálogo de desenvolvimento;
5. somente então monte as telas usando esses componentes.

Não reproduza cada screenshot como um widget monolítico. Divida a interface em componentes reutilizáveis e preserve a identidade visual.

Implemente:

- splash;
- cadastro;
- login;
- produtos;
- carrinho;
- mapa com Google Maps;
- localização aproximada atual;
- pesquisa de endereço;
- autocomplete;
- confirmação da região;
- segunda etapa em visão de satélite;
- marcador/seta arrastável;
- ponto de entrega exato;
- exibição de latitude e longitude;
- instruções;
- pagamento simulado;
- envio do pedido;
- tela aguardando aprovação;
- pedido rejeitado com motivo;
- pedido aprovado;
- missão preparada;
- drone em rota;
- drone no destino;
- retorno;
- conclusão;
- falha.

O aplicativo não:

- aprova pedido;
- autoriza voo;
- envia MAVLink;
- controla altitude;
- controla o drone.

---

## 17. Programação inicial obrigatória

Implemente um primeiro fluxo vertical funcional:

1. Cliente se cadastra.
2. Cliente entra.
3. Cliente lista produtos.
4. Cliente cria ponto.
5. Cliente cria pedido.
6. Cliente envia pedido para aprovação.
7. Administrador entra no painel.
8. Administrador vê o pedido.
9. Administrador aprova.
10. Backend cria missão.
11. Administrador visualiza a missão.
12. Administrador registra revisão.
13. Gateway fake ou SITL apresenta estado saudável.
14. Administrador autoriza o voo.
15. Gateway assume a missão.
16. Gateway simula ou executa upload conforme modo.
17. Estados aparecem no mobile e admin.

Depois, prepare a integração real com Pixhawk sem fingir que ela foi testada.

---

## 18. Ordem de implementação

### Fase 1 — Governança, documentação e design system

- atualizar AGENTS;
- atualizar arquitetura;
- criar regras;
- registrar admin e hardware real;
- criar ADRs;
- analisar as imagens de referência;
- criar `docs/DESIGN_SYSTEM.md`;
- definir tokens, tema, componentes e regras de reutilização;
- preparar o catálogo de componentes Flutter e React.

### Fase 2 — Infraestrutura

- Docker;
- PostGIS;
- backend;
- migrações;
- logs;
- configurações.

### Fase 3 — Domínio

- usuários;
- funções;
- produtos;
- pontos;
- pedidos;
- aprovação;
- missão;
- autorização;
- veículos;
- eventos.

### Fase 4 — Aplicativo Flutter

- autenticação;
- catálogo;
- mapa;
- pedido;
- acompanhamento.

### Fase 5 — Painel administrativo

- autenticação;
- pedidos;
- aprovação;
- missão;
- checklist;
- autorização;
- acompanhamento.

### Fase 6 — Gateway em modo fake

- contratos;
- estados;
- telemetria;
- idempotência;
- testes.

### Fase 7 — SITL

- conexão;
- upload;
- telemetria;
- RTL;
- testes ponta a ponta.

### Fase 8 — Hardware real

- conexão com Pixhawk;
- leitura de saúde;
- upload real;
- autorização;
- execução em bancada;
- motores sem hélices;
- voo manual;
- missão curta;
- entrega;
- retorno.

Não pule diretamente para voo autônomo real sem validar as etapas anteriores.

---

## 19. Testes obrigatórios

### Backend

Teste:

- cadastro;
- login;
- funções;
- acesso administrativo;
- pedido;
- submissão;
- aprovação;
- rejeição;
- motivo;
- missão;
- autorização;
- transições;
- duplicidade;
- auditoria.

### Admin

Teste:

- proteção de rotas;
- fila;
- aprovação;
- rejeição;
- revisão;
- autorização;
- confirmação reforçada;
- erro;
- reconexão.

### Mobile

Teste:

- formulários;
- catálogo;
- carrinho;
- ponto;
- pedido;
- estados;
- rejeição;
- acompanhamento.

### Gateway

Teste:

- heartbeat;
- parsing;
- timeout;
- claim;
- upload;
- duplicidade;
- telemetria;
- falha;
- RTL;
- autorização expirada;
- missão já consumida.

### SITL

Teste:

- missão curta;
- chegada;
- retorno;
- perda de link simulada;
- bateria simulada;
- upload incorreto;
- abortamento.

### Hardware

Documente e execute de forma manual e controlada:

- Pixhawk conectada;
- rádio;
- telemetria;
- GPS;
- motores sem hélices;
- armamento manual;
- voo manual;
- missão curta;
- RTL;
- carga leve;
- mecanismo de entrega.

Nunca marque um teste de hardware como aprovado sem evidência real.

---

## 20. Segurança e auditoria

Registre:

- quem aprovou o pedido;
- quem rejeitou;
- motivo;
- quem preparou missão;
- versão da missão;
- quem revisou;
- quem autorizou voo;
- horário;
- veículo;
- resultado do checklist;
- upload;
- início;
- chegada;
- entrega;
- retorno;
- conclusão;
- abortamento;
- falha.

A autorização do voo deve:

- ser de uso único;
- expirar;
- estar ligada a uma versão específica da missão;
- ser invalidada se a missão mudar;
- ser invalidada se o estado crítico do veículo mudar;
- não ser reutilizada após falha ou conclusão.

---

## 21. Configurações mínimas

O `.env.example` deve incluir:

```env
APP_ENV=development
APP_NAME=drone-delivery

API_HOST=0.0.0.0
API_PORT=8000
API_BASE_URL=http://localhost:8000

DATABASE_HOST=db
DATABASE_PORT=5432
DATABASE_NAME=drone_delivery
DATABASE_USER=drone_user
DATABASE_PASSWORD=change_me

JWT_SECRET=change_me
JWT_EXPIRE_MINUTES=60

ADMIN_INITIAL_EMAIL=admin@example.local
ADMIN_INITIAL_PASSWORD=change_me

MAP_PROVIDER=google_maps
GOOGLE_MAPS_ANDROID_API_KEY=
GOOGLE_MAPS_SERVER_API_KEY=
GOOGLE_MAPS_DEFAULT_TYPE=satellite
MAPS_SEARCH_COUNTRY=BR
MAPS_DEFAULT_LATITUDE=-23.1175
MAPS_DEFAULT_LONGITUDE=-46.5502

GATEWAY_API_KEY=change_me
MAVLINK_MODE=simulation
MAVLINK_CONNECTION=udp:127.0.0.1:14550
REAL_HARDWARE_CONFIRMATION_REQUIRED=true

DEFAULT_TAKEOFF_ALTITUDE_M=10
MAX_MISSION_DISTANCE_M=500
MIN_BATTERY_PERCENT=40
MIN_GPS_SATELLITES=10
HEARTBEAT_TIMEOUT_SECONDS=10
MISSION_COMMAND_TIMEOUT_SECONDS=15
FLIGHT_AUTHORIZATION_TTL_SECONDS=300
TELEMETRY_PERSIST_INTERVAL_SECONDS=2
```

Use valores de exemplo, nunca credenciais reais.

---

## 22. Comandos e validação

Execute, quando disponível:

### Backend

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

### Painel admin

```powershell
cd admin_web
npm install
npm run lint
npm run test
npm run build
```

### Flutter

```powershell
cd mobile
flutter pub get
dart format --set-exit-if-changed .
flutter analyze
flutter test
flutter build apk --debug
```

### Gateway

```powershell
cd drone_gateway
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

### Docker

```powershell
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100
```

Não esconda falhas e não afirme que executou o que não foi executado.

---

## 23. Restrições

- Produtos são simulados.
- Pagamento é simulado.
- Aplicativo, admin, banco, coordenadas, aprovação, missão, telemetria e hardware são reais.
- Não permita que o cliente autorize o voo.
- Não misture aprovação do pedido com autorização do voo.
- Não permita cadastro público de administrador.
- Não coloque lógica de voo no front-end.
- Não coloque regras de pedido no gateway.
- Não permita acesso direto do gateway ao banco.
- Não automatize cliques no Mission Planner.
- Não arme o drone ao iniciar o sistema.
- Não desative failsafes.
- Não ignore pre-arm.
- Não altere parâmetros críticos automaticamente.
- Não execute hardware em testes automatizados.
- Não invente resultado de testes.
- Não crie funcionalidades fora do escopo principal.
- Não duplique cores, espaçamentos, estilos de texto, sombras ou bordas em múltiplas telas.
- Não crie cada tela como um componente monolítico.
- Não use screenshots como substituição da interface real.
- Não crie componentes genéricos sem uso real.
- Não use valores visuais literais quando existir token correspondente.
- Não altere a identidade visual sem atualizar `docs/DESIGN_SYSTEM.md`.
- Não tratar o endereço pesquisado como coordenada final.
- Não confirmar automaticamente a localização aproximada do dispositivo.
- Não pular a segunda etapa de posicionamento manual.
- Não utilizar visão terrestre como única confirmação final.
- Não armazenar chaves do Google Maps diretamente no código.
- Não permitir que o administrador altere silenciosamente o ponto escolhido.

---

## 24. Resultado esperado

Entregue um repositório real, estruturado e executável.

Ao terminar, apresente:

1. resumo;
2. árvore criada;
3. documentos criados ou atualizados;
4. `docs/DESIGN_SYSTEM.md` e análise das imagens;
5. tokens, temas, componentes reutilizáveis e catálogo visual;
6. backend implementado;
7. aplicativo implementado;
8. painel administrativo implementado;
9. gateway implementado;
10. fluxo funcional disponível;
11. migrações;
12. testes;
13. comandos executados;
14. falhas;
15. limitações;
16. o que já funciona com SITL;
17. o que já foi validado com Pixhawk;
18. o que ainda precisa de teste real;
19. riscos;
20. próximo passo recomendado.

Diferencie claramente:

- código implementado;
- código testado;
- integração simulada;
- integração SITL;
- integração real com Pixhawk;
- voo real validado.

Nunca declare o drone real como funcional apenas porque a estrutura de software foi criada.
