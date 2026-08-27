# Contrato HTTP e WebSocket

Base: `/api/v1`. Respostas JSON usam UTC ISO-8601, UUID em texto e dinheiro como decimal serializado em string.

## Autenticação

`Authorization: Bearer <JWT>` para cliente/admin. O gateway usa `X-Gateway-API-Key` junto de
`X-Gateway-ID`; o backend vincula ambos ao `GATEWAY_ID` configurado e rejeita ID divergente em
header, query ou payload. Cadastro ignora/rejeita papel enviado pelo público. Erro padrão:

```json
{"code":"ORDER_INVALID_STATE","detail":"Pedido não aguarda aprovação.","fields":{"status":"APPROVED"}}
```

## Cliente

| Método e rota | Autorização | Resultado |
|---|---|---|
| `POST /auth/register` | pública | cliente |
| `POST /auth/login` | pública | access token |
| `GET /auth/me` | JWT | identidade sem hash |
| `GET /products` | JWT | lista com `limit`/`offset` |
| `GET /products/{id}` | JWT | detalhe |
| `GET /maps/places/search` | JWT | sugestões aproximadas |
| `GET /maps/geocode` | JWT | região aproximada por exatamente um de `address` ou `place_id` |
| `GET /maps/reverse-geocode` | JWT | rótulo auxiliar |
| `POST /delivery-points/validate` | cliente | faixa mundial, confirmações e distância informativa, sem persistir |
| `POST /delivery-points` | cliente | ponto final confirmado |
| `GET /delivery-points` | cliente | próprios pontos |
| `GET /saved-locations` | cliente | zero a três atalhos próprios |
| `POST /saved-locations` | cliente | novo atalho confirmado, sujeito ao limite transacional |
| `GET /saved-locations/{id}` | proprietário | detalhe do atalho |
| `PATCH /saved-locations/{id}` | proprietário | altera nome, ponto ou dados auxiliares |
| `DELETE /saved-locations/{id}` | proprietário | remove somente o atalho |
| `POST /orders` | cliente | rascunho e snapshots |
| `GET /orders` | cliente | próprios pedidos com `limit`/`offset` e grupo opcional |
| `GET /orders/{id}` | proprietário | detalhe com milestones sanitizados |
| `POST /orders/{id}/submit` | proprietário | `PENDING_ADMIN_APPROVAL` |
| `POST /orders/{id}/cancel` | proprietário | cancelamento permitido |

As três rotas `/maps/*` são o proxy autenticado para a Geocoding API do MapTiler. Pesquisa exige pelo menos três caracteres e aplica autocomplete; geocode recebe exatamente um de `address` ou `place_id`; reverse geocode recebe latitude/longitude, mas o adaptador externo envia `longitude,latitude`. A resposta externa GeoJSON é convertida aos DTOs internos e nunca expõe `MAPTILER_SERVER_API_KEY`.

Configuração ausente retorna `503/MAPS_NOT_CONFIGURED`; recusa, quota, timeout, rede ou resposta externa inválida retornam `502/MAPS_PROVIDER_ERROR`; consulta inválida retorna `422/MAPS_QUERY_INVALID`. Resultado vazio de geocode/reverse geocode retorna `404`, sem fabricar endereço.

## Localizações salvas

Todas as rotas `/saved-locations` exigem JWT de `CUSTOMER`. O servidor deriva o proprietário de `current_user.id`; os contratos de criação e atualização não aceitam `user_id` para definir propriedade. Buscar, editar ou excluir um identificador inexistente ou de outro cliente devolve o mesmo `404/NOT_FOUND`.

O corpo de criação contém:

```json
{
  "name": "Casa",
  "final_latitude": -23.1175,
  "final_longitude": -46.5502,
  "address_reference": "Entrada pelo portão lateral",
  "instructions": "Usar a área aberta sinalizada.",
  "accuracy_meters": 5,
  "map_provider": "maptiler",
  "map_type": "hybrid",
  "region_confirmed": true,
  "exact_point_selected": true,
  "user_confirmed": true,
  "user_confirmed_safe_area": true
}
```

`name` é obrigatório, aparado e possui de 1 a 40 caracteres. Latitude/longitude são obrigatórias e seguem a faixa mundial; `address_reference`, `instructions` e `accuracy_meters` são opcionais. `map_provider` identifica o provider realmente renderizado, e `map_type` aceita somente `hybrid` ou `satellite`. A criação exige `region_confirmed`, `exact_point_selected`, `user_confirmed` e `user_confirmed_safe_area` verdadeiros e provenientes do mesmo fluxo de mapa; o servidor não os preenche por default. A ausência de endereço textual não impede criação. A resposta inclui `id`, `user_id` derivado, coordenadas, provider/tipo, as quatro flags, dados opcionais e timestamps; o valor PostGIS permanece interno. `PATCH` recebe somente os campos editáveis. Nome, instruções e referência podem mudar isoladamente; alterar qualquer coordenada, provider, tipo ou confirmação exige reenviar o conjunto completo de coordenadas, mapa e quatro confirmações verdadeiras produzido pela nova revisão. `DELETE` retorna `204` e não altera `DeliveryPoint` nem pedido.

