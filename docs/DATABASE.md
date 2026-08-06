# Banco de dados

## Convenções

PostgreSQL + PostGIS, tabelas/colunas `snake_case`, UUID para entidades principais, timestamps UTC e preços `NUMERIC(12,2)`. A migração habilita `postgis`; seeds contêm dados, não mudanças estruturais.

## Entidades

| Tabela | Dados centrais | Regras |
|---|---|---|
| `users` | role, name, email, phone, password_hash, active | email único; hash nunca sai da API |
| `products` | name, description, price, category, available | catálogo acadêmico |
| `delivery_points` | aproximação, final, `location`, fonte, confirmações | `geography(Point,4326)` criado do final |
| `orders` | customer, point, status, forma simulada, totais | uma decisão vigente por submissão |
| `order_items` | product_id, snapshot name/price, quantity | quantidade positiva |
| `admin_decisions` | order, admin, decision, reason | rejeição exige motivo |
| `missions` | order, version, origin/destination, altitude, distance, state, file/hash | uma ativa por pedido |
| `mission_waypoints` | sequence, command, lat/lon/alt, params | sequência única por missão |
| `flight_authorizations` | mission/version, admin, status, expiry, used_at, checklist | uso único e expiração |
| `vehicles` | identifier, name, autopilot, status, last_seen | identificador único |
| `vehicle_health_snapshots` | heartbeat, GPS, satellites, EKF, battery, mode, armed | dados normalizados e timestamp |
| `telemetry_logs` | mission/vehicle, point, altitude, speed, battery, GPS, mode, armed | retenção/amostragem configurável |
| `system_events` | actor/order/mission/vehicle, type, severity, message, metadata | event_id único para deduplicação |

## Geografia

As coordenadas finais são a autoridade. O ponto é persistido conceitualmente como:

```sql
ST_SetSRID(ST_MakePoint(final_longitude, final_latitude), 4326)::geography
```

Longitude vem primeiro no construtor PostGIS. Constraints validam latitude/longitude, e índice GiST só é criado porque consultas de cobertura/distância usam `location`. Aproximação e endereço continuam disponíveis para auditoria, nunca para a rota final.

## Relacionamentos e exclusão

- usuário → pontos/pedidos: restrito enquanto houver auditoria;
- pedido → itens/decisões/missão: registros históricos não usam cascade destrutivo de produção;
- missão → waypoints/autorizações/telemetria: preservados conforme política de retenção;
- produto removido não apaga snapshot do item.

## Concorrência e integridade

- índice parcial/validação transacional impede duas missões ativas por pedido;
- claim bloqueia a linha ou usa atualização condicional por estado/versão;
- `event_id` e idempotency key evitam duplicidade;
- autorização muda de `ACTIVE` para `CONSUMED` atomicamente;
- amostra só atualiza snapshot se `occurred_at` for posterior.

## Migrações e seed

```powershell
cd backend
alembic upgrade head
python scripts/seed.py
```

O seed é idempotente e cria produtos de demonstração e, somente quando variáveis explícitas existem, o primeiro administrador. Nunca usa uma senha fixa silenciosa. Downgrade não apaga evidência em ambiente real sem backup e procedimento aprovado.

## Retenção

Telemetria não deve crescer sem limite. A API persiste no intervalo configurado e mantém snapshot atual separado; política de arquivamento/exclusão será aprovada antes de qualquer demonstração longa. Eventos operacionais têm retenção maior que amostras e não armazenam MAVLink bruto indiscriminadamente.
