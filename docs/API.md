# Contrato HTTP e WebSocket

Base: `/api/v1`. Respostas JSON usam UTC ISO-8601, UUID em texto e dinheiro como decimal serializado em string.

## Revisão de origem em pré-voo (contrato legado)

`POST /admin/missions/{id}/revise-origin` exige ADMIN e `Idempotency-Key`.
Corpo estrito: `expected_version`, `expected_sha256`, `origin_latitude`,
`origin_longitude` (até sete casas decimais), `reason` (10–1000 caracteres) e
`position_confirmed=true`. Não aceita destino ou altitude no corpo.
Exige missão pré-voo, veículo vinculado, saúde fresca/desarmada em STABILIZE,
quatro gates explicitamente falsos e nenhum comando pendente/reconhecido nem
tentativa anterior de START. O limite `MAX_MISSION_DISTANCE_M` aplica-se também
a esta revisão; não limita o checkout do cliente.
Retorna a nova versão em GENERATED, sem claim/revisão/exportação herdados.
O evento `MISSION_ORIGIN_REVISED` arquiva o JSON e o arquivo completos anteriores;
autorizações consumidas permanecem históricas, inválidas para a nova versão.

`POST /gateway/missions/{id}/release-retired-version` recebe `version` e
`mission_sha256` do journal. Exige identidade autenticada do veículo/gateway.
Retorna os mesmos campos, `mission_id` e `released`. Sem mudança, retorna false;
liberação exige revisão auditada correspondente, observação/desarmamento fresco
e ausência de comando em andamento. O reconhecimento é idempotente e auditado.
Nova autorização espera esse reconhecimento quando havia claim anterior.
Esse endpoint não cancela voo nem apaga a missão armazenada no piloto automático.

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

`POST /admin/missions/{id}/qgroundcontrol-plan` requer `ADMIN` e corpo com
`expected_version`, `expected_sha256` da missão e `home_amsl_m` opcional.
Retorna anexo `pedido-{order_id}-v{version}-{hash}.plan`, `X-Plan-SHA256` e
`Cache-Control: no-store`. Origem e destino vêm da revisão persistida. A
sequência Takeoff, Waypoint com 5 s e RTL conserva a altitude relativa
configurada. Versão/hash divergentes retornam `409`. O evento
`QGROUNDCONTROL_PLAN_EXPORTED` identifica a exportação e o campo
`qgroundcontrol_plan_exported_at` informa a última para a revisão atual.

`POST /admin/orders/{id}/confirm-delivery` requer `ADMIN` e `evidence` em
texto. Para os estados elegíveis, conclui o pedido com
`ORDER_DELIVERY_CONFIRMED` e permite repetir sem duplicar o evento. A
missão conserva seu estado. Upload e comandos do PX4 ficam no QGroundControl.

`POST /admin/missions/{id}/observed-flight` associa o acompanhamento com
`vehicle_id`, `expected_version` e `expected_sha256` do registro da missão.
Exige `ADMIN`, exportação da revisão atual e heartbeat recente de PX4 físico ou SITL identificado.
A operação grava ator, veículo, pedido e exportação em `FLIGHT_ASSOCIATED`.
`GET` na mesma rota e em `/admin/vehicles/{id}/observed-flight` retorna a
última sessão observada, ou `null`. O resultado inclui estado, proveniência
do vínculo, dados observados, trechos do trajeto e eventos. `stale` indica
perda de atualidade.

Rotas de escrita de comandos e claims adiante estão restritas a
`APP_ENV=test`. Em operação as filas `/gateway/missions/authorized` e
`/gateway/commands/pending` retornam listas vazias a gateways autenticados,
inclusive com registros antigos. O roteador físico de ARM não é montado.

