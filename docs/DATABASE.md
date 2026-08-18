# Banco de dados

## Convenções

PostgreSQL + PostGIS, tabelas/colunas `snake_case`, UUID para entidades principais, timestamps UTC e preços `NUMERIC(12,2)`. A migração habilita `postgis`; seeds contêm dados, não mudanças estruturais.

## Entidades

| Tabela | Dados centrais | Regras |
|---|---|---|
| `users` | role, name, email, phone, password_hash, active | email único; hash nunca sai da API |
| `products` | name, description, price, category, image_url, available | catálogo acadêmico; imagem opcional |
| `saved_locations` | user, name, final, `location`, referência, instruções, precisão, provider/tipo, confirmações | até três atalhos confirmados por cliente; endereço opcional |
| `delivery_points` | aproximação, final, `location`, fonte, confirmações | snapshot do pedido; `geography(Point,4326)` criado do final |
| `orders` | customer, point, status, forma simulada, totais | uma decisão vigente por submissão |
| `order_items` | product_id, snapshot name/price, quantity | quantidade positiva |
| `admin_decisions` | order, admin, decision, reason | rejeição exige motivo |
| `missions` | order, version, origin/destination, altitude, distance, state, file/hash | uma ativa por pedido |
| `mission_waypoints` | sequence, command, lat/lon/alt, params | sequência única por missão |
| `flight_authorizations` | mission/version, admin, status, expiry, used_at, checklist | uso único e expiração |
| `vehicles` | identifier, name, autopilot, status, last_seen | identificador único |
| `vehicle_health_snapshots` | source, heartbeat, GPS/bateria/modo/armed, diagnóstico de conexão e três gates | campos físicos nulos quando desconhecidos; frescor derivado |
| `gateway_commands` | mission, action, requester, gateway, status, timestamps e resultado | `START`, `PAUSE`, `CONTINUE`, RTL e ABORT persistidos/ACK-aware |
| `telemetry_logs` | mission/vehicle, source, received_at, point, altitude, speed, battery, GPS, mode, armed | retenção/amostragem configurável; campos físicos anuláveis |
| `system_events` | actor/order/mission/vehicle, type, severity, message, metadata | event_id único para deduplicação |

`Meus pedidos` não cria `order_history`. O status atual permanece em `orders`; as datas intermediárias vêm de uma whitelist de `system_events` vinculados ao pedido e são expostas ao cliente por um DTO sanitizado. Ausência de evento significa ausência de timestamp, nunca uma data inferida de `updated_at`.

`order_items` mantém os snapshots comerciais de nome e preço. Categoria e imagem são consultadas do produto relacionado e podem ser nulas ou mudar no catálogo; a interface sempre oferece fallback visual. O painel administrativo consulta a autorização mais recente da missão na tabela existente `flight_authorizations`, incluindo o administrador real e o estado de consumo, sem duplicar esse registro em `missions`.

`saved_locations` possui `id UUID`, `user_id UUID NOT NULL`, `name VARCHAR(40) NOT NULL`, `final_latitude NUMERIC(10,7)`, `final_longitude NUMERIC(10,7)`, `location geography(Point,4326)`, `address_reference` opcional, `instructions` opcional, `accuracy_meters` opcional, `map_provider VARCHAR(40) NOT NULL`, `map_type VARCHAR(30) NOT NULL`, `region_confirmed BOOLEAN NOT NULL`, `exact_point_selected BOOLEAN NOT NULL`, `user_confirmed BOOLEAN NOT NULL`, `user_confirmed_safe_area BOOLEAN NOT NULL` e timestamps UTC. O nome aparado possui de 1 a 40 caracteres; as coordenadas obedecem às mesmas constraints mundiais de `delivery_points`, e checks restringem `map_type` a `hybrid|satellite` e mantêm as quatro confirmações verdadeiras. A aplicação exige que essa evidência venha do fluxo real de mapa e quantiza coordenadas uma única vez em sete casas antes de preencher tanto as colunas numéricas quanto o ponto PostGIS. A FK aponta para `users`, e um índice B-tree em `user_id` atende listagem e contagem. Não se cria índice espacial GiST para essa tabela sem uma consulta espacial real que o justifique.

`SavedLocation` não substitui `DeliveryPoint`. Quando `OrderCreate` usa `saved_location_id`, o serviço também exige `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true`, copia os valores do atalho — inclusive `map_provider` e `map_type` — para uma nova linha de `delivery_points`, aplica as confirmações atuais ao snapshot, define a origem interna como `SAVED_POINT` e cria `orders` na mesma transação. Nenhum provider, tipo ou booleano é inventado pelo serviço. O pedido armazena apenas a FK para essa cópia; não depende da linha mutável de `saved_locations`.

## Geografia

As coordenadas finais são a autoridade. O ponto é persistido conceitualmente como:

```sql
ST_SetSRID(ST_MakePoint(final_longitude, final_latitude), 4326)::geography
```

Longitude vem primeiro no construtor PostGIS tanto em `saved_locations` quanto em `delivery_points`. Constraints validam latitude/longitude, e o índice GiST de `delivery_points` sustenta consultas geográficas operacionais quando necessárias; ele não impõe cobertura no checkout. Aproximação e endereço continuam disponíveis para auditoria, nunca para a rota final.

## Relacionamentos e exclusão

- usuário → localizações salvas: o proprietário é obrigatório e indexado; a política de remoção da conta não apaga snapshots de pedidos;
- usuário → pontos/pedidos: restrito enquanto houver auditoria;
- localização salva → pedido: não há FK histórica; os dados são copiados para `delivery_points`;
- pedido → itens/decisões/missão: registros históricos não usam cascade destrutivo de produção;
- missão → waypoints/autorizações/telemetria: preservados conforme política de retenção;
- produto removido não apaga snapshot do item.

## Concorrência e integridade

- a criação de `saved_locations` abre uma transação, executa `SELECT id FROM users WHERE id = :current_user_id FOR NO KEY UPDATE`, conta as linhas daquele usuário e insere apenas quando o total é menor que três;
- o lock da linha de `users` serializa somente criações concorrentes do mesmo cliente. O count e o insert fazem parte da mesma transação; atingir três produz `409/SAVED_LOCATION_LIMIT_REACHED` sem substituir dados;
- `OrderCreate` valida a exclusividade entre `delivery_point_id` e `saved_location_id`, a propriedade do recurso escolhido e, no caminho salvo, as duas confirmações atuais verdadeiras; snapshot e pedido são criados atomicamente com provider/tipo salvos e sem evidência sintetizada;
- atualizar ou excluir `saved_locations` não atualiza nem exclui `delivery_points` referenciados por pedidos;
- restrição única em `missions.order_id` mantém uma única missão por pedido;
- claim bloqueia a linha ou usa atualização condicional por estado/versão;
- `event_id` deduplica eventos, e a chave idempotente é reservada antes dos efeitos na mesma transação;
- autorização muda de `ACTIVE` para `CONSUMED` atomicamente;
- amostra só atualiza snapshot se `occurred_at` for posterior.

O JSON auditável de `flight_authorizations.checklist` persiste exatamente `area_and_conditions_clear`, `aircraft_and_payload_inspected` e `operator_ready`. Expiração ou revogação atualiza o registro e cria `FLIGHT_AUTHORIZATION_EXPIRED` ou `FLIGHT_AUTHORIZATION_REVOKED` em `system_events`; nenhuma tabela adicional de autorização foi necessária.

`vehicle_health_snapshots` também conserva `connection_state`, modo/topologia, endpoint, porta/baud upstream, system/component alvo, idade e instante do último heartbeat, posição disponível, erro e os booleanos independentes `mission_upload_enabled`, `flight_commands_enabled` e `mission_start_enabled`. O último deles nunca é inferido do gate geral de comandos.

## Migrações e seed

```powershell
cd backend
alembic upgrade head
python scripts/seed.py
```

O seed é idempotente e cria produtos de demonstração e, somente quando variáveis explícitas existem, o primeiro administrador. Nunca usa uma senha fixa silenciosa. Downgrade não apaga evidência em ambiente real sem backup e procedimento aprovado.

`0004_saved_locations` cria `saved_locations`, sua FK, índice por `user_id`, constraints geográficas, provider/tipo de mapa, quatro flags de confirmação e timestamps. Ela não converte automaticamente `delivery_points` antigos em atalhos: pontos existentes continuam snapshots/auditoria, e nenhum dado fictício ou confirmação presumida é criado para preencher o limite.

`0005_vehicle_integration_health` adiciona os diagnósticos de conexão, posição e os gates de upload/comandos ao snapshot do veículo. `0006_mission_start_health`, head aplicado em 17 de agosto de 2026, adiciona `mission_start_enabled` como gate independente. O downgrade de cada revisão remove apenas suas próprias colunas; em ambiente real, faça backup antes de qualquer downgrade.

`0003_schema_names` normaliza, de forma idempotente, nomes de índices e constraints encontrados em volumes antigos criados antes da cadeia Alembic atual. Em banco novo ela não altera a estrutura funcional. Valide com `alembic check`; os três tipos `geography` e os enums operacionais não nativos possuem comparação explícita para evitar falsos drifts.

## Retenção

Telemetria não deve crescer sem limite. A API persiste no intervalo configurado e mantém snapshot atual separado; política de arquivamento/exclusão será aprovada antes de qualquer demonstração longa. Eventos operacionais têm retenção maior que amostras e não armazenam MAVLink bruto indiscriminadamente.
