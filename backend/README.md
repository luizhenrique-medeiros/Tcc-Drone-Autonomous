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
