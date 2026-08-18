# Arquitetura

## Visão geral

O sistema mantém um monólito modular como fonte de verdade e separa apenas os executáveis que possuem responsabilidade e risco diferentes.

```text
Aplicativo Flutter ─┐
                    ├─ REST/WebSocket ─ FastAPI ─ PostgreSQL/PostGIS
Painel React ───────┘                      │
                                          │ contrato autenticado
                                          ▼
                                Drone Gateway Python
                                          │ MAVLink
                           Mission Planner/SITL/Pixhawk 6C
                                          │
                                      Drone real
```

O painel não é um módulo visual do backend e o gateway não é um microsserviço de domínio: ele é um adaptador operacional isolado que não acessa o banco. Redis, Celery, MQTT e Kubernetes não fazem parte desta arquitetura.

## Componentes e limites

### Aplicativo do cliente

O Flutter roda em Android e Web, autentica clientes, apresenta o catálogo acadêmico, mantém um carrinho simples, conduz a seleção de localização em duas etapas, registra a forma de pagamento simulada e oferece `Meus pedidos` com andamento, histórico paginado e detalhe. A aba `Conta` permite listar, criar, editar e excluir até três localizações salvas, sempre a partir da API autenticada; criação e edição registram o provider, o tipo de mapa e as confirmações reais do mesmo fluxo. No checkout, uma localização salva apenas inicializa o mesmo mapa MapLibre/MapTiler para revisão, ajuste opcional e nova confirmação; escolher o atalho não finaliza o pedido, e o request por `saved_location_id` só envia as duas confirmações atuais depois dessa etapa. Pedidos ativos recebem atualizações pelo WebSocket por pedido, com refetch canônico, reconexão, polling degradado e atualização manual. O mapa pode abrir diretamente em qualquer região do mundo, sem endereço e sem permissão de localização; busca e geocodificação são auxílios opcionais. Ele nunca aprova pedido, escolhe altitude, autoriza voo ou envia MAVLink.

### Painel administrativo

O React autentica `ADMIN`, mostra fila e detalhes, mapa satélite, coordenadas finais, decisões, missão, waypoints, saúde do veículo, checks automáticos, três confirmações humanas, autorização de voo, telemetria e eventos. Checks usam `PASS`, `WARNING` e `BLOCKING`; a frase digitada não faz parte da autorização. Toda evidência operacional conserva origem (`SIMULATION`, `SITL`, `HARDWARE_REAL` ou `UNKNOWN`), horário de recebimento e estado de frescor. A interface pode solicitar `START`, `PAUSE`, `CONTINUE`, RTL ou abortamento, mas o backend e o gateway ainda validam estado, idade do comando e gates locais; nenhum botão arma o veículo.

### Backend

O FastAPI concentra autenticação, autorização, regras, transações, PostGIS, auditoria e contratos de integração. O módulo de localizações salvas obtém o proprietário do JWT, exige as quatro confirmações verdadeiras na criação, persiste o provider/tipo e as flags reais, serializa a criação por cliente com lock transacional na linha de `users` e aplica o limite de três no servidor. Ao criar pedido a partir de um atalho, o backend exige as duas confirmações da revisão atual e copia seus dados para um novo `DeliveryPoint` na mesma transação do pedido; o snapshot usa provider/tipo persistidos e evidência atual, sem constantes que simulem confirmação. Os módulos separam router, schemas, service e persistência quando cada camada possui trabalho real. Modelos SQLAlchemy nunca são o contrato externo.

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

### Gateway e Mission Planner

O gateway é o único código que abre MAVLink. Uma implementação fake permite teste rápido; SITL valida o protocolo; o adaptador real exige configuração explícita. O Mission Planner revisa o arquivo `QGC WPL 110`, monitora, calibra e fornece evidência operacional. Não há automação de cliques na sua interface.

### Pixhawk 6C e drone

A Pixhawk/ArduPilot é a fonte de verdade física durante execução. O software prepara conexão, leitura, upload e telemetria, mas não comprova integração nem voo sem hardware e evidência manual. Pinagem, parâmetros e mecanismo de carga só são definidos depois da montagem confirmada.

## Fluxo de dados e controle

