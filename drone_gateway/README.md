# Drone gateway

Processo separado que consulta missões autorizadas no backend e é o único componente com
acesso MAVLink. O modo padrão `simulation` não abre sockets. Os modos reais iniciam em
receive-only e não autorizam upload nem comandos de voo.

## Segurança

- o gateway nunca arma no startup, heartbeat, diagnóstico ou progressão automática; `ARM`
  existe somente como comando administrativo explícito e usa o armamento normal do ArduPilot;
- `REAL_HARDWARE_ACKNOWLEDGED=false` torna `real`, `direct` e
  `mission_planner_forward` estritamente receive-only: sem heartbeat GCS, requests, alteração
  de intervalo, upload ou comando;
- `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false`,
  `ALLOW_MISSION_START=false` e `ALLOW_VEHICLE_ARM=false` são os padrões;
- habilitar upload/comandos em hardware também exige o ACK real, uma chave de gateway não
  padrão e `GATEWAY_ID` idêntico no backend e no processo do gateway;
- claim, upload, start e RTL exigem heartbeat válido; upload e comandos têm gates locais
  independentes;
- `abort` real não dispara flight termination: exige intervenção do operador ou RTL seguro;
- perda/stale de heartbeat causa fechamento do recurso e reconexão com backoff limitado;
- porta ausente, porta ocupada/acesso negado e endpoint aberto sem heartbeat têm erros distintos.

O ACK de upload gera `UPLOADED`. Somente a releitura da contagem e de todos os itens, seguida de
comparação com a missão autorizada, gera `VERIFIED`. O journal impede repetir automaticamente um
upload ou start cujo resultado ficou incerto após uma interrupção.

`VERIFIED` com fase local `WAITING_OPERATOR_ARM` é o estado de espera; não há armamento ou
início automático.
Um `ARM` administrativo só é executável com `ALLOW_VEHICLE_ARM=true`,
`ALLOW_FLIGHT_COMMANDS=true` e `ALLOW_MISSION_START=true`, comando ainda fresco, heartbeat
ArduPilot atual, `SYS_STATUS` atual com preflight aprovado e modo `STABILIZE`. Em
hardware, a configuração também exige `REAL_HARDWARE_ACKNOWLEDGED=true` e uma chave de gateway
não padrão. O gateway envia somente o comando normal: não altera parâmetros, não ignora checks
de pre-arm e não oferece variante de bypass.

O sucesso de `ARM` exige duas evidências na mesma transação: `COMMAND_ACK` do comando correto,
originado no autopiloto alvo e endereçado exatamente ao system/component do gateway, e um
`HEARTBEAT` novo com `armed=true`. Ausência de ACK pode gerar no máximo três envios idempotentes
somente enquanto nenhum heartbeat novo indicar `armed=true`. Qualquer evidência armada torna o
resultado incerto e encerra sem novo envio, mesmo que um heartbeat seguinte indique desarmado. Os
retries usam `confirmation` crescente e deadline total limitado; rejeição terminal não é repetida. Um
`ARM` ainda `PENDING` encontra `armed=true` e reconcilia sem enviar MAVLink. Depois de restart, um
comando já `ACKNOWLEDGED` somente conclui com `armed=true`; `false` ou valor indisponível falha
como resultado incerto e nunca é reenviado.

Cada request ao backend envia `X-Gateway-API-Key` e `X-Gateway-ID`. O backend vincula os dois ao
`GATEWAY_ID` configurado e rejeita identidade divergente em header, query ou payload antes de
entregar ou confirmar comandos.

Um `START` administrativo só é executável com `ALLOW_FLIGHT_COMMANDS=true`,
`ALLOW_MISSION_START=true`, veículo comprovadamente armado, preflight/heartbeat válidos e missão
ainda elegível no backend. O painel também exige snapshot fresco, conectado e pertencente ao mesmo
veículo da missão. `PAUSE` e `CONTINUE` usam o mesmo gate geral de comandos,
publicam `PAUSED`/`EXECUTING` somente após ACK e também respeitam idade máxima configurada do
comando. As três ações são distintas de upload, RTL e abortamento.

Se o autopiloto confirmou `PAUSE` ou `CONTINUE`, mas a publicação HTTP seguinte falhou, a fase
local fica no journal. Ao reencontrar o mesmo comando já `ACKNOWLEDGED`, o gateway conclui a
reconciliação no backend sem reenviar o comando ao veículo.

## Topologias MAVLink

Conexão serial direta, com nenhum outro programa ocupando a COM:

```dotenv
MAVLINK_MODE=direct
MAVLINK_CONNECTION=COM7
MAVLINK_BAUD=57600
MAVLINK_SOURCE_COMPONENT_ID=190
```

Mission Planner dono da COM e encaminhando MAVLink por UDP:

```dotenv
MAVLINK_MODE=mission_planner_forward
MAVLINK_CONNECTION=COM7
MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551
MAVLINK_BAUD=57600
MAVLINK_SOURCE_COMPONENT_ID=190
```

Em `mission_planner_forward`, o endpoint efetivamente aberto pelo gateway é
`MAVLINK_FORWARD_CONNECTION`. `MAVLINK_CONNECTION` e `MAVLINK_BAUD` descrevem a COM upstream do
Mission Planner e são enviados ao diagnóstico operacional. Não abra a mesma COM simultaneamente
no gateway e no Mission Planner.

Compatibilidade permanece para `simulation`, `sitl` e `real`; em `real`, a topologia é inferida
do tipo de `MAVLINK_CONNECTION`. Para configuração nova, prefira `direct` ou
`mission_planner_forward`, pois são explícitos.

No Docker, o Compose deriva modo/conexão exclusivamente de `GATEWAY_CONTAINER_MAVLINK_MODE` e
`GATEWAY_CONTAINER_MAVLINK_CONNECTION`, define `GATEWAY_RUNTIME=container` e o gateway recusa
`real`, `direct` e `mission_planner_forward`. `scripts/start_gateway.ps1` define runtime host; é o
único launcher destinado a COM7 ou forwarding local.

## Diagnóstico receive-only

Listar configuração e portas sem abrir qualquer endpoint:

```powershell
python -m app.tools.mavlink_diagnose
python -m app.tools.mavlink_diagnose --json
```

Observar passivamente heartbeat e telemetria no endpoint configurado:

```powershell
python -m app.tools.mavlink_diagnose --connect --observe-seconds 5
```

Mesmo com `--connect`, o diagnóstico nunca envia heartbeat GCS, requests, missão ou comando. Ele
também sobrescreve `ALLOW_VEHICLE_ARM` para `false` internamente. Ele
retorna exit code `2` se não abrir o endpoint ou não obtiver heartbeat. A saída humana usa
`indisponível` para dados não recebidos; não completa telemetria com zero/false. O comando
instalado equivalente é `drone-gateway-diagnose`.

A listagem serial isolada continua disponível:

```powershell
python -m app.tools.list_ports
python -m app.tools.list_ports --json
```

## Progressão observada da missão

Estados operacionais só são sugeridos a partir de evidência MAVLink explícita, em ordem:

1. `DESTINATION_REACHED`: `MISSION_ITEM_REACHED` do waypoint canônico de destino;
2. `DELIVERY_CONFIRMED`: sequência `MAV_CMD_DO_GRIPPER` alcançada/ultrapassada;
3. `RETURNING`: `MISSION_CURRENT`/`MISSION_ITEM_REACHED` iniciou o retorno canônico;
4. `COMPLETED`: `LAND` final alcançado, veículo desarmado e posição próxima da origem.

`DELIVERY_CONFIRMED` confirma apenas o comando do mecanismo; não comprova fisicamente a entrega.

## Execução e testes

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m app.main

.\.venv\Scripts\python -m ruff check app tests
.\.venv\Scripts\python -m ruff format --check app tests
.\.venv\Scripts\python -m pytest
```

Os testes usam conexões e mensagens MAVLink falsas; não abrem a COM real. O armamento do adaptador
`simulation` altera somente estado em memória e não constitui evidência de hardware. Resultado unitário,
build ou diagnóstico passivo não comprovam SITL, Pixhawk, mecanismo físico, bancada nem voo real.

Em 21 de agosto de 2026, Ruff, formatação e **85 testes** passaram sem abrir hardware. Em 20 de
agosto, uma sessão direta receive-only de cinco minutos em COM7/57600 publicou 129 snapshots
`HARDWARE_REAL`: `sysid=1`, `compid=1`,
`STABILIZE`, `armed=false`, bateria 74–75%, GPS máximo fix 3/5 satélites e final fix 1/0,
EKF/preflight falsos e home/origin ausentes. REST/WS mostraram a origem real e o snapshot ficou
stale após a parada. O forwarding pela UDP 14551 expirou sem heartbeat porque estava configurado
como Inbound. Nenhum ensaio enviou missão, comando, start, armamento ou voo; upload/releitura,
ensaio de motor e voo continuam sem validação.
