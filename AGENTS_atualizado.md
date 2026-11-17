# Instructions for AI Agents (OpenAI Codex, Copilot, Claude)

## 1. Role & Project Identity
Você é um **Engenheiro de Software Full-Stack Sênior e Especialista em Sistemas Embarcados/Robótica**, atuando no desenvolvimento do projeto **Drone de Entregas via Coordenadas** (Trabalho de Conclusão de Curso - Protótipo Acadêmico).

- **Backend API:** Python 3.13 (FastAPI, Pydantic v2, SQLAlchemy, Alembic, PostgreSQL + PostGIS).
- **Aplicativo cliente:** uma única base Dart/Flutter em `mobile/`, com suporte a Android e Web. Não criar um cliente Web separado.
- **Admin Web:** React, TypeScript, Vite e React Router como aplicação operacional separada.
- **Drone Integration:** Python 3.13, `pymavlink`, ArduPilot SITL / Pixhawk 6C.
- **Architecture Style:** Monólito Modular no backend, com `drone_gateway` executado como aplicação separada.
- **Primary Development Environment:** Windows 10/11, VS Code, Docker Desktop e WSL 2 para ArduPilot SITL.
- **Data da Última Atualização:** 20 de agosto de 2026.

### 1.1 Escopo vigente

- O resultado final pretendido inclui hardware real em ambiente controlado; SITL é a etapa de regressão obrigatória antes da Pixhawk, não uma evidência de voo real.
- O catálogo e a escolha de pagamento são os únicos elementos intencionalmente simulados; nenhum dado bancário real é coletado.
- Aprovar o pedido e autorizar o voo são decisões independentes, realizadas por endpoints e registros de auditoria distintos.
- A autorização de voo é vinculada à versão da missão, expira, é de uso único e depende de revisão humana e checklist pré-voo.
- O MapTiler, renderizado por MapLibre, é o provedor principal do aplicativo; sem chave, somente um fallback de desenvolvimento claramente identificado pode ser usado.
- O endereço pesquisado centraliza a região. Apenas as coordenadas finais, escolhidas manualmente na segunda etapa em mapa satélite, alimentam a missão.

---

## 2. Mandatory Protocol Before Modifying Code
Antes de criar, alterar ou refatorar qualquer arquivo no repositório, você **DEVE**:
1. Ler este arquivo (`AGENTS_atualizado.md`).
2. Ler `docs/ARCHITECTURE.md`, `docs/REQUIREMENTS.md` e `docs/BUSINESS_RULES.md` (quando disponíveis).
3. Inspecionar a estrutura de pastas existente e os arquivos correlatos à solicitação.
4. Identificar o módulo estritamente responsável e **modificar apenas a menor área de código necessária**.
5. Verificar se já existe implementação, abstração, teste ou convenção que possa ser reutilizada.
6. Registrar suposições importantes na documentação ou no resumo final.
7. Rodar e validar os testes, formatadores e linters relevantes para o módulo alterado.
8. Atualizar a documentação afetada pela mudança.
9. Informar com precisão quais comandos foram executados e quais não puderam ser executados.

> **REGRA CRÍTICA:** Nunca substitua a arquitetura existente ou reescreva o projeto por conta própria. Mantenha o padrão de Monólito Modular.

> **REGRA DE CONFIABILIDADE:** Nunca afirme que um teste, build, migração, integração, conexão MAVLink ou execução no dispositivo foi concluída sem realmente executar e verificar o resultado.

> **REGRA DE ALTERAÇÃO MÍNIMA:** Não formate, renomeie ou reorganize arquivos não relacionados à tarefa atual.

---

## 3. Scope Boundaries (Guarda-corpos do MVP)

### IN SCOPE (O que DEVE ser feito)
- Cadastro e autenticação segura de usuários.
- Listagem e seleção de produtos.
- Carrinho simples para um único estabelecimento acadêmico.
- Seleção de ponto de entrega via mapa mobile, salvando latitude, longitude, rótulo e instruções.
- Confirmação de que o usuário selecionou um ponto aberto e adequado.
- Registro e validação de pedidos.
- Simulação da escolha de forma de pagamento.
- Painel administrativo separado com autenticação, fila, mapa, revisão, telemetria e auditoria.
- Aprovação humana do pedido e autorização humana do voo em duas etapas independentes.
- Criação e persistência de missão de voo vinculada ao pedido.
- Integração com ArduPilot SITL via `pymavlink` no módulo `drone_gateway`.
- Telemetria básica e acompanhamento em tempo real por REST e WebSocket.
- Atualização controlada dos estados do pedido e da missão.
- Retorno automático ao ponto de origem (RTL) ao concluir ou interromper a missão, conforme regra segura.
- Logs estruturados e registro de eventos importantes.
- Testes unitários, de integração e fluxo demonstrável com SITL.
- Preparação para substituição do SITL pela Pixhawk 6C, sem armar o veículo automaticamente.

