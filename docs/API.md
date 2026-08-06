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
| `POST /delivery-points/validate` | cliente | faixa/cobertura/distância, sem persistir |
| `POST /delivery-points` | cliente | ponto final confirmado |
| `GET /delivery-points` | cliente | próprios pontos |
| `POST /orders` | cliente | rascunho e snapshots |
| `GET /orders` | cliente | próprios pedidos |
| `GET /orders/{id}` | proprietário | detalhe |
| `POST /orders/{id}/submit` | proprietário | `PENDING_ADMIN_APPROVAL` |
| `POST /orders/{id}/cancel` | proprietário | cancelamento permitido |

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
  "map_provider": "google_maps",
  "map_type": "satellite",
  "accuracy_meters": 5
}
```

O request de pedido aceita apenas enum da forma simulada, `delivery_point_id` e itens. Não aceita dados de cartão.

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

A autorização recebe veículo, operador, confirmação de área controlada e todos os itens do checklist. O servidor a vincula à versão e ao hash atuais da missão; ela nunca aceita um booleano genérico que contorne as verificações.

## Gateway

| Método e rota | Semântica |
|---|---|
| `POST /gateway/heartbeat` | identidade e snapshot normalizado |
| `GET /gateway/missions/authorized` | missões vigentes elegíveis |
| `POST /gateway/missions/{id}/claim` | consome autorização uma vez |
| `POST /gateway/missions/{id}/upload-status` | início/resultado do upload, deduplicado por `event_id` |
| `POST /gateway/missions/{id}/status` | transição física validada |
| `POST /gateway/missions/{id}/telemetry` | amostra normalizada |
| `POST /gateway/missions/{id}/events` | evento com UUID deduplicável |
| `GET /gateway/commands/pending` | comandos RTL/ABORT destinados ao gateway |
| `POST /gateway/commands/{id}/ack` | ACK/resultado idempotente do comando |

Repetir `claim`, `upload-status` ou evento com a mesma chave retorna resultado consistente ou `409`; nunca inicia novamente.

## WebSocket

- `WS /ws/orders/{order_id}` valida JWT e propriedade antes do upgrade.
- `WS /ws/admin/operations` exige `ADMIN`.
- A primeira mensagem do cliente é `{"type":"AUTH","token":"<jwt>"}`. Eventos carregam `type` e `data`; o conteúdo varia entre snapshot do pedido, missão, telemetria e evento operacional.
- Cliente reconecta com backoff e sempre refaz GET para obter o snapshot canônico.

## Códigos relevantes

`400` request inválido, `401` não autenticado, `403` papel/propriedade, `404` ausente, `409` estado/idempotência, `422` campos, `503` dependência ou veículo indisponível.
