# DEVcore — entrega por drone via coordenadas

Protótipo acadêmico de um sistema de entrega por drone no qual o cliente escolhe o ponto exato no aplicativo Flutter Android/Web, um administrador aprova o pedido e disponibiliza a revisão da missão em `.plan`. O operador revisa e controla a aeronave no QGroundControl.

> **Segurança:** este repositório não autoriza operação comercial nem substitui avaliação aeronáutica. O modo padrão é simulado. Conectar uma Pixhawk, armar motores ou voar exige operador responsável, área controlada, checklist, failsafes e evidência manual. Nenhum health check arma ou inicia o veículo.

## O que é real e o que é simulado

| Parte | Implementação | Limite atual |
|---|---|---|
| Cadastro, autenticação e papéis | API real | Administrador criado somente por seed/CLI |
| Coordenadas e pedidos | API e persistência reais | MapTiler depende de chave configurada |
| Catálogo | Dados acadêmicos | Produtos e avaliações não são comerciais |
| Pagamento | Escolha simulada | Nenhum dado de cartão é coletado ou processado |
| Aprovação e geração | Duas ações administrativas auditadas | Independentes da telemetria |
| Missão | Arquivo `.plan` para QGroundControl, identificado por pedido e revisão | Revisão operacional e upload feitos no QGroundControl |
| Gateway | Recepção passiva PX4 e ambientes de teste isolados | O gateway real não transmite MAVLink |
| Pixhawk 6C | Telemetria recebida pelo encaminhamento UDP | PX4 controla a aeronave e aplica as proteções nativas |

## Fluxo principal

```text
Flutter → FastAPI/PostGIS → aprovação e geração no painel → download do .plan
                                                          → QGroundControl
Pixhawk/PX4 ↔ QGroundControl → recepção UDP → gateway → API/painel
```

No painel, abra o pedido aprovado, prepare a missão e clique em **Baixar missão
para QGroundControl**. Abra em **Plan → Open** e confira origem, rota, altitude
e retorno. O operador conduz o restante no QGroundControl. O painel mantém
exportação e execução observada separadas e permite confirmar entrega mediante
evidência.

## Componentes

- `backend/`: monólito modular FastAPI, SQLAlchemy, Alembic e PostGIS.
- `admin_web/`: painel React, TypeScript e Vite separado do aplicativo.
- `mobile/`: aplicativo Flutter Android/Web e design system derivado das referências.
- `drone_gateway/`: processo Python separado; único componente que fala MAVLink.
- `docs/`: requisitos, arquitetura, design, mapas, hardware e operação segura.
- `infrastructure/`: inicialização do PostgreSQL/PostGIS.
- `scripts/`: comandos locais reproduzíveis para Windows e WSL 2.

O diretório `flutter/`, quando presente localmente, é um SDK de desenvolvimento e fica ignorado pelo Git; não faz parte do produto.

## Pré-requisitos

- Python 3.13;
- Docker Desktop com Compose;
- Node.js 24 ou superior;
- Flutter 3.47/Dart 3.13, Android SDK com API 37, AGP 9.1.1 e Gradle 9.3.1;
- PX4 SITL para testes de protocolo em ambiente isolado;
- QGroundControl para abrir e revisar o plano. Pixhawk é necessária apenas para acompanhar telemetria real.

## Configuração e execução

1. Copie `.env.example` para `.env` e troque todos os valores `change_me`.
2. Nunca versione `.env` ou chaves do MapTiler.
3. Para iniciar banco, API, admin e Flutter Web com um único comando seguro:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_development.ps1 `
  -FlutterSdkRoot 'C:\Users\Luiz\Documents\flutter'
```

O Flutter fica em primeiro plano; gateway não é iniciado por padrão. Para incluir somente o
gateway simulado, use confirmação dupla:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_development.ps1 `
  -FlutterSdkRoot 'C:\Users\Luiz\Documents\flutter' `
  -IncludeSimulationGateway `
  -ConfirmSimulationGateway
```

Esse modo força runtime `container`, `simulation`, `udp:0.0.0.0:14550` e as permissões de escrita desativadas.
Para apenas validar pré-requisitos/configuração sem iniciar serviços, acrescente `-ValidateOnly`.
A recepção real usa o encaminhamento UDP do QGroundControl e o gateway do host.

Para subir somente a pilha de API, banco e painel:

```powershell
docker compose up -d --build db backend admin
Start-Process 'http://localhost:5173'
```

O admin fica em `http://localhost:5173`, a API em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

Para abrir no navegador o mesmo frontend Flutter usado pelo APK:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1 `
  -FlutterSdkRoot 'C:\Users\Luiz\Documents\flutter'
```

Ele fica em `http://localhost:5174`, usa hot reload e lê a configuração Web do MapTiler no `.env` sem imprimir a chave. O painel administrativo continua sendo outra aplicação, em `http://localhost:5173`.

Para o acompanhamento real, configure o encaminhamento unidirecional e inicie
o gateway conforme [Conexão PX4](docs/CONEXAO_DRONE_PX4.md). Os exercícios
legados de comandos dependem de aplicação e banco de teste dedicados.



4. Para executar componentes separadamente:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_admin.ps1
.\scripts\start_mobile.ps1
.\scripts\start_gateway.ps1 -ObserveOnly
```

O padrão versionado é `MAVLINK_MODE=simulation`. Na operação PX4,
`scripts/start_gateway.ps1 -ObserveOnly` recebe o encaminhamento do
QGroundControl e publica observações. O perfil Docker usa variáveis
`GATEWAY_CONTAINER_*` separadas para simulação.

Para comandos separados de Flutter Web, Android e APK, consulte [Build e execução](docs/BUILD_AND_RUN.md). Para celular físico, não use `localhost`: siga [Rede local](docs/LOCAL_NETWORK_SETUP.md).

## Testes

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 `
  -FlutterSdkRoot '<CAMINHO_SDK_FLUTTER_OFICIAL>'