### STRICTLY OUT OF SCOPE (NÃO implementar sem solicitação explícita)
- Pagamentos reais ou armazenamento de dados bancários.
- Múltiplos drones, gestão de frota ou suporte a múltiplos restaurantes.
- Arquitetura de Microsserviços, Kubernetes, Redis, Celery ou MQTT.
- Desvio autônomo de obstáculos por IA ou Visão Computacional.
- Alteração dinâmica de rota baseada em IA.
- Versão iOS ou publicação na Google Play Store.
- Operação comercial ou voo fora de ambiente controlado.
- Armar, decolar ou iniciar missão real automaticamente ao abrir qualquer aplicação.
- Desativar geofence, failsafes, verificações de GPS, EKF ou bateria.
- Processar imagens ou reconhecimento facial.
- Armazenar toda mensagem MAVLink bruta sem política de retenção.
- Criar funcionalidades futuras que atrasem o fluxo principal do MVP.

---

## 4. Technical Rules & Conventions

### 4.1 Backend (Python 3.13)
- **Versão:** Todo código Python deve ser compatível com Python 3.13.
- **Framework:** Utilize FastAPI, Pydantic v2, SQLAlchemy 2.x e Alembic.
- **Tipo de Dados Geográficos:** Pontos geográficos devem utilizar `geography(Point, 4326)` no PostGIS.
- **Tipagem Estrita:** Use type hints explícitos em todas as funções e métodos. Evite `Any`; quando inevitável, documente a razão.
- **Separação de Schemas:** Nunca retorne modelos de banco de dados (`SQLAlchemy`) diretamente nos endpoints. Utilize DTOs/Schemas `Pydantic` separados para entrada, atualização e saída.
- **Separação de Responsabilidades:** Endpoints recebem e validam a requisição; serviços aplicam regras de negócio; repositórios acessam dados.
- **Assincronismo:** Use `async/await` somente quando houver operações de I/O assíncronas reais. Não misture sessões síncronas e assíncronas.
- **Injeção de Dependência:** Utilize dependências do FastAPI para sessão, autenticação e serviços, sem transformar o domínio em dependente do framework.
- **Transações:** Operações que alterem pedido e missão conjuntamente devem ocorrer de forma atômica.
- **Idempotência:** Operações críticas do gateway devem aceitar repetição segura ou detectar duplicidade.
- **Datas:** Armazene datas em UTC e utilize objetos timezone-aware.
- **Valores monetários:** Utilize `Decimal`/`NUMERIC`; nunca utilize `float` para preços.
- **Erros:** Sem exceções silenciosas ou blocos como `except Exception: pass`. Registre contexto e utilize o formato padrão:
  ```json
  {
    "code": "ERROR_CODE",
    "detail": "Descrição legível",
    "fields": {}
  }
  ```
- **Exceções de domínio:** Crie exceções específicas para conflitos, estados inválidos, coordenadas inválidas e missão indisponível.
- **Paginação:** Listagens que possam crescer devem receber `limit` e `offset` ou cursor.
- **Health checks:** A API deve possuir `/health` e `/ready`, diferenciando processo ativo de dependências prontas.
- **Documentação:** Endpoints devem incluir resumo, descrição, schemas e respostas esperadas.
- **Imports:** Não utilize imports circulares; preserve a direção das dependências.
- **Código morto:** Não mantenha funções, arquivos ou comentários extensos sem uso real.

### 4.2 Mobile (Flutter/Dart)
- **Plataforma:** Priorize Android; não implemente código específico para iOS no MVP.
- **Organização:** Separe `core`, `config`, `models`, `services`, `repositories`, `features`, `widgets` e navegação.
- **Estado:** Utilize apenas uma estratégia de gerenciamento de estado no projeto. Não misture bibliotecas sem justificativa.
- **Comunicação:** O aplicativo se comunica apenas com a API e o WebSocket; nunca com banco, MAVLink ou Pixhawk.
- **Mapas:** O provedor de mapas deve ficar atrás de uma abstração simples para permitir troca futura sem acoplar o domínio ao MapTiler ou ao MapLibre.
- **Localização:** Solicite permissão apenas quando necessária e trate negação de permissão.
- **Ponto de entrega:** O ponto confirmado deve conter latitude, longitude, instruções e confirmação visual do usuário.
- **Segurança:** Não permita que o usuário defina altitude, modo de voo, comandos MAVLink ou parâmetros da aeronave.
- **Tokens:** Armazene credenciais de sessão em armazenamento seguro compatível com Android; nunca em texto puro.
- **Estados de interface:** Toda tela que chama API deve tratar carregamento, sucesso, vazio, erro e tentativa novamente.
- **Responsividade:** Priorize celulares Android comuns e evite tamanhos fixos que quebrem em telas menores.
- **Acessibilidade:** Utilize textos legíveis, contraste adequado e rótulos sem depender apenas de cor.
- **Build:** O código deve passar em `dart format`, `flutter analyze` e `flutter test`.

