# DEVcore — entrega por drone via coordenadas

Protótipo acadêmico de um sistema de entrega por drone no qual o cliente escolhe o ponto exato no aplicativo Flutter Android/Web, um administrador aprova o pedido e, em uma segunda etapa independente, autoriza uma missão revisada para execução pelo gateway MAVLink.

> **Segurança:** este repositório não autoriza operação comercial nem substitui avaliação aeronáutica. O modo padrão é simulado. Conectar uma Pixhawk, armar motores ou voar exige operador responsável, área controlada, checklist, failsafes e evidência manual. Nenhum health check arma ou inicia o veículo.

## O que é real e o que é simulado

| Parte | Implementação | Limite atual |
|---|---|---|
| Cadastro, autenticação e papéis | API real | Administrador criado somente por seed/CLI |
| Coordenadas e pedidos | API e persistência reais | MapTiler depende de chave configurada |
| Catálogo | Dados acadêmicos | Produtos e avaliações não são comerciais |
| Pagamento | Escolha simulada | Nenhum dado de cartão é coletado ou processado |
| Aprovação e autorização | Duas ações e endpoints distintos | Exigem papel `ADMIN` e auditoria |
| Missão | Waypoints e arquivo QGC WPL 110 | Revisão humana no Mission Planner continua obrigatória |
| Gateway | Simulação, SITL, serial direta e forwarding do Mission Planner | Upload e comandos possuem gates independentes, falsos por padrão |
| Pixhawk 6C e voo | COM7/57600 identificados; heartbeat real recebido anteriormente em modo direto | No estado atual a COM7 está ausente; forwarding, upload, armamento e voo não foram validados |

## Fluxo principal

```text
Flutter → FastAPI/PostGIS → aprovação do pedido no React
        → geração e revisão da missão → checklist e autorização do voo
        → gateway → SITL ou Pixhawk/ArduPilot → telemetria → Flutter/React
```

A aprovação do pedido apenas permite preparar a missão. O upload/execução exige outra autorização, vinculada à versão da missão, de uso único e com validade curta.

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
- WSL 2 e ArduPilot SITL para testes MAVLink;
- Mission Planner e Pixhawk 6C apenas para as etapas controladas de integração real.

## Configuração e execução

1. Copie `.env.example` para `.env` e troque todos os valores `change_me`.
2. Nunca versione `.env` ou chaves do MapTiler.
3. Para a pilha de API, banco e painel:

```powershell
docker compose up -d --build db backend admin
Start-Process 'http://localhost:5173'
```

O admin fica em `http://localhost:5173`, a API em `http://localhost:8000` e o Swagger em `http://localhost:8000/docs`.

Para abrir no navegador o mesmo frontend Flutter usado pelo APK:

```powershell
.\scripts\start_mobile_web.ps1
```

Ele fica em `http://localhost:5174`, usa hot reload e lê a configuração Web do MapTiler no `.env` sem imprimir a chave. O painel administrativo continua sendo outra aplicação, em `http://localhost:5173`.

Para incluir o gateway determinístico no teste ponta a ponta:

```powershell
docker compose --profile gateway up --build
$env:ADMIN_INITIAL_PASSWORD='SENHA_LOCAL'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1 -ConfirmSimulationMutation
```

4. Para executar componentes separadamente:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_admin.ps1
.\scripts\start_mobile.ps1
.\scripts\start_gateway.ps1
```

O padrão versionado é `MAVLINK_MODE=simulation`. Para o primeiro ensaio físico, execute antes `scripts\start_gateway.ps1 -DiagnoseOnly`: ele apenas recebe, mostra heartbeat/telemetria realmente observados e termina. Os modos `direct` e `mission_planner_forward`, a COM7/57600 e as travas independentes de upload, comandos e início estão em [Setup Mission Planner/Pixhawk](docs/MISSION_PLANNER_SETUP.md).

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

## Estado de validação

Em 17 de agosto de 2026, a bateria orquestrada terminou com exit 0 em 107,5 s e aprovou **275 testes**: backend 53, gateway 57, admin 67 e Flutter 98; o backend teve ainda um teste opt-in ignorado. O resolvedor selecionou explicitamente o SDK oficial global stable Flutter 3.47.0/Dart 3.13.0, e format/analyze/test do Flutter passaram. Também passaram os builds Docker, Vite, Flutter Web, dry run Wasm e APK debug. A migração aplicada é `0006_mission_start_health`.

O Web e o APK debug integrados foram regenerados com `DEMO_MODE=false` e a configuração MapTiler do `.env` ignorado. O APK atual tem 195.236.488 bytes e SHA-256 `202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`; nenhum valor secreto é documentado.

Banco, API e admin estão disponíveis em loopback nas portas 5432, 8000 e 5173; o build Flutter Web está servido em 5174. O login administrativo integrado não foi repetido porque a senha do `.env` diverge do hash persistido; não redefina a conta sem autorização. O controlador visual do navegador estava indisponível, portanto respostas HTTP 200 e builds desta rodada não são apresentados como novo smoke visual de mapa/UI.

Dois diagnósticos passivos anteriores receberam heartbeat real da Pixhawk em `COM7` a 57600, `sysid=1`, `compid=1`, modo `STABILIZE` e `armed=false`; um ciclo limitado também enviou sete heartbeats normalizados ao backend. Depois da desconexão física, a COM7 deixou de existir e o snapshot atual registra erro/offline. Forwarding do Mission Planner, GPS/bateria/EKF ao vivo pelo gateway, SITL, upload, armamento, motores e voo continuam **não validados**. As três flags `ALLOW_MISSION_UPLOAD`, `ALLOW_FLIGHT_COMMANDS` e `ALLOW_MISSION_START` permanecem falsas. A chave MapTiler exposta deve ser rotacionada. Consulte a [matriz de integrações](docs/INTEGRATION_STATUS.md).
