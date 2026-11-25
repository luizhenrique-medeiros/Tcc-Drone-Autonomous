# Arquitetura

## Fluxo PX4 vigente

Flutter registra o pedido e o React permite aprovar, gerar e exportar a revisão `.plan`. A origem, o destino e a altitude relativa vêm da missão persistida. O operador revisa o arquivo e opera a Pixhawk pelo QGroundControl. A Pixhawk com PX4 aplica suas proteções. O gateway escuta o encaminhamento MAVLink e publica observações autenticadas na API.

## Visão geral

O sistema mantém um monólito modular como fonte de verdade e separa apenas os executáveis que possuem responsabilidade e risco diferentes.

```text
Aplicativo Flutter ─┐
                    ├─ REST/WebSocket ─ FastAPI ─ PostgreSQL/PostGIS
Painel React ───────┘                      │
                                          ▲ snapshots e eventos autenticados
                                Drone Gateway Python
                                          ▲ UDP de recepção
                                    QGroundControl
                                          ↕ MAVLink
                                      Pixhawk / PX4
```

O painel não é um módulo visual do backend e o gateway não é um microsserviço de domínio: ele é um adaptador operacional isolado que não acessa o banco. Redis, Celery, MQTT e Kubernetes não fazem parte desta arquitetura.

## Componentes e limites

### Aplicativo do cliente

O Flutter roda em Android e Web, autentica clientes, apresenta o catálogo acadêmico, mantém um carrinho simples, conduz a seleção de localização em duas etapas, registra a forma de pagamento simulada e oferece `Meus pedidos` com andamento, histórico paginado e detalhe. A aba `Conta` permite listar, criar, editar e excluir até três localizações salvas, sempre a partir da API autenticada; criação e edição registram o provider, o tipo de mapa e as confirmações reais do mesmo fluxo. No checkout, uma localização salva apenas inicializa o mesmo mapa MapLibre/MapTiler para revisão, ajuste opcional e nova confirmação; escolher o atalho não finaliza o pedido, e o request por `saved_location_id` só envia as duas confirmações atuais depois dessa etapa. Pedidos ativos recebem atualizações pelo WebSocket por pedido, com refetch canônico, reconexão, polling degradado e atualização manual. O mapa pode abrir diretamente em qualquer região do mundo, sem endereço e sem permissão de localização; busca e geocodificação são auxílios opcionais. Ele nunca aprova pedido, escolhe altitude, autoriza voo ou envia MAVLink.

### Painel administrativo

O React autentica `ADMIN`, mostra fila, detalhes, mapa e coordenadas finais, permite gerar e baixar a revisão e registrar a conclusão da entrega com evidência. Telemetria e eventos preservam origem, horário e atualidade. A área de telemetria mostra observações do veículo e associa progresso à revisão somente com evidência inequívoca.

### Backend

O FastAPI concentra autenticação, autorização, regras, transações, PostGIS, auditoria e contratos de integração. Requests do gateway vinculam chave e `X-Gateway-ID` à identidade configurada; comandos críticos usam locks de missão/comando antes de transições e eventos. O módulo de localizações salvas obtém o proprietário do JWT, exige as quatro confirmações verdadeiras na criação, persiste o provider/tipo e as flags reais, serializa a criação por cliente com lock transacional na linha de `users` e aplica o limite de três no servidor. Ao criar pedido a partir de um atalho, o backend exige as duas confirmações da revisão atual e copia seus dados para um novo `DeliveryPoint` na mesma transação do pedido; o snapshot usa provider/tipo persistidos e evidência atual, sem constantes que simulem confirmação. Os módulos separam router, schemas, service e persistência quando cada camada possui trabalho real. Modelos SQLAlchemy nunca são o contrato externo.

### Banco

PostgreSQL é o armazenamento transacional. PostGIS mantém o ponto final como `geography(Point, 4326)`. `saved_locations` guarda atalhos mutáveis do cliente junto do provider, tipo de mapa e confirmações reais de sua seleção; `delivery_points` guarda o snapshot do destino e da revisão atual de cada pedido. Não existe dependência histórica do pedido para a localização salva. Valores monetários usam `NUMERIC`, entidades principais usam UUID e datas são UTC.

### Localizações salvas e snapshot

```text
SavedLocation mutável + evidência real de criação
              │ nova revisão e confirmações atuais no mapa
              ▼
DeliveryPoint copiado com provider/tipo salvos e evidência atual
              ▼
Order histórico
```