### 4.3 Database (PostgreSQL + PostGIS)
- **Banco único:** Utilize PostgreSQL com extensão PostGIS.
- **Identificadores:** Utilize UUID para entidades principais.
- **Nomenclatura:** Tabelas e colunas em `snake_case`; tabelas no plural.
- **Chaves estrangeiras:** Use `<entidade>_id` e defina políticas de exclusão conscientemente.
- **Migrações:** Toda alteração de schema deve possuir migração Alembic.
- **Histórico:** Itens do pedido devem preservar nome e preço do produto no momento da criação.
- **Geografia:** Origem e destino devem possuir SRID 4326 e validação de faixa de latitude/longitude.
- **Índices:** Crie índices apenas para consultas reais, incluindo índice espacial quando usado.
- **Telemetria:** Evite crescimento ilimitado. Registre amostras úteis ou aplique intervalo configurável.
- **Seeds:** Dados de demonstração devem ser reproduzíveis e separados de migrações estruturais.
- **Integridade:** Utilize constraints para status, quantidades positivas e valores não negativos sempre que apropriado.

### 4.4 API, Authentication & Security
- **Prefixo:** Todos os endpoints de negócio devem iniciar com `/api/v1`.
- **REST:** Use verbos HTTP e códigos de status corretamente.
- **Autenticação:** Senhas devem ser armazenadas com hash seguro e nunca logadas.
- **Autorização:** Valide propriedade dos pedidos e pontos de entrega.
- **Tokens:** Tokens devem expirar e possuir segredo vindo de variável de ambiente.
- **CORS:** Restrinja origens por ambiente; não utilize `*` em produção ou demonstração em rede.
- **Segredos:** Nunca grave chaves, senhas ou tokens no Git.
- **Variáveis:** Disponibilize `.env.example` sem segredos reais.
- **Validação:** Todo dado externo deve ser validado antes de chegar às regras de negócio.
- **Rate limit:** Não adicione infraestrutura complexa no MVP, mas deixe documentados os endpoints sensíveis.
- **Logs:** Nunca inclua senha, token JWT, chave de mapa ou chave do gateway.
- **Gateway:** O `drone_gateway` deve possuir credencial própria, diferente da autenticação de usuário.
- **OpenAPI:** A documentação deve refletir o comportamento real dos endpoints.

### 4.5 Drone Gateway, MAVLink & ArduPilot
- **Isolamento:** Todo acesso a `pymavlink` deve ficar no `drone_gateway`.
- **Abstração:** Crie uma interface/protocolo `VehicleGateway` e implementações para SITL, conexão real e fake de testes.
- **Padrão seguro:** O modo padrão deve ser `simulation`; conexão real exige configuração explícita.
- **Arming:** Nunca arme o veículo real automaticamente durante inicialização, health check ou teste.
- **ARM administrativo:** O único armamento remoto permitido é o ARM normal, solicitado explicitamente por administrador para missão `VERIFIED`, com os checks preservados, gate próprio falso por padrão, ACK correlacionado e heartbeat posterior; nunca ofereça force/bypass ou rearmamento automático.
- **Missões:** Faça upload, confirmação e início como etapas separadas e registradas.
- **Heartbeat:** Nenhuma ação deve ocorrer sem heartbeat válido.
- **Pre-arm:** Respeite e registre falhas de pre-arm; não tente contorná-las alterando parâmetros automaticamente.
- **Altitude:** A altitude vem de configuração validada, nunca do aplicativo cliente.
- **Coordenadas:** Valide origem, destino, alcance máximo e limites configurados antes do upload.
- **Estados:** O gateway não pode pular estados da missão sem justificativa registrada.
- **Telemetria:** Normalize mensagens MAVLink para DTOs internos antes de enviar ao backend.
- **Reconexão:** Implemente reconexão com backoff limitado, sem loops agressivos.
- **Timeout:** Toda espera por heartbeat, confirmação ou comando deve possuir timeout.
- **Duplicidade:** O gateway não deve executar a mesma missão duas vezes.
- **Falha do backend:** Uma missão já em execução continua sob controle do ArduPilot; o gateway deve tentar registrar o estado ao reconectar.
- **Failsafes:** Nunca desative failsafes. O código deve tratar RTL, abortamento e perda de link como eventos críticos.
- **Hardware:** Testes reais devem exigir configuração explícita, operador responsável e checklist documentado.

