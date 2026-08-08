# Contrato HTTP e WebSocket

Base: `/api/v1`. Respostas JSON usam UTC ISO-8601, UUID em texto e dinheiro como decimal serializado em string.

## Autenticação

`Authorization: Bearer <JWT>` para cliente/admin. O gateway usa `X-Gateway-API-Key`. Cadastro ignora/rejeita papel enviado pelo público. Erro padrão:

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
| `POST /orders` | cliente | rascunho e snapshots |
| `GET /orders` | cliente | próprios pedidos com `limit`/`offset` e grupo opcional |
| `GET /orders/{id}` | proprietário | detalhe com milestones sanitizados |
| `POST /orders/{id}/submit` | proprietário | `PENDING_ADMIN_APPROVAL` |
| `POST /orders/{id}/cancel` | proprietário | cancelamento permitido |

As três rotas `/maps/*` são o proxy autenticado para a Geocoding API do MapTiler. Pesquisa exige pelo menos três caracteres e aplica autocomplete; geocode recebe exatamente um de `address` ou `place_id`; reverse geocode recebe latitude/longitude, mas o adaptador externo envia `longitude,latitude`. A resposta externa GeoJSON é convertida aos DTOs internos e nunca expõe `MAPTILER_SERVER_API_KEY`.

Configuração ausente retorna `503/MAPS_NOT_CONFIGURED`; recusa, quota, timeout, rede ou resposta externa inválida retornam `502/MAPS_PROVIDER_ERROR`; consulta inválida retorna `422/MAPS_QUERY_INVALID`. Resultado vazio de geocode/reverse geocode retorna `404`, sem fabricar endereço.

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

O request de pedido aceita apenas enum da forma simulada, `delivery_point_id` e itens. Não aceita dados de cartão.

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
| `POST /admin/missions/{id}/abort` | estado abortável |
| `POST /admin/missions/{id}/request-rtl` | execução/condição válida |
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
| `GET /gateway/commands/pending` | comandos RTL/ABORT destinados ao gateway |
| `POST /gateway/commands/{id}/ack` | ACK/resultado idempotente do comando |

Repetir `claim`, `upload-status` ou evento com a mesma chave retorna resultado consistente ou `409`; nunca inicia novamente.

## WebSocket

- `WS /ws/orders/{order_id}` valida JWT e propriedade antes do upgrade.
- `WS /ws/admin/operations` exige `ADMIN`.
- A primeira mensagem do cliente é `{"type":"AUTH","token":"<jwt>"}`. Eventos carregam `type` e `data`; o conteúdo varia entre snapshot do pedido, missão, telemetria e evento operacional.
- Cliente reconecta com backoff e sempre refaz GET para obter o snapshot canônico. Durante a queda, conserva o último pedido, sinaliza atualização instantânea indisponível, usa polling quando possível e oferece atualização manual.

## Códigos relevantes

`400` request inválido, `401` não autenticado, `403` papel/propriedade, `404` ausente, `409` estado/idempotência, `422` campos, `503` dependência ou veículo indisponível.
