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

O Flutter roda em Android e Web, autentica clientes, apresenta o catálogo acadêmico, mantém um carrinho simples, conduz a seleção de localização em duas etapas, registra a forma de pagamento simulada e acompanha o pedido. O mapa pode abrir diretamente em qualquer região do mundo, sem endereço e sem permissão de localização; busca e geocodificação são auxílios opcionais. Ele nunca aprova pedido, escolhe altitude, autoriza voo ou envia MAVLink.

### Painel administrativo

O React autentica `ADMIN`, mostra fila e detalhes, mapa satélite, coordenadas finais, decisões, missão, waypoints, saúde do veículo, checklist, autorização de voo, telemetria e eventos. Toda evidência operacional conserva origem (`SIMULATION`, `SITL`, `HARDWARE_REAL` ou `UNKNOWN`), horário de recebimento e estado de frescor. A interface pode solicitar RTL/abortamento, mas o backend e o gateway ainda validam estado e segurança.

### Backend

O FastAPI concentra autenticação, autorização, regras, transações, PostGIS, auditoria e contratos de integração. Os módulos separam router, schemas, service e persistência quando cada camada possui trabalho real. Modelos SQLAlchemy nunca são o contrato externo.

### Banco

PostgreSQL é o armazenamento transacional. PostGIS mantém o ponto final como `geography(Point, 4326)`. Valores monetários usam `NUMERIC`, entidades principais usam UUID e datas são UTC.

### Gateway e Mission Planner

O gateway é o único código que abre MAVLink. Uma implementação fake permite teste rápido; SITL valida o protocolo; o adaptador real exige configuração explícita. O Mission Planner revisa o arquivo `QGC WPL 110`, monitora, calibra e fornece evidência operacional. Não há automação de cliques na sua interface.

### Pixhawk 6C e drone

A Pixhawk/ArduPilot é a fonte de verdade física durante execução. O software prepara conexão, leitura, upload e telemetria, mas não comprova integração nem voo sem hardware e evidência manual. Pinagem, parâmetros e mecanismo de carga só são definidos depois da montagem confirmada.

## Fluxo de dados e controle

1. O cliente pesquisa uma região; o resultado apenas move a câmera.
2. Na etapa satélite, move o marcador e confirma coordenadas finais e área segura.
3. O backend valida faixa, cobertura e distância e persiste o ponto.
4. O pedido submetido entra em `PENDING_ADMIN_APPROVAL`.
5. Um administrador aprova ou rejeita. Rejeição exige motivo.
6. Para pedido aprovado, uma ação separada gera a missão e seu arquivo versionado.
7. O administrador registra abertura/revisão no Mission Planner.
8. Um snapshot recente, não nulo e com origem conhecida do veículo, junto ao checklist, alimenta a segunda decisão.
9. A autorização fica ligada à versão, expira e é de uso único.
10. O gateway reivindica a missão de forma idempotente, valida novamente, envia e confirma o upload.
11. Telemetria e eventos atualizam backend, painel e cliente.
12. Após o comando do mecanismo ser registrado — sem presumir entrega física — a missão retorna à origem e só conclui com a evidência operacional prevista; falhas permanecem falhas.

## Autoridade em duas etapas

```text
PENDING_ADMIN_APPROVAL --aprovar--> APPROVED --preparar--> MISSION_READY
       └--rejeitar(motivo)--> REJECTED

UNDER_REVIEW --revisar--> READY_FOR_AUTHORIZATION
READY_FOR_AUTHORIZATION --autorizar(checklist + saúde)--> AUTHORIZED
```

Nenhuma transação, botão ou endpoint reúne as duas setas. Alterar a missão invalida autorização anterior.

## Estados

Pedido: `DRAFT`, `PENDING_ADMIN_APPROVAL`, `APPROVED`, `REJECTED`, `MISSION_PREPARING`, `MISSION_READY`, `WAITING_FLIGHT_AUTHORIZATION`, `MISSION_UPLOADING`, `IN_TRANSIT`, `AT_DESTINATION`, `DELIVERED`, `RETURNING`, `COMPLETED`, `CANCELLED`, `FAILED`.

Missão: `DRAFT`, `PENDING_VALIDATION`, `GENERATED`, `EXPORTED_TO_MISSION_PLANNER`, `UNDER_REVIEW`, `READY_FOR_AUTHORIZATION`, `AUTHORIZED`, `UPLOADING`, `UPLOADED`, `EXECUTING`, `DESTINATION_REACHED`, `DELIVERY_CONFIRMED`, `RETURNING`, `COMPLETED`, `ABORTED`, `FAILED`.

As transições válidas ficam no domínio, não nos routers ou componentes visuais.

## Segurança e falhas

- JWT de cliente/admin e chave própria do gateway; propriedade do recurso é verificada.
- Segredos vêm do ambiente; CORS é restrito; logs removem token, senha e chaves.
- Heartbeat, GPS, EKF, bateria, geofence, RTL, origem, distância e área controlada são pré-condições.
- Timeouts e reconexão têm limite; upload/claim/eventos possuem chaves de idempotência.
- Perda do backend não muda a autoridade do ArduPilot sobre um voo em execução.
- Abortamento e RTL são decisões registradas; o sistema não altera parâmetros para esconder pre-arm.
- Falha de mapa preserva o pedido e permite tentar novamente; sem mapa real não há confirmação operacional.

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