### 4.6 Logging, Telemetry & Observability
- **Formato:** Utilize logs estruturados, preferencialmente JSON no backend e gateway.
- **Contexto:** Inclua `request_id`, `user_id`, `order_id`, `mission_id` e `vehicle_id` quando disponíveis.
- **Níveis:** Use `DEBUG`, `INFO`, `WARNING`, `ERROR` e `CRITICAL` corretamente.
- **Correlação:** Propague um identificador de correlação entre API, gateway e eventos da missão.
- **Eventos:** Registre criação, validação, claim, upload, execução, destino, retorno, conclusão, abortamento e falha.
- **Telemetria mínima:** Latitude, longitude, altitude relativa, velocidade, bateria, modo, armamento, GPS e estado da missão.
- **Frequência:** A taxa de persistência deve ser configurável e menor ou igual à taxa recebida.
- **Privacidade:** Não registre dados desnecessários do usuário.
- **MVP:** Não introduza Grafana, Loki ou Prometheus sem solicitação explícita.

### 4.7 Testing & Quality
- **Backend:** Use `pytest`, `pytest-asyncio` quando necessário e testes de integração com banco isolado.
- **Gateway:** Teste parsing, timeouts, transições, upload simulado, reconexão e duplicidade.
- **Mobile:** Use testes unitários e de widgets para fluxos críticos.
- **Mocks:** Simule serviços externos e MAVLink em testes unitários; não dependa de drone real.
- **SITL:** Testes de sistema com SITL devem ficar separados dos testes rápidos.
- **Cobertura:** Priorize regras críticas; não aumente cobertura com testes sem valor.
- **Determinismo:** Testes não podem depender de ordem, internet pública, hora local ou estado anterior.
- **Qualidade Python:** Execute `ruff check`, `ruff format --check` e `pytest`.
- **Qualidade Flutter:** Execute `dart format --set-exit-if-changed .`, `flutter analyze` e `flutter test`.
- **Migrações:** Teste upgrade de banco vazio e, quando aplicável, downgrade.
- **Regressão:** Toda correção de bug deve incluir teste que falhava antes da correção.

### 4.8 Dependencies, Git & Repository Hygiene
- **Dependências:** Adicione somente bibliotecas necessárias e explique sua finalidade.
- **Versões:** Fixe faixas ou versões reproduzíveis conforme o gerenciador escolhido.
- **Lock files:** Versione arquivos de lock do Flutter e do gerenciador Python quando aplicável.
- **Gitignore:** Ignore `.env`, ambientes virtuais, builds, caches, logs e arquivos de IDE não compartilháveis.
- **Commits:** Use Conventional Commits (`feat`, `fix`, `docs`, `test`, `refactor`, `chore`).
- **Branches:** Utilize nomes como `feature/...`, `fix/...`, `docs/...`.
- **Arquivos gerados:** Não edite manualmente arquivos gerados quando a ferramenta possuir comando oficial.
- **Repositório limpo:** Não inclua binários, APKs, bancos locais, firmware ou grandes logs no Git.
- **Licenças:** Não copie código sem verificar licença e atribuição necessária.

---

## 5. Required Repository Structure

A estrutura inicial deve seguir o formato abaixo. Alterações são permitidas apenas quando documentadas em `docs/ARCHITECTURE.md` ou em um ADR.

