# Drone gateway

Processo separado que consulta missões autorizadas no backend e é o único componente com acesso MAVLink. O padrão `simulation` não abre sockets e percorre um voo determinístico para o fluxo vertical.

## Segurança

- não acessa banco;
- não arma veículo no startup, health ou upload;
- `real` exige `REAL_HARDWARE_ACKNOWLEDGED=true` e `ALLOW_MISSION_START=true`;
- `sitl` também só inicia a missão com `ALLOW_MISSION_START=true`; o padrão permite validar conexão/upload sem iniciar automaticamente;
- upload, início, RTL e abortamento são etapas explícitas;
- o raio `MAX_MISSION_DISTANCE_M` é validado antes de upload/início e não é alterado pelo checkout mundial;
- geofence/RTL/preflight ausentes bloqueiam execução;
- `abort` não dispara flight termination: o adaptador real exige intervenção do operador ou solicitação RTL apropriada.

## Progressão observada da missão

No adaptador MAVLink, estados operacionais só são sugeridos a partir de mensagens e condições
explícitas, em ordem e no máximo uma transição por leitura:

1. `DESTINATION_REACHED`: `MISSION_ITEM_REACHED` do waypoint canônico de destino;
2. `DELIVERY_CONFIRMED`: a sequência `MAV_CMD_DO_GRIPPER` (`211`) foi alcançada ou o
   `MISSION_CURRENT` já avançou além dela;
3. `RETURNING`: `MISSION_CURRENT`/`MISSION_ITEM_REACHED` iniciou o waypoint canônico de retorno;
4. `COMPLETED`: o item `LAND` final foi alcançado, o veículo está desarmado e a posição atual
   está dentro da tolerância configurada da origem.

O nome de contrato `DELIVERY_CONFIRMED` confirma somente que o comando do mecanismo de entrega
foi alcançado/ultrapassado na missão. Ele **não comprova fisicamente** que o pacote saiu, chegou
ao destinatário ou foi recebido. O gateway publica um evento operacional com essa ressalva.
O último progresso confirmado e a transição de status pendente, com seu `event_id`, ficam no
journal local para evitar regressão ou repetição após reinício do processo.

## Execução

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.main
```

Variáveis principais: `API_BASE_URL`, `GATEWAY_API_KEY`, `GATEWAY_ID`, `MAVLINK_MODE`,
`MAVLINK_CONNECTION`, `MAVLINK_BAUD`, `MAVLINK_SOURCE_SYSTEM_ID`,
`MAVLINK_TARGET_SYSTEM_ID`, `MAVLINK_TARGET_COMPONENT_ID`, `GATEWAY_JOURNAL_PATH`, limites
preflight e intervalos. IDs-alvo vazios ativam descoberta pelo primeiro heartbeat de autopiloto;
quando conhecidos, configure-os para rejeitar qualquer outro veículo no mesmo enlace. O gateway
reporta a fonte como `SIMULATION`, `SITL` ou `HARDWARE_REAL`, sem completar mensagens MAVLink ainda
não recebidas com zero ou `false`.

Para listar portas seriais sem abri-las nem competir com o Mission Planner:

```powershell
python -m app.tools.list_ports
python -m app.tools.list_ports --json
```

Também é instalado o comando `drone-gateway-list-ports`. A listagem é apenas assistiva: a porta e
o baud rate ainda precisam ser confirmados pelo operador. Consulte `../.env.example` e
`../docs/DRONE_PROTOCOL.md`. O journal atômico evita repetir claim/start após reinício; em
container, monte um volume persistente e aponte `GATEWAY_JOURNAL_PATH` para ele.

## Testes

```powershell
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\pytest
```

Os testes unitários exercitam `PymavlinkVehicleGateway` com mensagens MAVLink falsas e conexão
controlada, inclusive ACKs, releitura, progresso e telemetria vencida. Eles não comprovam SITL,
Pixhawk, mecanismo físico, bancada nem voo real; essas validações continuam separadas e pendentes.
