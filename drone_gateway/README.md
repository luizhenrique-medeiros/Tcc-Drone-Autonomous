# Drone gateway

Processo separado que consulta missões autorizadas no backend e é o único componente com
acesso MAVLink. O modo padrão `simulation` não abre sockets. Os modos reais iniciam em
receive-only e não autorizam upload nem comandos de voo.

## Segurança

- o gateway nunca arma o veículo;
- `REAL_HARDWARE_ACKNOWLEDGED=false` torna `real`, `direct` e
  `mission_planner_forward` estritamente receive-only: sem heartbeat GCS, requests, alteração
  de intervalo, upload ou comando;
- `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false` e
  `ALLOW_MISSION_START=false` são os padrões;
- habilitar upload/comandos em hardware também exige o ACK real e uma chave de gateway não
  padrão;
- claim, upload, start e RTL exigem heartbeat válido; upload e comandos têm gates locais
  independentes;
- `abort` real não dispara flight termination: exige intervenção do operador ou RTL seguro;
- perda/stale de heartbeat causa fechamento do recurso e reconexão com backoff limitado;
- porta ausente, porta ocupada/acesso negado e endpoint aberto sem heartbeat têm erros distintos.

O ACK de upload gera `UPLOADED`. Somente a releitura da contagem e de todos os itens, seguida de
comparação com a missão autorizada, gera `VERIFIED`. O journal impede repetir automaticamente um
upload ou start cujo resultado ficou incerto após uma interrupção.

`VERIFIED` é um estado de espera: o gateway não arma e não inicia automaticamente. Um `START`
administrativo só é executável com `ALLOW_FLIGHT_COMMANDS=true`,
`ALLOW_MISSION_START=true`, veículo já armado pelo operador, preflight/heartbeat válidos e
missão ainda elegível no backend. O painel também exige snapshot fresco, conectado e pertencente
ao mesmo veículo da missão. `PAUSE` e `CONTINUE` usam o mesmo gate geral de comandos,
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

Os testes usam conexões e mensagens MAVLink falsas; não abrem a COM real. Resultado unitário,
build ou diagnóstico passivo não comprovam SITL, Pixhawk, mecanismo físico, bancada nem voo real.

Em 17 de agosto de 2026, Ruff, a verificação de formatação e **57 testes** passaram. Dois
diagnósticos passivos diretos anteriores receberam heartbeat real de `sysid=1`, `compid=1`, modo
`STABILIZE` e veículo desarmado; um ciclo integrado limitado publicou sete heartbeats no backend.
Depois da desconexão do cabo/link, `COM7` deixou de ser enumerada e o diagnóstico atual retorna
erro de porta ausente. Nenhum desses ensaios enviou missão, comando de modo, armamento ou voo;
forwarding pela UDP 14551, upload/releitura e comandos reais continuam sem validação.
