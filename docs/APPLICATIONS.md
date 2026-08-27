# Aplicações

## Matriz de responsabilidade

| Aplicação | Pode | Não pode | Porta padrão |
|---|---|---|---|
| Flutter Android/Web | fluxo do cliente, ponto mundial, pedido, tracking | admin, altitude, MAVLink | dispositivo ou Web 5174 |
| Admin React | decisões, revisão, checklist, monitoramento | banco direto, MAVLink direto | 5173 |
| FastAPI | regras, persistência, auditoria, WebSocket | abrir serial/UDP do veículo | 8000 |
| PostgreSQL/PostGIS | estado transacional/geográfico | regra de interface/voo | 5432 |
| Drone gateway | MAVLink, upload, telemetria, RTL controlado | banco, decisões de pedido | processo local |
| Mission Planner | revisão, configuração, calibração, operação | fonte de regra de pedido | Windows |
| SITL | regressão ArduPilot | provar hardware | WSL 2/local |

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python scripts/seed.py
.\.venv\Scripts\uvicorn app.main:app --reload
```

O backend é a fonte de verdade de identidade, pedido, missão e autorização. `/health` não consulta dependências; `/ready` verifica banco.

## Painel administrativo

```powershell
cd admin_web
npm.cmd install
npm.cmd run dev
```

`VITE_API_BASE_URL` aponta para a API. Modo demo, quando existente, deve ser explicitamente ativado e visualmente identificado; ele não substitui o fluxo integrado.

O mapa administrativo usa MapLibre GL JS e o estilo `MAPTILER_STYLE_URL`. `MAPTILER_WEB_API_KEY` é incorporada ao bundle, deve ser restrita pelas origens autorizadas e nunca deve ser confundida com a credencial de servidor. O admin não usa `iframe` nem Static Maps.

## Aplicativo Flutter (Web e Android)

```powershell
.\scripts\start_mobile_web.ps1
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -MapTilerConfigured
```

O perfil `local_web` usa `http://localhost:8000` e publica em `http://localhost:5174`; no emulador Android, `10.0.2.2` alcança o host. Dispositivo físico exige IP LAN explícito e a API exposta conscientemente com `API_BIND_ADDRESS=0.0.0.0`.

`MAP_PROVIDER=maptiler` seleciona a integração. As chaves `MAPTILER_WEB_API_KEY`, `MAPTILER_ANDROID_API_KEY` e `MAPTILER_SERVER_API_KEY` ficam somente no ambiente/configuração local, nunca no Git. Web é restrita por origem; Android deve usar chave separada e só restringir o `User-Agent` depois de observá-lo/validá-lo no aparelho; servidor não é reutilizado nos clientes.

Para validar apenas o fallback de desenvolvimento, execute `.\scripts\start_mobile_web.ps1 -WithoutMapTiler`. Esse modo é identificado e não comprova cartografia nem libera checkout integrado.

## Gateway

```powershell
cd drone_gateway
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.main
```

`simulation` é o padrão. `sitl` usa UDP. No Windows, `direct` abre a porta configurada em `MAVLINK_CONNECTION`; `mission_planner_forward` recebe o mirror configurado em `MAVLINK_FORWARD_CONNECTION`. O valor legado `real` continua aceito, mas as duas topologias explícitas são preferidas.

Hardware inicia somente em recepção com `REAL_HARDWARE_ACKNOWLEDGED=false`. Upload, ARM normal, comandos e start são gates separados por `ALLOW_MISSION_UPLOAD`, `ALLOW_VEHICLE_ARM`, `ALLOW_FLIGHT_COMMANDS` e `ALLOW_MISSION_START`, todos falsos por padrão. ARM só entra pelo fluxo administrativo dedicado de uma missão `VERIFIED`, exige os três gates de atuação verdadeiros e confirmação por ACK + heartbeat; `START` continua separado e nunca arma implicitamente. `PAUSE`/`CONTINUE` exigem ACK e estado compatível. Consulte [setup Mission Planner/Pixhawk](MISSION_PLANNER_SETUP.md).

## Compose

`docker compose up --build` inicia banco, migração/seed, API e painel. O gateway fica em profile intencional:

```powershell
docker compose --profile gateway up --build
```

No profile Docker, modo e conexão vêm exclusivamente de `GATEWAY_CONTAINER_MAVLINK_MODE` e `GATEWAY_CONTAINER_MAVLINK_CONNECTION`. A configuração versionada usa `simulation` e `udp:0.0.0.0:14550`; o processo recusa `real`, `direct` ou `mission_planner_forward` quando `GATEWAY_RUNTIME=container`. Para `COM7` ou forwarding local no Windows, execute `scripts/start_gateway.ps1` no host; o container Linux não disputa a serial do Mission Planner. Testes automatizados nunca abrem hardware.

Para desenvolvimento completo, `scripts/start_development.ps1` sobe DB/backend/admin e inicia
Flutter Web em primeiro plano; gateway não inicia por padrão. O gateway simulado exige os dois
switches `-IncludeSimulationGateway -ConfirmSimulationGateway`. Use `-ValidateOnly` para validar
sem iniciar serviços. Hardware continua em um segundo terminal pelo launcher host.