| Método e rota | Pré-condição |
|---|---|
| `GET /admin/orders` | `ADMIN` |
| `GET /admin/orders/{id}` | `ADMIN` |
| `POST /admin/orders/{id}/approve` | pendente |
| `POST /admin/orders/{id}/reject` | pendente + motivo |
| `POST /admin/orders/{id}/prepare-mission` | aprovado |
| `POST /admin/orders/{id}/confirm-delivery` | estado elegível, evidência e `ADMIN` |
| `GET /admin/missions` | `ADMIN` |
| `GET /admin/missions/{id}` | `ADMIN` |
| `POST /admin/missions/{id}/qgroundcontrol-plan` | versão/hash atuais e `ADMIN` |
| `GET /admin/missions/{id}/export` | formato WPL legado |
| `POST /admin/missions/{id}/qgroundcontrol-draft` | missão existente, com telemetria opcional |
| `GET /admin/missions/{id}/qgroundcontrol-review` | `ADMIN` e revisão da versão atual |
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

O endpoint legado `qgroundcontrol-draft` contém Takeoff, um Waypoint no ponto
confirmado do pedido com 5 segundos em `param1` e Return To Launch (RTL).
O corpo aceita `{}`. Sem posição recente, o rascunho usa a origem planejada
da missão. O parâmetro `home_amsl_m` é opcional e completa a altitude quando
ela não é recebida pela telemetria.
O GET da revisão devolve o `.plan` original como anexo e informa seu
`X-Plan-SHA256`. Retorna `404` quando falta uma revisão e `409` quando a
revisão está desatualizada ou os bytes divergem do hash registrado.

Na leitura de auditoria, `metadata` preserva valores JSON estruturados. O
registro de revisão do QGroundControl inclui a lista `reviewed_items` com os
comandos e parâmetros do plano revisado.

A autorização legada é usada em testes e simulação. Ela vincula a versão e o hash da missão ao veículo simulado e conserva os campos auditáveis `area_and_conditions_clear`, `aircraft_and_payload_inspected` e `operator_ready`. Para hardware real, o site oferece planejamento, revisão de arquivos e telemetria. A operação de voo é feita no QGroundControl.

O objeto de saúde preserva o campo legado `authorization_limits` com `min_battery_percent`, `battery_warning_percent` e `min_gps_satellites` para compatibilidade com a simulação. O painel apresenta os dados recebidos.

O diagnóstico opcional `px4_diagnostics` inclui `current_mode_prearm_ok`,
`rtl_type`, `rtl_return_alt_m`, `rtl_descend_alt_m`, `rtl_land_delay_s`,
`rtl_cone_angle_deg` e `rtl_min_distance_m`.
Os campos ausentes ou expirados permanecem nulos. O pré-arm se refere ao modo
`flight_mode` da amostra. Autorização legada de teste pode usar `preflight_ok` e `rtl_configured`. A operação real exibe observações sem avaliar aptidão.

As respostas administrativas de missão incluem `authorization` com o último registro real, quando existente: identificadores da autorização e do administrador, nome real do administrador e operador, status, versão, emissão, expiração e consumo. Isso preserva a evidência após reload sem expor checklist bruto nem fabricar nomes no navegador.

O campo administrativo `qgroundcontrol_review_status` retorna `null` quando
não há revisão registrada. Retorna `CURRENT` quando o último registro do
`.plan` corresponde à versão e ao hash da missão ou `OUTDATED` quando pertence
a um artefato anterior. A revisão legada e a autorização em hardware continuam
bloqueadas nesses estados. Somente em `APP_ENV=test` com
`PX4_SITL_PLAN_VALIDATION=true`, o detalhe administrativo pode informar
`qgroundcontrol_sitl_review_event_id`. Envie esse ID como
`qgroundcontrol_review_event_id` na autorização para o veículo PX4 SITL.
A autorização registra esse ID e `qgroundcontrol_candidate_sha256`.
O claim devolve o artefato revisado com seu hash, e o gateway confere o
conteúdo antes de enviar ao simulador isolado.

`POST /admin/missions/{id}/authorize-flight` aceita `Idempotency-Key`: repetir chave e corpo devolve a mesma autorização com `Idempotency-Replayed`. O painel conserva a chave enquanto a resposta for ambígua. Nova emissão fora de `READY_FOR_AUTHORIZATION` retorna conflito, exceto pela renovação explícita de `VERIFIED` abaixo.

