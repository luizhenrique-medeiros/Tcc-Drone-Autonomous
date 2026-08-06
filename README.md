# DEVcore — entrega por drone via coordenadas

Protótipo acadêmico de um sistema de entrega por drone no qual o cliente escolhe o ponto exato em um aplicativo Android, um administrador aprova o pedido e, em uma segunda etapa independente, autoriza uma missão revisada para execução pelo gateway MAVLink.

> **Segurança:** este repositório não autoriza operação comercial nem substitui avaliação aeronáutica. O modo padrão é simulado. Conectar uma Pixhawk, armar motores ou voar exige operador responsável, área controlada, checklist, failsafes e evidência manual. Nenhum health check arma ou inicia o veículo.

## O que é real e o que é simulado

| Parte | Implementação | Limite atual |
|---|---|---|
| Cadastro, autenticação e papéis | API real | Administrador criado somente por seed/CLI |
| Coordenadas e pedidos | API e persistência reais | Google Maps depende de chave configurada |
| Catálogo | Dados acadêmicos | Produtos e avaliações não são comerciais |
| Pagamento | Escolha simulada | Nenhum dado de cartão é coletado ou processado |
| Aprovação e autorização | Duas ações e endpoints distintos | Exigem papel `ADMIN` e auditoria |
| Missão | Waypoints e arquivo QGC WPL 110 | Revisão humana no Mission Planner continua obrigatória |
| Gateway | Modo fake/SITL e adaptação MAVLink | O modo real nunca é ativado implicitamente |
| Pixhawk 6C e voo | Preparação de software/documentação | Só pode ser marcado validado após ensaio real documentado |

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
- `mobile/`: aplicativo Flutter Android e design system derivado das referências.
- `drone_gateway/`: processo Python separado; único componente que fala MAVLink.
- `docs/`: requisitos, arquitetura, design, mapas, hardware e operação segura.
- `infrastructure/`: inicialização do PostgreSQL/PostGIS.
- `scripts/`: comandos locais reproduzíveis para Windows e WSL 2.

O diretório `flutter/`, quando presente localmente, é um SDK de desenvolvimento e fica ignorado pelo Git; não faz parte do produto.

## Pré-requisitos

- Python 3.13;
- Docker Desktop com Compose;
- Node.js 22 ou superior;
- Flutter/Dart compatível com o `pubspec.yaml` e Android SDK;
- WSL 2 e ArduPilot SITL para testes MAVLink;
- Mission Planner e Pixhawk 6C apenas para as etapas controladas de integração real.

## Configuração e execução

1. Copie `.env.example` para `.env` e troque todos os valores `change_me`.
2. Nunca versione `.env` ou chaves do Google Maps.
3. Para a pilha de API, banco e painel:

```powershell
docker compose up --build
```

Para incluir o gateway determinístico no teste ponta a ponta:

```powershell
docker compose --profile gateway up --build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1
```

4. Para executar componentes separadamente:

```powershell
.\scripts\start_backend.ps1
.\scripts\start_admin.ps1
.\scripts\start_mobile.ps1
.\scripts\start_gateway.ps1
```

O gateway inicia em `MAVLINK_MODE=simulation`. Consulte [Desenvolvimento](docs/DEVELOPMENT.md) e [Aplicações](docs/APPLICATIONS.md) para os comandos e portas.

## Testes

```powershell
.\scripts\test_all.ps1
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
- [Fluxo administrativo](docs/ADMIN_FLOW.md)
- [Mission Planner](docs/MISSION_PLANNER_INTEGRATION.md)
- [Protocolo do gateway](docs/DRONE_PROTOCOL.md)
- [Hardware](docs/HARDWARE.md)
- [Checklist pré-voo](docs/PREFLIGHT_CHECKLIST.md)
- [Segurança](docs/SECURITY.md)

## Estado de validação

Em 2026-08-06, as suítes locais, os builds, a migração PostGIS e o fluxo completo em `simulation` foram executados com sucesso. Google Maps com chave real, instalação do APK, SITL, bancada Pixhawk e voo real continuam **não validados**. Código implementado, teste automatizado, simulação, SITL, bancada e voo são evidências diferentes; consulte a matriz e os números exatos no [Plano de testes](docs/TEST_PLAN.md).