`POST /saved-locations` bloqueia a linha do cliente com `SELECT ... FOR NO KEY UPDATE`, conta os atalhos e insere na mesma transação. Ao já existirem três, retorna:

```json
{
  "code": "SAVED_LOCATION_LIMIT_REACHED",
  "detail": "Você pode salvar no máximo 3 localizações.",
  "fields": {}
}
```

O status é `409`. Requisições concorrentes para o mesmo cliente passam pelo mesmo lock e não conseguem criar uma quarta localização. A criação aceita `Idempotency-Key`; repetir a mesma chave e corpo devolve o resultado original sem consumir outra vaga, enquanto reutilizar a chave com outro corpo retorna conflito.

## Ponto de entrega e criação do pedido

Exemplo mínimo de ponto:

```json
{
  "searched_address": "Rua de referência, 100",
  "address_reference": "Entrada aberta ao lado do campo",
  "selection_source": "MANUAL_MAP_SELECTION",
  "approximate_latitude": -23.1170,
  "approximate_longitude": -46.5500,
  "final_latitude": -23.1175,
  "final_longitude": -46.5502,
  "instructions": "Depositar no marcador sinalizado.",
  "region_confirmed": true,
  "exact_point_selected": true,
  "user_confirmed": true,
  "user_confirmed_safe_area": true,
  "map_provider": "maptiler",
  "map_type": "hybrid",
  "accuracy_meters": 5
}
```

O request de pedido aceita apenas enum da forma simulada, itens e exatamente um de `delivery_point_id` ou `saved_location_id`. Não aceita dados de cartão. Informar ambos ou nenhum retorna erro de validação. No caminho salvo, o corpo é semelhante a:

```json
{
  "payment_method": "PIX",
  "items": [
    {
      "product_id": "11111111-1111-4111-8111-111111111111",
      "quantity": 1
    }
  ],
  "saved_location_id": "22222222-2222-4222-8222-222222222222",
  "saved_location_review_confirmed": true,
  "saved_location_safe_area_confirmed": true
}
```

Quando `saved_location_id` é usado, os dois booleanos são obrigatórios e devem ser `true`, pois descrevem a revisão feita naquele checkout; a evidência antiga da criação do atalho não substitui essa confirmação atual.

Com `delivery_point_id`, o ponto confirmado deve pertencer ao cliente. Com `saved_location_id`, o backend carrega o atalho próprio e, na mesma transação da criação do pedido, cria um novo `DeliveryPoint` com os valores copiados e `selection_source=SAVED_POINT`. O snapshot conserva `map_provider` e `map_type` do atalho e registra as confirmações da revisão atual recebidas no request; nenhuma flag ou proveniência é fabricada por constante. A resposta e todas as leituras posteriores usam essa cópia; editar ou excluir o atalho não muda o pedido.

Se o cliente ajustou no mapa uma localização salva apenas para o pedido, o aplicativo persiste o ponto ajustado como `DeliveryPoint` e envia `delivery_point_id`; não atualiza `SavedLocation`. Se optar por transformar um novo ponto manual em atalho, chama `POST /saved-locations` somente depois de o pedido ser criado. Falha, offline ou `SAVED_LOCATION_LIMIT_REACHED` nessa chamada posterior não reverte o pedido e não impede sua submissão.

`GET /orders` nunca aceita `user_id`: o proprietário vem do JWT. Rascunhos `DRAFT` ainda não submetidos são internos ao checkout e não entram na listagem. `group=all|active|history` permite paginação coerente; `all` prioriza estados ativos e, dentro de cada grupo, ordena por criação decrescente. A resposta conserva o padrão do projeto como lista e o cliente calcula `has_more` quando a página contém `limit` itens.

`GET /orders/{id}` retorna itens, valores, forma simulada, ponto final e `milestones`. Cada item inclui `category` e `image_url` reais do produto quando disponíveis; ausência ou falha da imagem usa o artwork local, sem fabricar URL. Cada milestone contém somente `event_type` permitido e `occurred_at`; mensagens, ator e metadados internos de `SystemEvent` não são expostos ao cliente. Evento inexistente não gera data estimada. Pedido de outro cliente recebe o mesmo `404` de um recurso inexistente.