```

Os testes rápidos não abrem conexão com hardware. SITL é uma suíte separada, e os ensaios com Pixhawk são manuais. Veja [Plano de testes](docs/TEST_PLAN.md) e [Plano de demonstração](docs/DEMO_PLAN.md).

## Documentação essencial

- [Arquitetura](docs/ARCHITECTURE.md)
- [Requisitos e rastreabilidade](docs/REQUIREMENTS.md)
- [Regras de negócio](docs/BUSINESS_RULES.md)
- [Contrato da API](docs/API.md)
- [Design system](docs/DESIGN_SYSTEM.md)
- [Seleção do ponto exato](docs/LOCATION_SELECTION.md)
- [Integração de mapas](docs/MAPS_INTEGRATION.md)
- [Configuração do MapTiler](docs/MAPTILER_SETUP.md)
- [Fluxo administrativo](docs/ADMIN_FLOW.md)
- [Mission Planner](docs/MISSION_PLANNER_INTEGRATION.md)
- [Setup Mission Planner/Pixhawk](docs/MISSION_PLANNER_SETUP.md)
- [Protocolo do gateway](docs/DRONE_PROTOCOL.md)
- [Hardware](docs/HARDWARE.md)
- [Checklist pré-voo](docs/PREFLIGHT_CHECKLIST.md)
- [Segurança](docs/SECURITY.md)
- [Relatório de auditoria](docs/AUDIT_REPORT.md)
- [Estado das integrações](docs/INTEGRATION_STATUS.md)
- [Ações manuais](docs/MANUAL_ACTIONS_REQUIRED.md)

## Estado de validação — 21 de agosto de 2026

Após a inclusão do ARM administrativo normal e do endurecimento de concorrência/correlação, a bateria unificada com `-SkipBuilds` terminou com exit 0 e aprovou **351 testes**: backend 56, gateway 85, admin 112 e Flutter 98; o backend manteve 1 teste PostgreSQL opt-in ignorado por falta do ambiente específico. Ruff/format, ESLint, Flutter format/analyze e `docker compose config` passaram. O admin também passou no build Vite. A revisão versionada atual é `0007_vehicle_arm_command`, validada por upgrade/current/downgrade em banco temporário; ela ainda não foi aplicada ao PostgreSQL vivo. Nenhum ARM foi enviado ao hardware e as imagens Docker não foram reconstruídas nesta rodada.

### Snapshot integrado anterior — 20 de agosto de 2026

Na branch `final-1`, sobre o commit-base `b61913995c31933477b2e73910e6d275205d14d2`, a bateria unificada terminou com exit 0 e aprovou **282 testes**: backend 54, gateway 63, admin 67 e Flutter 98; o backend teve ainda um teste PostgreSQL opt-in ignorado porque seu ambiente não foi fornecido. Ruff/format, lint, Flutter format/analyze e `docker compose config` passaram. A migração aplicada é `0006_mission_start_health`.

Os audits atuais retornaram zero vulnerabilidades conhecidas nos ambientes virtuais e nas imagens finais Python, além de zero no `npm audit` completo e de produção. Os builds Docker com `--pull`, Vite, Flutter Web release, dry run automático Wasm e APK debug integrado passaram. Web e APK usam `DEMO_MODE=false` e configuração MapTiler local sem documentar credenciais. O APK final tem 195.252.860 bytes e SHA-256 `0D1F104AB2D22605F901E7588B8DF16CF159D1149CE9F2F1880DDAA1F482B9F6`.

Banco, API e admin ficaram disponíveis em loopback nas portas 5432, 8000 e 5173; o Flutter Web permanece servido em `http://localhost:5174`. Preflight CORS retornou 200 com origem e métodos esperados; uma chamada sem token retornou 401, e um JWT efêmero de cliente listou os quatro produtos reais da API. A senha administrativa atual do `.env` continuou retornando 401 e não foi redefinida. O controlador visual integrado não encontrou navegador disponível; portanto HTTP 200, bundles e worker válidos não são apresentados como smoke visual de login, UI ou mapa renderizado.

Em um ensaio passivo direto de cinco minutos, a Pixhawk 6C/ArduCopter 4.6.3 em `COM7` a 57600 produziu 129 snapshots `HARDWARE_REAL`: `sysid=1`, `compid=1`, modo `STABILIZE`, `armed=false`, bateria 74–75% e GPS que chegou a fix 3/5 satélites, mas terminou em fix 1/0. EKF/preflight permaneceram falsos e home/origin ausentes. Todos os gates ficaram falsos; nenhum comando, upload, início, armamento, ensaio de motor ou voo ocorreu. REST e WebSocket do admin refletiram a origem real e, após a parada, `is_stale=true`.

O forwarding do Mission Planner não completou o fluxo: a porta 14551 estava configurada como entrada, e o diagnóstico expirou sem heartbeat. SITL também não pôde ser executado porque o WSL dispõe apenas de `docker-desktop`, sem distribuição ArduPilot/MAVProxy. As três variáveis MapTiler ainda compartilham a mesma chave exposta; crie substitutas separadas/restritas, rebuild/teste e só então revogue a antiga. Consulte a [matriz de integrações](docs/INTEGRATION_STATUS.md) para os limites literais de evidência e as ações restantes.
