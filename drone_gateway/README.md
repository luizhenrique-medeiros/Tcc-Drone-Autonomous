# Drone gateway

Processo separado que consulta missões autorizadas no backend e é o único componente com acesso MAVLink. O padrão `simulation` não abre sockets e percorre um voo determinístico para o fluxo vertical.

## Segurança

- não acessa banco;
- não arma veículo no startup, health ou upload;
- `real` exige `REAL_HARDWARE_ACKNOWLEDGED=true` e `ALLOW_MISSION_START=true`;
- `sitl` também só inicia a missão com `ALLOW_MISSION_START=true`; o padrão permite validar conexão/upload sem iniciar automaticamente;
- upload, início, RTL e abortamento são etapas explícitas;
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

Variáveis principais: `API_BASE_URL`, `GATEWAY_API_KEY`, `GATEWAY_ID`, `MAVLINK_MODE`, `MAVLINK_CONNECTION`, `GATEWAY_JOURNAL_PATH`, limites preflight e intervalos. Consulte `../.env.example` e `../docs/DRONE_PROTOCOL.md`. O journal atômico evita repetir claim/start após reinício; em container, monte um volume persistente e aponte `GATEWAY_JOURNAL_PATH` para ele.

## Testes

```powershell
.\.venv\Scripts\ruff check .
.\.venv\Scripts\ruff format --check .
.\.venv\Scripts\pytest
```

Os testes unitários exercitam `PymavlinkVehicleGateway` com mensagens MAVLink falsas e conexão
controlada, inclusive ACKs, releitura, progresso e telemetria vencida. Eles não comprovam SITL,
Pixhawk, mecanismo físico, bancada nem voo real; essas validações continuam separadas e pendentes.