Após as confirmações obrigatórias, qualquer latitude/longitude mundial válida é aceita no checkout. A validação retorna `within_coverage=true` e `max_distance_m=null` para indicar cobertura global; a distância continua disponível para auditoria. O limite operacional de missão é aplicado separadamente pelo gateway, antes de upload/início de voo.

Os POSTs de persistência do checkout aceitam `Idempotency-Key`. Repetir a mesma chave com o mesmo corpo devolve o resultado original; reutilizá-la com outro corpo devolve `409`.

## Administração

| Método e rota | Pré-condição |
|---|---|
| `GET /admin/orders` | `ADMIN` |
| `GET /admin/orders/{id}` | `ADMIN` |
| `POST /admin/orders/{id}/approve` | pendente |
| `POST /admin/orders/{id}/reject` | pendente + motivo |
| `POST /admin/orders/{id}/prepare-mission` | aprovado |
| `GET /admin/missions` | `ADMIN` |
| `GET /admin/missions/{id}` | `ADMIN` |
| `GET /admin/missions/{id}/export` | missão gerada |
| `POST /admin/missions/{id}/mark-under-review` | exportada |
| `POST /admin/missions/{id}/mark-reviewed` | em revisão |
| `POST /admin/missions/{id}/authorize-flight` | revisada + checklist + saúde |
| `POST /admin/missions/{id}/arm` | `VERIFIED`, reivindicada + ARM normal elegível |
| `GET /admin/missions/{id}/commands/{command_id}` | acompanhar o comando exato da missão |
| `POST /admin/missions/{id}/abort` | estado abortável |
| `POST /admin/missions/{id}/request-rtl` | execução/condição válida |
| `POST /admin/missions/{id}/commands/{action}` | `action=START|PAUSE|CONTINUE|RTL|ABORT`, estado compatível; `ARM` é recusado aqui |
| `GET /admin/vehicles` | `ADMIN` |
| `GET /admin/vehicles/{id}/health` | `ADMIN` |
| `GET /admin/events` | `ADMIN` e paginação |
| `GET /admin/telemetry` | `ADMIN`, filtro opcional por missão |

A autorização recebe veículo, operador, confirmação de área controlada e exatamente três confirmações auditáveis em `checklist`: `area_and_conditions_clear`, `aircraft_and_payload_inspected` e `operator_ready`. Não há booleanos técnicos preenchidos manualmente nem frase digitada; conexão, heartbeat, GPS, satélites, EKF, bateria, home, geofence, RTL, armamento e preflight vêm do snapshot real e são recalculados pelo servidor. O servidor vincula a autorização à versão e ao hash atuais da missão; ele nunca aceita resultado técnico enviado pelo navegador como forma de contornar as verificações.

O objeto de saúde inclui `authorization_limits` com `min_battery_percent`, `battery_warning_percent` e `min_gps_satellites`. Esses valores vêm da configuração efetiva do backend e são a fonte canônica usada pelo painel; contrato legado sem limites permanece bloqueante em vez de assumir números locais.

As respostas administrativas de missão incluem `authorization` com o último registro real, quando existente: identificadores da autorização e do administrador, nome real do administrador e operador, status, versão, emissão, expiração e consumo. Isso preserva a evidência após reload sem expor checklist bruto nem fabricar nomes no navegador.

`POST /admin/missions/{id}/authorize-flight` aceita `Idempotency-Key`: a chave é reservada na mesma transação antes dos efeitos, e repetir chave e corpo devolve a mesma autorização com `Idempotency-Replayed`. O painel conserva a chave da tentativa lógica enquanto a resposta for ambígua; uma chave diferente após a missão sair de `READY_FOR_AUTHORIZATION` retorna conflito.

`GET /admin/missions` e `GET /admin/missions/{id}` incluem a autorização mais recente quando ela existe, com administrador real, operador, status, versão e datas de emissão, expiração e consumo. Esse resumo administrativo não é enviado ao WebSocket do cliente.

No `claim`, o gateway precisa corresponder ao veículo autorizado. Mudanças saudáveis de telemetria, como pequenas variações de bateria ou satélites, não revogam a autorização por igualdade exata de amostra; qualquer falha atual nos limites técnicos, expiração ou alteração de versão/hash revoga a autorização, retorna a missão para nova autorização e registra o motivo em `SystemEvent`.

### Armamento normal dedicado

`POST /api/v1/admin/missions/{id}/arm` exige JWT `ADMIN`, header `Idempotency-Key` e exatamente este formato:

```json
{
  "reason": "Ensaio autorizado com operador presente.",
  "area_clear_confirmed": true,
  "operator_present_confirmed": true,
  "safety_switch_ready_confirmed": true
}
```

`reason` é aparado, obrigatório e possui de 10 a 1000 caracteres. Os três booleanos aceitam somente `true`; campo desconhecido, inclusive qualquer tentativa de `force` ou bypass, retorna `422`. Repetir a mesma chave e o mesmo corpo devolve a resposta original com `Idempotency-Replayed`; reutilizar a chave com outro corpo retorna conflito.