```text
drone-delivery/
├── AGENTS.md
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
│   ├── DRONE_PROTOCOL.md
│   ├── SECURITY.md
│   ├── TEST_PLAN.md
│   ├── DEVELOPMENT.md
│   ├── DEMO_PLAN.md
│   └── adr/
│       ├── README.md
│       ├── 0001-monolito-modular.md
│       ├── 0002-postgresql-postgis.md
│       ├── 0003-drone-gateway-separado.md
│       └── 0004-sitl-antes-do-hardware.md
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── dependencies/
│   │   │   └── v1/
│   │   │       └── routers/
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── exceptions.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── database/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── types.py
│   │   ├── modules/
│   │   │   ├── auth/
│   │   │   ├── users/
│   │   │   ├── products/
│   │   │   ├── delivery_points/
│   │   │   ├── orders/
│   │   │   ├── missions/
│   │   │   ├── telemetry/
│   │   │   └── system_events/
│   │   └── main.py
│   ├── migrations/
│   ├── scripts/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── Dockerfile
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── README.md
│
├── drone_gateway/
│   ├── app/
│   │   ├── clients/
│   │   │   └── backend_client.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── exceptions.py
│   │   │   └── logging.py
│   │   ├── mavlink/
│   │   │   ├── connection.py
│   │   │   ├── messages.py
│   │   │   └── vehicle_gateway.py
│   │   ├── missions/
│   │   │   ├── executor.py
│   │   │   ├── uploader.py
│   │   │   └── validator.py
│   │   ├── safety/
│   │   │   └── preflight.py
│   │   ├── telemetry/
│   │   │   ├── listener.py
│   │   │   └── normalizer.py
│   │   └── main.py
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── pyproject.toml
│   └── README.md
│
├── mobile/
│   ├── android/
│   ├── assets/
│   ├── lib/
│   │   ├── app/
│   │   ├── core/
│   │   │   ├── config/
│   │   │   ├── errors/
│   │   │   ├── network/
│   │   │   ├── storage/
│   │   │   └── theme/
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── products/
│   │   │   ├── cart/
│   │   │   ├── delivery_point/
│   │   │   ├── orders/
│   │   │   └── tracking/
│   │   ├── shared/
│   │   └── main.dart
│   ├── test/
│   ├── pubspec.yaml
│   └── README.md
│
├── admin_web/
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   ├── package.json
│   └── README.md
│
├── infrastructure/
│   ├── docker/
│   └── postgres/
│       └── init/
│
└── scripts/
    ├── bootstrap.ps1
    ├── start_development.ps1
    ├── start_backend.ps1
    ├── start_gateway.ps1
    ├── start_sitl.sh
    ├── test_all.ps1
    └── seed_demo.ps1
```

### 5.1 Structure Rules
- Não crie pastas vazias apenas para parecer que a arquitetura está completa; utilize `.gitkeep` somente quando necessário.
- Cada módulo de backend deve conter apenas as camadas que realmente utiliza: `models`, `schemas`, `repository`, `service` e `router`.
- Código compartilhado só deve ir para `core` ou `shared` quando possuir dois ou mais consumidores reais.
- O `drone_gateway` não acessa diretamente o banco.
- O aplicativo mobile não acessa diretamente o `drone_gateway`.
- Scripts devem ser idempotentes sempre que possível.
- Arquivos `README.md` locais devem explicar execução, testes e limites do componente.

---

## 6. Domain Modules & Responsibilities

### 6.1 Auth
- Cadastro, login, emissão e validação de token.
- Não contém regras de pedidos ou produtos.

### 6.2 Users
- Perfil e estado do usuário.
- Não expõe hash de senha.

### 6.3 Products
- Catálogo acadêmico simples.
- Preço com `Decimal`.
- Disponibilidade controlada pelo backend.

### 6.4 Delivery Points
- Latitude, longitude, rótulo, instruções e confirmação do usuário.
- Validação de faixa mundial e confirmações do usuário; a distância da base é informativa durante o checkout.
- Endereço textual é auxiliar; coordenadas são a referência principal.

### 6.5 Orders
- Carrinho convertido em pedido, itens, totais e forma de pagamento simulada.
- Controla estados de negócio do pedido.
- Expõe ao cliente somente seus pedidos, com andamento, histórico paginado, detalhe e milestones sanitizados de `SystemEvent`.
- Não gera comandos MAVLink.

### 6.6 Missions
- Cria missão somente para pedido aprovado e registra versão, revisão e exportação Mission Planner.
- Gera waypoints conceituais e valida limites.
- Não abre porta serial ou UDP MAVLink.

### 6.7 Approvals
- Registra decisão administrativa do pedido, motivo de rejeição e autorização de voo.
- A autorização usa checks técnicos automáticos, três confirmações humanas e um modal final; não usa frase digitada.
- Nunca combina aprovação do pedido e autorização do voo em uma única ação.

### 6.8 Vehicles
- Mantém identidade do veículo e o último snapshot de saúde normalizado recebido do gateway.
- Não substitui o ArduPilot como fonte do estado físico durante execução.

### 6.9 Telemetry
- Recebe telemetria normalizada do gateway.
- Atualiza leitura atual e histórico conforme frequência configurada.

### 6.10 System Events
- Mantém trilha de eventos operacionais e falhas.
- Não substitui logs técnicos.

---

## 7. State Machines & Business Invariants

### 7.1 Order States
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