O cliente pode manter de zero a três atalhos, mas continua livre para usar qualquer quantidade de destinos manuais válidos em pedidos. Cada atalho conserva `map_provider`, `map_type` (`hybrid` ou `satellite`) e as quatro flags verdadeiras produzidas em sua criação. Editar ou excluir `SavedLocation` não percorre nem altera `DeliveryPoint` existente. O valor interno `SAVED_POINT` registra a origem da seleção no snapshot sem transformar o atalho na autoridade do destino histórico.

### Gateway e QGroundControl

O gateway recebe MAVLink por UDP do QGroundControl e publica snapshots e eventos na API. O gateway operacional força o transporte passivo e recusa configurações de escrita, inclusive o perfil experimental de bancada. Seu ciclo não consome filas nem retoma o journal de comandos. O QGroundControl usa o enlace configurado do operador. A API não oferece filas legadas fora de `APP_ENV=test`. Em testes, o fake e um perfil PX4 SITL isolado cobrem os contratos históricos.

### Pixhawk 6C e drone

O PX4 é a fonte do estado físico e decide se aceita ações operadas no QGroundControl. Leituras ausentes permanecem nulas. O gateway marca amostras antigas e a API preserva o horário da observação.

## Fluxo de dados e controle

1. O cliente seleciona a região e confirma o ponto final no mapa. Se partir de um atalho, os dados revisados são copiados para o snapshot do pedido.
2. Um administrador aprova o pedido ou rejeita com motivo. Em ação separada, gera a missão versionada.
3. O painel baixa o `.plan` da revisão. O backend confere versão e hash, usa a origem planejada e o destino da revisão e registra a exportação.
4. O operador abre e revisa o plano no QGroundControl. As ações do veículo acontecem no QGroundControl.
5. O gateway publica telemetria. O backend mantém um registro de voo observado por sessão de armamento. A missão se vincula por evidência de identidade ou por seleção explícita do administrador. Só a verificação do plano a bordo identifica os itens da revisão. O andamento observado é exibido separadamente do estado comercial do pedido.
6. A entrega é concluída administrativamente, com evidência e ator registrados.

## Estados

Pedido: `DRAFT`, `PENDING_ADMIN_APPROVAL`, `APPROVED`, `REJECTED`, `MISSION_PREPARING`, `MISSION_READY`, `WAITING_FLIGHT_AUTHORIZATION`, `MISSION_UPLOADING`, `IN_TRANSIT`, `AT_DESTINATION`, `DELIVERED`, `RETURNING`, `COMPLETED`, `CANCELLED`, `FAILED`. `DRAFT` é interno ao checkout e só passa a integrar `Meus pedidos` depois da submissão.

Missão: `DRAFT`, `PENDING_VALIDATION`, `GENERATED`, `EXPORTED_TO_MISSION_PLANNER`, `UNDER_REVIEW`, `READY_FOR_AUTHORIZATION`, `AUTHORIZED`, `UPLOADING`, `UPLOADED`, `VERIFIED`, `EXECUTING`, `PAUSED`, `DESTINATION_REACHED`, `DELIVERY_CONFIRMED`, `RETURNING`, `COMPLETED`, `ABORTED`, `FAILED`.

As transições válidas ficam no domínio, não nos routers ou componentes visuais.

## Segurança e falhas

- JWT de cliente/admin, propriedade do recurso, autenticação própria do gateway e segredos no ambiente.
- Transações de criação e de revisão preservam integridade, versão e dados históricos. Localizações salvas continuam limitadas a três por conta.
- Disponibilidade de telemetria não condiciona aprovação, geração ou exportação. Nenhuma regra do site substitui proteções ou decisões operacionais do PX4.
- A observação passiva não atualiza parâmetros, transmite consultas, transfere missão ou reage a falhas com comandos. Falhas e dados antigos permanecem visíveis.
- A confirmação idempotente de entrega usa lock do pedido e registra a evidência no mesmo commit.

## Ambientes e evidência

| Ambiente | MAVLink | Objetivo | Evidência permitida |
|---|---|---|---|
| `test` | fake ou SITL isolado | testes determinísticos | código testado |
| `development` | fake ou recepção passiva | integração local | simulação ou telemetria observada |
| `demo` | recepção passiva | apresentação controlada | registrar origem e atualidade |
| `production` | não habilitado no MVP | evolução futura | nenhuma alegação comercial |

Uma passagem em fake não prova SITL; SITL não prova Pixhawk; bancada sem hélices não prova voo; um voo manual não prova missão autônoma completa.

## Decisões relacionadas

Consulte [ADRs](adr/README.md), [Segurança](SECURITY.md), [Protocolo](DRONE_PROTOCOL.md) e [Hardware](HARDWARE.md).