Em `VERIFIED`, o mesmo endpoint renova uma autorização **consumida e vencida**:
exige mesmo veículo/gateway, versão/hash, saúde atual desarmada, três novas
confirmações e nenhum comando `PENDING`/`ACKNOWLEDGED`. Emite novo registro
`CONSUMED`, prazo e `used_at`, auditado como `FLIGHT_AUTHORIZATION_RENEWED`.
Registro antigo, artefato e estado `VERIFIED` permanecem intactos. Não arma,
inicia ou reenfileira upload. Autorização ainda vigente não pode ser renovada.

`POST /gateway/missions/{id}/claim` em `VERIFIED` devolve essa autoridade atual
somente ao gateway vinculado, sem novo upload. ARM/START recusam prazo vencido
já no backend (`409`, com orientação de renovação). Para um novo comando humano
com claim local vencido, o gateway consulta e compara o claim atual inteiro
antes de persistir o novo prazo. Divergência/indisponibilidade nunca libera comando.

`GET /admin/missions` e `GET /admin/missions/{id}` incluem a autorização mais recente quando ela existe, com administrador real, operador, status, versão e datas de emissão, expiração e consumo. Esse resumo administrativo não é enviado ao WebSocket do cliente.

No `claim`, o gateway precisa corresponder ao veículo autorizado. Mudanças saudáveis de telemetria, como pequenas variações de bateria ou satélites, não revogam a autorização por igualdade exata de amostra; qualquer falha atual nos limites técnicos, expiração ou alteração de versão/hash revoga a autorização, retorna a missão para nova autorização e registra o motivo em `SystemEvent`.

### Armamento legado em SITL

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
- último snapshot do mesmo veículo fresco, conectado, com heartbeat, origem `SITL` e `armed=false`;
- GPS/satélites, EKF,  home/origem, geofence, RTL e preflight completos e dentro dos limites canônicos;
- `flight_mode=STABILIZE`;
- `vehicle_arm_enabled=true`, `flight_commands_enabled=true` e `mission_start_enabled=true`;
- ausência de outro comando crítico `PENDING` ou `ACKNOWLEDGED` para a missão.

Campo ausente, nulo, stale ou falso falha fechado com `409`; o navegador não pode fornecer resultados técnicos. O `202` devolve `{ "mission": AdminMissionRead, "command": GatewayCommandRead }` e significa apenas que a solicitação foi persistida. O painel acompanha o `command.id` exato por `GET /api/v1/admin/missions/{id}/commands/{command_id}`. A sequência auditável é `PENDING → ACKNOWLEDGED → COMPLETED|FAILED`; `FAILED` expõe `result_detail`, enquanto `COMPLETED` só é aceito depois de ACK MAVLink correlacionado e de um heartbeat novo, persistido pelo backend, com `armed=true`, origem permitida e identidade correta. ARM não inicia nem muda a missão para `EXECUTING`; `START` continua sendo request posterior. Não existe rearmamento automático após timeout, falha, restart ou desarmamento.

O endpoint genérico de comando aceita `SafetyActionRequest` opcional e `Idempotency-Key`. `START` só é criado em `VERIFIED`; `PAUSE`, durante estados físicos permitidos; `CONTINUE`, somente em `PAUSED`. O `202` significa que o pedido foi persistido, não que o autopiloto executou. O gateway ainda rejeita comando vencido, identidade de veículo divergente, snapshot/heartbeat/preflight inválido ou gate local fechado. Em especial, `START` requer `flight_commands_enabled=true`, `mission_start_enabled=true` e veículo já armado; ele nunca envia ARM implicitamente. O único caminho de armamento é o endpoint dedicado descrito acima.

## Ensaios PX4 SITL