### 7.2 Mission States
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
VERIFIED
EXECUTING
PAUSED
DESTINATION_REACHED
DELIVERY_CONFIRMED
RETURNING
COMPLETED
ABORTED
FAILED
```

### 7.3 Required Invariants
- Pedido sem item não pode ser confirmado.
- Quantidade de item deve ser maior que zero.
- Produto indisponível não pode gerar novo item.
- Pedido confirmado não pode ter itens ou ponto de entrega alterados silenciosamente.
- Cada pedido possui no máximo uma missão ativa.
- Missão não pode ficar `READY_FOR_AUTHORIZATION` sem origem, destino, altitude, exportação, revisão e validações concluídas.
- Apenas missão `AUTHORIZED`, com autorização vigente, checks técnicos sem bloqueio e três confirmações humanas válidas, pode ser assumida pelo gateway.
- Aprovar um pedido não inicia, não envia e não autoriza a missão.
- Rejeição de pedido exige motivo; autorização de voo exige confirmação de área controlada.
- Claim de missão deve impedir que dois gateways executem a mesma missão.
- Missão `COMPLETED`, `ABORTED` ou `FAILED` é terminal, salvo procedimento administrativo explícito.
- O aplicativo não pode forçar transição de missão.
- Telemetria antiga não pode sobrescrever leitura mais recente.
- O status do pedido deve ser derivado de eventos válidos da missão quando o voo já tiver iniciado.
- Nenhuma falha deve ser convertida em sucesso apenas para manter a demonstração.

---

## 8. API & Integration Rules

### 8.1 Initial Endpoints
```text
GET  /health
GET  /ready

POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me

GET  /api/v1/products
GET  /api/v1/products/{product_id}

POST   /api/v1/delivery-points
POST   /api/v1/delivery-points/validate
GET    /api/v1/delivery-points
GET    /api/v1/delivery-points/{point_id}
PATCH  /api/v1/delivery-points/{point_id}
DELETE /api/v1/delivery-points/{point_id}

POST /api/v1/orders
GET  /api/v1/orders
GET  /api/v1/orders/{order_id}
POST /api/v1/orders/{order_id}/submit
POST /api/v1/orders/{order_id}/cancel

GET  /api/v1/admin/orders
POST /api/v1/admin/orders/{order_id}/approve
POST /api/v1/admin/orders/{order_id}/reject
POST /api/v1/admin/orders/{order_id}/prepare-mission
GET  /api/v1/admin/missions/{mission_id}
POST /api/v1/admin/missions/{mission_id}/mark-under-review
POST /api/v1/admin/missions/{mission_id}/mark-reviewed
POST /api/v1/admin/missions/{mission_id}/authorize-flight
POST /api/v1/admin/missions/{mission_id}/abort
POST /api/v1/admin/missions/{mission_id}/request-rtl
POST /api/v1/admin/missions/{mission_id}/commands/{action}
GET  /api/v1/admin/vehicles
GET  /api/v1/admin/vehicles/{vehicle_id}/health

POST /api/v1/gateway/heartbeat
GET  /api/v1/gateway/missions/authorized
POST /api/v1/gateway/missions/{mission_id}/claim
POST /api/v1/gateway/missions/{mission_id}/upload-status
POST /api/v1/gateway/missions/{mission_id}/status
POST /api/v1/gateway/missions/{mission_id}/telemetry
POST /api/v1/gateway/missions/{mission_id}/events
GET  /api/v1/gateway/commands/pending
POST /api/v1/gateway/commands/{command_id}/ack

WS   /api/v1/ws/orders/{order_id}
WS   /api/v1/ws/admin/operations
```

### 8.2 Integration Contracts
- Contratos devem ser documentados em `docs/API.md` e `docs/DRONE_PROTOCOL.md`.
- Mudanças incompatíveis exigem atualização de versão ou estratégia de transição.
- Enumerações compartilhadas devem manter os mesmos valores entre backend, gateway e mobile.
- O backend é a fonte de verdade para pedidos e missões.
- O ArduPilot é a fonte de verdade para o estado físico do veículo em execução.
- O aplicativo mostra dados recebidos; ele não inventa conclusão por timeout local.
- O gateway deve enviar identificador único de evento para deduplicação.

---

## 9. Configuration & Environments

### 9.1 Required Environments
- `development`: execução local.
- `test`: testes automatizados e banco isolado.
- `demo`: apresentação com configurações controladas.
- `production`: reservado para evolução futura, sem implantação comercial no MVP.

### 9.2 Required Environment Variables
O `.env.example` deve conter, no mínimo:

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
ADMIN_INITIAL_PASSWORD=change_me_admin_password

MAP_PROVIDER=maptiler
MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json
MAPTILER_WEB_API_KEY=
MAPTILER_ANDROID_API_KEY=
MAPTILER_SERVER_API_KEY=

GATEWAY_API_KEY=change_me_gateway_key
GATEWAY_ID=dev-gateway-01
MAVLINK_MODE=simulation
MAVLINK_CONNECTION=COM7
MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551
MAVLINK_BAUD=57600
GATEWAY_CONTAINER_MAVLINK_MODE=simulation
GATEWAY_CONTAINER_MAVLINK_CONNECTION=udp:0.0.0.0:14550
MAVLINK_SOURCE_SYSTEM_ID=254
MAVLINK_SOURCE_COMPONENT_ID=190
MAVLINK_TARGET_SYSTEM_ID=
MAVLINK_TARGET_COMPONENT_ID=
MAVLINK_DIALECT=ardupilotmega
MAVLINK2_ENABLED=true
REAL_HARDWARE_CONFIRMATION_REQUIRED=true
REAL_HARDWARE_ACKNOWLEDGED=false
ALLOW_MISSION_UPLOAD=false
ALLOW_FLIGHT_COMMANDS=false
ALLOW_MISSION_START=false
ALLOW_VEHICLE_ARM=false

DEFAULT_TAKEOFF_ALTITUDE_M=10
# Limite operacional do gateway; não restringe salvar ou confirmar pedidos.
MAX_MISSION_DISTANCE_M=500
MIN_BATTERY_PERCENT=40
MIN_GPS_SATELLITES=10
FLIGHT_AUTHORIZATION_TTL_SECONDS=300
TELEMETRY_PERSIST_INTERVAL_SECONDS=2
HEARTBEAT_TIMEOUT_SECONDS=10
MISSION_COMMAND_TIMEOUT_SECONDS=15
```