Antes de persistir `ARM`, o backend bloqueia a missão para serializar ações críticas e exige:

- missão `VERIFIED`, já reivindicada, com veículo e gateway correspondentes;
- último snapshot do mesmo veículo fresco, conectado, com heartbeat, origem `SITL` ou `HARDWARE_REAL` e `armed=false`;
- GPS/satélites, EKF, bateria, home/origem, geofence, RTL e preflight completos e dentro dos limites canônicos;
- `flight_mode=STABILIZE`;
- `vehicle_arm_enabled=true`, `flight_commands_enabled=true` e `mission_start_enabled=true`;
- ausência de outro comando crítico `PENDING` ou `ACKNOWLEDGED` para a missão.

Campo ausente, nulo, stale ou falso falha fechado com `409`; o navegador não pode fornecer resultados técnicos. O `202` devolve `{ "mission": AdminMissionRead, "command": GatewayCommandRead }` e significa apenas que a solicitação foi persistida. O painel acompanha o `command.id` exato por `GET /api/v1/admin/missions/{id}/commands/{command_id}`. A sequência auditável é `PENDING → ACKNOWLEDGED → COMPLETED|FAILED`; `FAILED` expõe `result_detail`, enquanto `COMPLETED` só é aceito depois de ACK MAVLink correlacionado e de um heartbeat novo, persistido pelo backend, com `armed=true`, origem permitida e identidade correta. ARM não inicia nem muda a missão para `EXECUTING`; `START` continua sendo request posterior. Não existe rearmamento automático após timeout, falha, restart ou desarmamento.

O endpoint genérico de comando aceita `SafetyActionRequest` opcional e `Idempotency-Key`. `START` só é criado em `VERIFIED`; `PAUSE`, durante estados físicos permitidos; `CONTINUE`, somente em `PAUSED`. O `202` significa que o pedido foi persistido, não que o autopiloto executou. O gateway ainda rejeita comando vencido, identidade de veículo divergente, snapshot/heartbeat/preflight inválido ou gate local fechado. Em especial, `START` requer `flight_commands_enabled=true`, `mission_start_enabled=true` e veículo já armado; ele nunca envia ARM implicitamente. O único caminho de armamento é o endpoint dedicado descrito acima.

## Gateway

| Método e rota | Semântica |
|---|---|
| `POST /gateway/heartbeat` | identidade, origem e snapshot normalizado; servidor define `received_at`/frescor |
| `GET /gateway/missions/authorized` | missões vigentes elegíveis |
| `POST /gateway/missions/{id}/claim` | consome autorização uma vez |
| `POST /gateway/missions/{id}/upload-status` | início/resultado do upload, deduplicado por `event_id` |
| `POST /gateway/missions/{id}/status` | transição física validada |
| `POST /gateway/missions/{id}/telemetry` | amostra normalizada com origem; desconhecidos permanecem nulos |
| `POST /gateway/missions/{id}/events` | evento com UUID deduplicável |
| `GET /gateway/commands/pending` | comandos ARM/`START`/`PAUSE`/`CONTINUE`/RTL/ABORT destinados ao gateway da missão |
| `POST /gateway/commands/{id}/ack` | ACK/resultado idempotente do comando |

Repetir `claim`, `upload-status` ou evento com a mesma chave retorna resultado consistente ou `409`; nunca inicia novamente.

O heartbeat/health do gateway persiste diagnóstico de conexão, topologia, endpoint/serial/baud, `sysid`/`compid`, idade/horário do heartbeat, posição disponível, erro e quatro flags independentes: `mission_upload_enabled`, `flight_commands_enabled`, `mission_start_enabled` e `vehicle_arm_enabled`. Campo não observado continua `null` e nunca é promovido a habilitado.

## WebSocket

- `WS /ws/orders/{order_id}` valida JWT e propriedade antes do upgrade.
- `WS /ws/admin/operations` exige `ADMIN`.
- A primeira mensagem do cliente é `{"type":"AUTH","token":"<jwt>"}`. Eventos carregam `type` e `data`; o conteúdo varia entre snapshot do pedido, missão, telemetria e evento operacional.
- Cliente reconecta com backoff e sempre refaz GET para obter o snapshot canônico. Durante a queda, conserva o último pedido, sinaliza atualização instantânea indisponível, usa polling quando possível e oferece atualização manual.

## Códigos relevantes

`400` request inválido, `401` não autenticado, `403` papel, `404` ausente ou recurso alheio não enumerável, `409` estado/idempotência/`SAVED_LOCATION_LIMIT_REACHED`, `422` campos, `503` dependência ou veículo indisponível.