Os endpoints administrativos a seguir existem em ambiente de teste com
`PX4_SITL_PLAN_VALIDATION`. Eles exigem JWT administrativo. Solicitações
`POST` requerem `Idempotency-Key` e `confirmed: true`.

| Método e rota | Resultado |
| --- | --- |
| `POST /admin/missions/{id}/px4-sitl/upload` | Fila o upload e vincula o veículo e o registro atual da revisão a partir de `vehicle_id` e `qgroundcontrol_review_event_id`. |
| `POST /admin/missions/{id}/px4-sitl/commands/{action}` | Registra uma solicitação `ARM`, `START` ou `RTL` e devolve o comando com seu ID. |
| `GET /admin/missions/{id}/px4-sitl/commands` | Consulta os estados e detalhes dos comandos recentes. |

O retorno `202` indica recebimento administrativo. O resultado do PX4 é
registrado após correlação da resposta com o comando e confirmação do estado
esperado. Falhas e timeouts permanecem visíveis.

## Gateway

Em observação, o gateway envia `POST /gateway/heartbeat` e, quando houver
eventos, `POST /gateway/vehicles/{vehicle_id}/observations`. Saúde inclui
`px4_flight` com estado de solo, índices e extensões de missão quando
recebidos, e carimbos das posições e da missão.
`current_ground_speed_m_s` em m/s quando recebida com posição atual. A API
preserva o horário da leitura e o painel indica campos ausentes e dados
desatualizados. O backend associa progresso físico somente a evidência
que identifica a revisão atual, sem concluir entrega.

As demais rotas abaixo incluem contratos usados em testes isolados.

`POST /gateway/vehicles/{vehicle_id}/observations` recebe até 20 observações
MAVLink normalizadas do veículo associado ao gateway autenticado. Os tipos
aceitos são respostas de comando e de missão, waypoint atual, waypoint
alcançado e mensagens de estado. O gateway mantém os identificadores de
evento durante novas tentativas após falhas de comunicação. A API deduplica,
registra as observações no veículo e publica `system.event` aos administradores.
A operação preserva os estados da missão e do pedido. Uma resposta observada
pode ter sido dirigida ao QGroundControl e deve ser interpretada como evento
do veículo.

Em hardware PX4, o gateway registra `PX4_PHYSICAL_PLAN_READBACK` após
conferir a missão gravada com o arquivo revisado. Quando uma observação
posterior `MAVLINK_MISSION_CURRENT` traz o mesmo identificador nativo
e os mesmos IDs MAVLink, a API publica
`PX4_PHYSICAL_MISSION_PROGRESS_OBSERVED` na missão e no pedido que têm
uma única revisão atual correspondente ao hash conferido. O evento bruto
também permanece na lista de observações do veículo. Uma revisão ambígua
ou identificador ausente deixa o progresso sem vínculo.

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

- `WS /ws/orders/{order_id}` valida JWT e propriedade antes de enviar dados do pedido.
- `WS /ws/admin/operations` exige `ADMIN`.
- A primeira mensagem do cliente é `{"type":"AUTH","token":"<jwt>"}`. Eventos carregam `type` e `data`; o conteúdo varia entre snapshot do pedido, missão, telemetria e evento operacional.
- Cada conexão autorizada do pedido recebe `order.snapshot` e, se houver missão,
  `mission.status` com o estado persistido atual, no mesmo contrato `MissionRead`
  das atualizações. Isso recupera transições perdidas durante logout/desconexão;
  não altera a missão, autoriza ou envia comandos ao veículo. Pedido sem missão
  não recebe estado de missão fabricado.
- Cliente reconecta com backoff e sempre refaz GET para obter o snapshot canônico. Durante a queda, conserva o último pedido, sinaliza atualização instantânea indisponível, usa polling quando possível e oferece atualização manual.

## Códigos relevantes

`400` request inválido, `401` não autenticado, `403` papel, `404` ausente ou recurso alheio não enumerável, `409` estado/idempotência/`SAVED_LOCATION_LIMIT_REACHED`, `422` campos, `503` dependência ou veículo indisponível.