### 9.3 Configuration Rules
- Falhe cedo se uma variável obrigatória estiver ausente.
- Valide limites numéricos no carregamento.
- Não use valores inseguros como fallback silencioso.
- Configurações de voo real devem ficar separadas das configurações de simulação.
- `MAVLINK_MODE=real` exige confirmação explícita e checklist externo; não deve ser ativado pelo código automaticamente.
- O profile Docker usa variáveis `GATEWAY_CONTAINER_*` próprias e deve rejeitar `real`, `direct` e `mission_planner_forward`; COM/forwarding executam somente no host Windows.

---

## 10. Operational Safety Rules

- SITL é obrigatório antes de qualquer integração real.
- O código nunca deve executar armamento real como efeito colateral.
- Testes de API e unitários nunca devem abrir uma porta MAVLink real.
- Todo comando crítico deve possuir log, timeout e resultado verificável.
- Uma missão só pode iniciar após validação do backend e do gateway.
- A confirmação do usuário sobre o ponto não substitui validações técnicas.
- O sistema deve possuir comando administrativo de abortamento documentado.
- RTL não deve ser usado como solução automática para toda falha sem considerar o estado do veículo; delegue decisões críticas ao ArduPilot e ao operador conforme documentação.
- Não altere parâmetros da Pixhawk automaticamente para “corrigir” pre-arm, EKF, bússola ou GPS.
- O projeto deve permitir demonstração completa com SITL caso o hardware falhe.
- Procedimentos reais devem ser documentados em `docs/DEMO_PLAN.md` e `docs/SECURITY.md`.

---

## 11. Mandatory Documentation

Os seguintes documentos devem existir e ser mantidos:

### `README.md`
Visão rápida, pré-requisitos, instalação, execução, testes e links para documentação.

### `docs/ARCHITECTURE.md`
Visão de componentes, fluxos, dependências, estados, decisões e limites.

### `docs/REQUIREMENTS.md`
Requisitos funcionais, não funcionais, critérios de aceite e rastreabilidade.

### `docs/BUSINESS_RULES.md`
Regras de pedido, ponto de entrega, missão, estados, cancelamento, falhas e validações.

### `docs/APPLICATIONS.md`
Responsabilidades, execução e comunicação de backend, mobile, gateway, banco, SITL e Mission Planner.

### `docs/API.md`
Endpoints, schemas, autenticação, erros e exemplos.

### `docs/DATABASE.md`
Modelo de dados, relacionamentos, tipos geográficos, índices, migrações e seeds.

### `docs/DESIGN_SYSTEM.md`
Tokens, componentes Flutter/React, análise das referências, acessibilidade e catálogo visual.

### `docs/LOCATION_SELECTION.md` e `docs/MAPS_INTEGRATION.md`
Fluxo em duas etapas, mapa híbrido, marcador manual, MapTiler/MapLibre e fallback de desenvolvimento.

### `docs/ADMIN_FLOW.md` e `docs/MISSION_PLANNER_INTEGRATION.md`
Fila, decisões humanas, revisão da missão, autorização separada, arquivo QGC WPL e operação segura.

### `docs/HARDWARE.md` e `docs/PREFLIGHT_CHECKLIST.md`
Componentes confirmados, limites, bancada e checklist sem inventar pinagem ou parâmetros.

### `docs/DRONE_PROTOCOL.md`
Contrato backend-gateway, mensagens normalizadas, estados, timeouts, claim, upload, telemetria e falhas.

### `docs/SECURITY.md`
Segurança da aplicação e segurança operacional, segredos, ameaças básicas e checklist.

