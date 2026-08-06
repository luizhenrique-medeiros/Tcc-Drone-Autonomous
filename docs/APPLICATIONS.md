# Aplicações

## Matriz de responsabilidade

| Aplicação | Pode | Não pode | Porta padrão |
|---|---|---|---|
| Flutter | fluxo do cliente, ponto, pedido, tracking | admin, altitude, MAVLink | dispositivo/emulador |
| Admin React | decisões, revisão, checklist, monitoramento | banco direto, MAVLink direto | 5174 local / 5173 no Compose |
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

## Aplicativo Android

```powershell
cd mobile
..\flutter\bin\flutter.bat pub get
..\flutter\bin\flutter.bat run
```

No emulador Android, `10.0.2.2` alcança o host. A chave Google fica em configuração local Android, nunca no Dart ou Git.

## Gateway

```powershell
cd drone_gateway
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.main
```

`simulation` é padrão. `sitl` usa conexão UDP configurada, mas só inicia uma missão quando o operador define explicitamente `ALLOW_MISSION_START=true`. `real` exige também confirmação de ambiente, checklist e operador; nenhum modo arma no startup.

## Compose

`docker compose up --build` inicia banco, migração/seed, API e painel. O gateway fica em profile intencional:

```powershell
docker compose --profile gateway up --build
```

Não use o profile real durante testes automatizados.
