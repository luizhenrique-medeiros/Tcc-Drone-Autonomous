# Backend Drone Delivery

Monólito modular FastAPI responsável por autenticação, catálogo acadêmico, seleção exata do
ponto de entrega, pedidos, decisões administrativas, missões Mission Planner, autorização de
voo separada, comunicação exclusiva do gateway, telemetria e auditoria.

Produtos e a escolha de pagamento são simulações acadêmicas. Coordenadas, decisões,
autorizações, missões e telemetria são persistidas. O backend não abre conexão MAVLink e não
arma o veículo.

## Executar

Requer Python 3.13 e PostgreSQL com PostGIS para o ambiente integrado.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload
```

`AUTO_CREATE_SCHEMA=true` existe apenas para desenvolvimento/testes rápidos. Nos ambientes
integrados, use `AUTO_CREATE_SCHEMA=false` e Alembic.

## Segurança e fluxo

- `POST /api/v1/auth/register` sempre cria `CUSTOMER`; o primeiro `ADMIN` vem do seed
  controlado por ambiente.
- Aprovar `/admin/orders/{id}/approve` nunca autoriza voo.
- Uma missão deve ser exportada/revisada e chegar a `READY_FOR_AUTHORIZATION`.
- `/admin/missions/{id}/authorize-flight` exige snapshot recente e saudável, checklist e área
  controlada; a autorização expira, fica presa ao hash/versão e é consumida no claim.
- Endpoints `/gateway/*` exigem `X-Gateway-API-Key`, independente do JWT.
- Abortamento e RTL viram comandos pendentes; o backend espera confirmação real do gateway.
- Health e telemetria preservam `null` para dados MAVLink ainda não recebidos e expõem
  `source`, `received_at` e `is_stale`; a elegibilidade é bloqueada quando a fonte é `UNKNOWN`.
- `recorded_at` é o horário da amostra informado pelo gateway, enquanto `received_at` é a
  recepção no backend. A leitura recalcula expiração com `HEARTBEAT_TIMEOUT_SECONDS`.

WebSockets aceitam autenticação somente pela primeira mensagem
`{"type":"AUTH","token":"<jwt>"}`. Tokens em query parameters são deliberadamente
ignorados para não aparecerem em URLs e logs de acesso.

## Validar

```powershell
ruff check .
ruff format --check .
pytest
alembic upgrade head
```

O teste automatizado usa SQLite apenas como substituto rápido de persistência. A migração
PostgreSQL cria `postgis`, colunas `geography(POINT,4326)` e índice espacial GiST.

## Rotação da senha administrativa

O seed não altera uma conta existente. Para substituir uma senha inicial insegura, use o
prompt interativo (a senha não aparece na linha de comando):

```powershell
docker compose exec backend python scripts/rotate_admin_password.py `
  --email admin@example.local
```

Depois atualize `ADMIN_INITIAL_PASSWORD` no `.env` local para o mesmo valor antes de executar
o smoke. `ADMIN_NEW_PASSWORD` existe apenas para automação controlada; prefira o prompt.