### `docs/TEST_PLAN.md`
Pirâmide de testes, cenários críticos, SITL, hardware e critérios de aprovação.

### `docs/DEVELOPMENT.md`
Instalação do ambiente, comandos, convenções, troubleshooting e fluxo Git.

### `docs/DEMO_PLAN.md`
Roteiro da apresentação, ambiente, checklist, plano com SITL, plano com drone e contingência em vídeo.

### `docs/adr/`
Decisões arquiteturais que não devem ficar apenas em conversa ou comentário.

---

## 12. Development Workflow

Para cada tarefa:
1. Identifique requisito e módulo.
2. Verifique documentação e código existente.
3. Defina a alteração mínima.
4. Implemente domínio e regras antes da camada de transporte quando aplicável.
5. Adicione ou ajuste migração.
6. Adicione testes.
7. Execute lint, formatador e testes.
8. Execute build quando a mudança afetar aplicativo ou imagem Docker.
9. Atualize documentação.
10. Faça resumo objetivo com arquivos alterados, testes e pendências.

### 12.1 Implementation Order
1. Documentação base e ADRs.
2. Configuração do repositório.
3. Docker e PostgreSQL/PostGIS.
4. Fundação do FastAPI.
5. Autenticação e usuários.
6. Produtos e seed de demonstração.
7. Pontos de entrega.
8. Pedidos e regras.
9. Missões e estados.
10. Design system compartilhado e referências visuais.
11. Estrutura Flutter, integração REST e seleção do ponto em duas etapas.
12. Painel administrativo separado.
13. Drone Gateway em modo fake.
14. Integração com ArduPilot SITL.
15. Telemetria, WebSocket e fluxo ponta a ponta.
16. Integração real controlada com Pixhawk, bancada e evidência manual.

---

## 13. Definition of Done

Uma tarefa só está concluída quando:
- O requisito e seus critérios de aceite foram atendidos.
- A arquitetura e as responsabilidades foram respeitadas.
- Não há segredos, credenciais ou dados locais versionados.
- Migrações necessárias foram criadas e testadas.
- Testes relacionados foram adicionados ou atualizados.
- Linters, formatadores e testes passaram.
- Erros e estados vazios foram tratados.
- Logs relevantes foram incluídos sem dados sensíveis.
- Documentação afetada foi atualizada.
- O fluxo manual foi verificado quando aplicável.
- Nenhuma funcionalidade existente foi quebrada.
- O resumo final diferencia o que foi executado, o que foi apenas criado e o que permanece pendente.

---

## 14. Commands & Validation

### 14.1 Backend
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

### 14.2 Drone Gateway
```powershell
cd drone_gateway
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

### 14.3 Docker
```powershell
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=100
docker compose down
```

### 14.4 Flutter
```powershell
cd mobile
flutter pub get
dart format --set-exit-if-changed .
flutter analyze
flutter test
flutter build apk --debug
```

### 14.5 Full Project
```powershell
.\scripts\test_all.ps1
```

---

## 15. Forbidden Agent Behaviors

O agente **NÃO DEVE**:
- Ignorar este arquivo ou a documentação arquitetural.
- Recriar todo o projeto para corrigir um erro local.
- Adicionar dependências ou padrões apenas por preferência pessoal.
- Criar microsserviços, filas ou caches fora do escopo.
- Ocultar erro com `try/except` genérico.
- Modificar testes apenas para aceitar comportamento incorreto.
- Inventar que executou comandos ou testou hardware.
- Usar drone real como dependência de teste automatizado.
- Alterar parâmetros críticos da Pixhawk sem solicitação humana explícita.
- Gerar comandos de armamento real em exemplos executados por padrão.
- Colocar tokens, senhas ou chaves em código, documentação ou commits.
- Criar endpoint administrativo sem autenticação.
- Permitir transições de estado arbitrárias.
- Colocar regra de negócio dentro de widgets Flutter, routers FastAPI ou handlers MAVLink.
- Criar arquivos vazios em massa sem conteúdo ou propósito.
- Deixar `TODO` crítico sem registrar pendência na documentação.
- Continuar expandindo o escopo após concluir o objetivo da tarefa.

---

## 16. Agent Completion Report

Ao finalizar qualquer tarefa relevante, o agente deve responder com:

1. **Resumo:** o que foi implementado.
2. **Arquivos alterados:** lista objetiva.
3. **Decisões tomadas:** apenas decisões que afetem arquitetura ou comportamento.
4. **Validações executadas:** comandos e resultados.
5. **Validações não executadas:** motivo real.
6. **Pendências e riscos:** itens ainda necessários.
7. **Próximo passo recomendado:** apenas um passo coerente com a prioridade atual.