1. O cliente escolhe uma localização salva ou pesquisa/abre manualmente uma região; nenhum desses atos confirma sozinho o destino.
2. Uma localização salva centraliza o mesmo mapa satélite/híbrido. O cliente revisa, pode ajustar o ponto ou as instruções somente para o pedido e confirma novamente as coordenadas finais e a área segura; só então o app produz `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true`. Qualquer ajuste de ponto ou instrução segue o caminho manual de `DeliveryPoint`, sem mutar o atalho nem perder o valor revisado.
3. No caminho manual, o resultado de busca apenas move a câmera; a etapa satélite exige a seleção final.
4. `OrderCreate` recebe exatamente um de `delivery_point_id` ou `saved_location_id`. No segundo caminho, também exige as duas confirmações atuais, valida propriedade e copia a localização para um novo `DeliveryPoint` na mesma transação do pedido, preservando provider/tipo salvos e sem sintetizar flags de confirmação.
5. Se o cliente optar por salvar um novo ponto manual, o aplicativo dispara `POST /saved-locations` somente depois da criação do pedido e não aguarda essa chamada para devolver o pedido à interface. Recusa, latência, limite, offline ou falha não desfazem nem bloqueiam o pedido; o resultado tardio aparece apenas como aviso do atalho.
6. O pedido submetido entra em `PENDING_ADMIN_APPROVAL`.
7. Um administrador aprova ou rejeita. Rejeição exige motivo.
8. Para pedido aprovado, uma ação separada gera a missão e seu arquivo versionado.
9. O administrador registra abertura/revisão no Mission Planner.
10. Um snapshot recente, não nulo e com origem conhecida alimenta checks automáticos; o operador confirma somente área/condições, inspeção física do drone/carga e sua prontidão.
11. A autorização fica ligada à versão, expira e é de uso único.
12. O gateway reivindica a missão de forma idempotente, valida novamente, envia, recebe o ACK e relê o conteúdo. Só a comparação completa publica `VERIFIED`.
13. `VERIFIED` aguarda o armamento físico pelo operador e uma solicitação administrativa `START`; o gateway exige separadamente os gates de comandos e de início. `PAUSE` e `CONTINUE` também são comandos auditados e ACK-aware.
14. Telemetria e eventos atualizam backend, painel e `Meus pedidos`; uma desconexão conserva o último snapshot e aciona reconexão/refetch.
15. Após o comando do mecanismo ser registrado — sem presumir entrega física — a missão retorna à origem e só conclui com a evidência operacional prevista; falhas permanecem falhas.

## Autoridade em duas etapas

```text
PENDING_ADMIN_APPROVAL --aprovar--> APPROVED --preparar--> MISSION_READY
       └--rejeitar(motivo)--> REJECTED

UNDER_REVIEW --revisar--> READY_FOR_AUTHORIZATION
READY_FOR_AUTHORIZATION --autorizar(3 confirmações + checks sem BLOCKING)--> AUTHORIZED
```

Nenhuma transação, botão ou endpoint reúne as duas setas. Alterar a missão invalida autorização anterior.

## Estados

Pedido: `DRAFT`, `PENDING_ADMIN_APPROVAL`, `APPROVED`, `REJECTED`, `MISSION_PREPARING`, `MISSION_READY`, `WAITING_FLIGHT_AUTHORIZATION`, `MISSION_UPLOADING`, `IN_TRANSIT`, `AT_DESTINATION`, `DELIVERED`, `RETURNING`, `COMPLETED`, `CANCELLED`, `FAILED`. `DRAFT` é interno ao checkout e só passa a integrar `Meus pedidos` depois da submissão.

Missão: `DRAFT`, `PENDING_VALIDATION`, `GENERATED`, `EXPORTED_TO_MISSION_PLANNER`, `UNDER_REVIEW`, `READY_FOR_AUTHORIZATION`, `AUTHORIZED`, `UPLOADING`, `UPLOADED`, `VERIFIED`, `EXECUTING`, `PAUSED`, `DESTINATION_REACHED`, `DELIVERY_CONFIRMED`, `RETURNING`, `COMPLETED`, `ABORTED`, `FAILED`.

As transições válidas ficam no domínio, não nos routers ou componentes visuais.

## Segurança e falhas

- JWT de cliente/admin e chave própria do gateway; propriedade do recurso é verificada.
- Rotas de `saved-locations` derivam `user_id` exclusivamente do JWT e devolvem a resposta não enumerável do projeto para recurso alheio.
- Antes de contar e inserir uma localização, a transação bloqueia a linha do cliente com `FOR NO KEY UPDATE`; duas criações concorrentes não ultrapassam três.
- Segredos vêm do ambiente; CORS é restrito; logs removem token, senha e chaves.
- Heartbeat, GPS, EKF, bateria, geofence, RTL, origem, distância e área controlada são pré-condições.
- Timeouts e reconexão têm limite; upload/claim/eventos possuem chaves de idempotência.
- Perda do backend não muda a autoridade do ArduPilot sobre um voo em execução.
- Abortamento e RTL são decisões registradas; o sistema não altera parâmetros para esconder pre-arm.
- Falha de mapa preserva o pedido e permite tentar novamente; sem mapa real não há confirmação operacional.
- Falha ao criar o atalho opcional depois do pedido preserva o `DeliveryPoint` e o pedido já criados; não há substituição automática ao atingir o limite.

## Ambientes e evidência

| Ambiente | MAVLink | Objetivo | Evidência permitida |
|---|---|---|---|
| `test` | fake | testes determinísticos | código testado |
| `development` | fake ou SITL | integração local | simulação/SITL |
| `demo` | SITL ou real explícito | apresentação controlada | registrar qual modo foi usado |
| `production` | não habilitado no MVP | evolução futura | nenhuma alegação comercial |

Uma passagem em fake não prova SITL; SITL não prova Pixhawk; bancada sem hélices não prova voo; um voo manual não prova missão autônoma completa.

## Decisões relacionadas

Consulte [ADRs](adr/README.md), [Segurança](SECURITY.md), [Protocolo](DRONE_PROTOCOL.md) e [Hardware](HARDWARE.md).
