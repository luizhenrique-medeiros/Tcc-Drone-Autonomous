# Protocolo backend–gateway

## Confiança e direção

O gateway chama a API por HTTPS/rede controlada usando `X-Gateway-API-Key`; nunca acessa PostgreSQL. O backend decide elegibilidade/autorização; ArduPilot decide estado físico em execução. Todo request crítico carrega correlação e identificador idempotente.

## Ciclo

```text
heartbeat → listar AUTHORIZED → claim atômico → preflight local
→ upload started → MAVLink upload/ACK → UPLOADED
→ releitura/comparação → VERIFIED → operador arma fisicamente
→ START administrativo + revalidação → EXECUTING
→ PAUSE/CONTINUE opcionais → telemetria/eventos → entrega → retorno → conclusão
```

`claim` consome uma autorização vigente da mesma versão. Se outro gateway já assumiu, retorna conflito. Repetir a mesma chave pelo mesmo gateway devolve o resultado conhecido.

O aceite mundial do ponto no checkout não amplia o raio operacional: antes de upload ou início, o gateway rejeita a missão cuja rota ou waypoints excedam `MAX_MISSION_DISTANCE_M`.

Solicitações administrativas de `START`, `PAUSE`, `CONTINUE`, `RTL` ou `ABORT` viram comandos persistidos. O gateway consulta `/gateway/commands/pending`, rejeita comando acima de `GATEWAY_COMMAND_MAX_AGE_SECONDS`, acusa recebimento e publica `COMPLETED` ou `FAILED` por `event_id`; a transição física da missão continua sendo reportada separadamente. Um comando para missão que o processo não reconhece como ativa falha e exige intervenção, em vez de agir sobre veículo incerto.

## DTO de saúde

```json
{
  "gateway_id": "dev-gateway-01",
  "vehicle_identifier": "pixhawk-6c-01",
  "vehicle_name": "Drone acadêmico",
  "autopilot_system": "ARDUPILOT",
  "source": "HARDWARE_REAL",
  "received_at": "2026-08-06T18:42:10Z",
  "is_stale": false,
  "connected": true,
  "heartbeat": true,
  "flight_mode": "GUIDED",
  "armed": false,
  "gps_fix_type": 3,
  "satellites": 14,
  "ekf_ok": true,
  "battery_percent": 76,
  "battery_voltage": 22.4,
  "preflight_ok": true,
  "rtl_configured": true,
  "geofence_enabled": true,
  "origin_latitude": -23.1175,
  "origin_longitude": -46.5502,
  "connection_state": "CONNECTED",
  "connection_mode": "direct",
  "connection_topology": "direct_serial",
  "connection_endpoint": "COM7",
  "serial_port": "COM7",
  "connection_baud": 57600,
  "mavlink_system_id": 1,
  "mavlink_component_id": 1,
  "heartbeat_age_seconds": 0.1,
  "mission_upload_enabled": false,
  "flight_commands_enabled": false,
  "mission_start_enabled": false,
  "connection_error": null
}
```

`source` é sempre um dos valores `UNKNOWN`, `SIMULATION`, `SITL` ou `HARDWARE_REAL`; somente o gateway determina essa origem a partir do modo configurado. `received_at` é carimbado no servidor e `is_stale` é derivado do limite de frescor. Ausência/desatualização não vira `connected=true`. Campo desconhecido é `null` e falha na verificação que o exige.

## Telemetria normalizada

`event_id`, missão, veículo, `occurred_at`, `received_at`, `source`, `is_stale`, latitude, longitude, altitude relativa, velocidade, bateria, GPS, modo, armamento e estado. Campos físicos ausentes permanecem `null`; não são convertidos em zero ou `false`. MAVLink bruto não cruza o contrato nem é persistido indiscriminadamente. A frequência de envio pode exceder a de persistência; amostras antigas não substituem o snapshot.

## Estado e mapeamento

- upload: `UPLOADING → UPLOADED` somente após ACK; `UPLOADED → VERIFIED` somente após releitura/comparação integral; timeout, ACK negativo ou divergência nunca viram sucesso;
- início: `VERIFIED → EXECUTING` exige `START` persistido, heartbeat/preflight atuais, `ALLOW_FLIGHT_COMMANDS=true`, `ALLOW_MISSION_START=true` e veículo já armado pelo operador; o gateway não arma;
- pausa: estados executáveis → `PAUSED` somente após ACK de `MAV_CMD_DO_PAUSE_CONTINUE`; `CONTINUE` só é permitido em `PAUSED` e retorna a `EXECUTING` após ACK;
- execução: `DESTINATION_REACHED` exige o item de destino; `DELIVERY_CONFIRMED` significa somente que a sequência `MAV_CMD_DO_GRIPPER` foi alcançada/ultrapassada e **não comprova a entrega física do pacote**; `RETURNING` exige o início do retorno; `COMPLETED` exige `LAND` final alcançado, veículo desarmado e posição fresca próxima da origem;
- abortamento: `ABORTED` registra comando/resultado/estado físico;
- RTL é comando operacional e evento; não deve falsificar entrega/conclusão.

O gateway propõe no máximo uma transição operacional por ciclo, não pula revisão/autorização e não reenvia missão terminal/consumida. O progresso e o `event_id` pendente ficam em journal atômico persistente para retomada idempotente.

## Timeouts, retry e reconexão

- heartbeat e comandos têm timeout configurável; porta aberta ou bytes sem heartbeat do `system/component` alvo não definem conexão;
- consultas HTTP usam backoff exponencial limitado e respeitam cancelamento;
- status crítico é idempotente; eventos usam UUID único;
- após queda do backend, o ArduPilot mantém a missão; ao reconectar, o gateway publica snapshot e reconcilia sem reexecutar;
- se `PAUSE`/`CONTINUE` foi confirmado pelo veículo e a publicação HTTP falhou, a fase persistida
  permite concluir o mesmo comando `ACKNOWLEDGED` sem reenviá-lo ao autopiloto;
- perda MAVLink gera alerta e segue failsafe/configuração do veículo, nunca alteração automática de parâmetros.

Um componente MAVLink difunde heartbeat periodicamente, normalmente perto de 1 Hz. O gateway usa o heartbeat recebido do alvo para presença/frescor e não confunde seu próprio heartbeat de GCS com o do autopiloto. No diagnóstico somente leitura não há transmissão do gateway. Quando uma sessão bidirecional for autorizada, heartbeat de GCS usa source system/component próprios e não altera o alvo configurado.

`MAV_CMD_SET_MESSAGE_INTERVAL` é um comando e exige `COMMAND_ACK`; não faz parte do diagnóstico passivo. Em operação bidirecional, Mission Planner ou gateway deve ser o único responsável pelas taxas para evitar disputa com `REQUEST_DATA_STREAM`. Todo comando permitido casa o ACK com comando/alvo; `MAV_RESULT_ACCEPTED` é aceite, `MAV_RESULT_IN_PROGRESS` exige aguardar o ACK final, e ausência/resultado negativo após retry é falha.

No Mission Protocol, upload segue `MISSION_COUNT` → pares `MISSION_REQUEST_INT`/`MISSION_ITEM_INT` → `MISSION_ACK` aceito. A verificação baixa a missão com `MISSION_REQUEST_LIST` → `MISSION_COUNT` → pares `MISSION_REQUEST_INT`/`MISSION_ITEM_INT` e emite o ACK final do receptor. Tipo, sequência, contagem e alvo são conferidos; `MISSION_REQUEST`/`MISSION_ITEM` são legados e não são originados pelo gateway. Toda espera possui timeout/retry limitado; como referência de interoperabilidade, a especificação recomenda 1500 ms no geral, 250 ms para itens e no máximo cinco tentativas. Esgotamento cancela a operação e retorna a idle sem publicar sucesso.

## Modos

`simulation` usa fake determinístico, sem socket, e publica `SIMULATION`. `sitl` usa Pymavlink com conexão de desenvolvimento e publica `SITL`. Para compatibilidade, `real` continua representando hardware com conexão explícita; as duas topologias reais preferidas são `direct` e `mission_planner_forward`, ambas publicando `HARDWARE_REAL` somente a partir de amostras ao vivo. O mesmo DTO é usado, mas evidências permanecem rotuladas; valor ausente ou legado é `UNKNOWN` e nunca recebe prontidão operacional.

```text
direct:
  MAVLINK_MODE=direct
  MAVLINK_CONNECTION=COM7
  MAVLINK_BAUD=57600
  gateway é o único dono da COM

mission_planner_forward:
  MAVLINK_MODE=mission_planner_forward
  Mission Planner é o único dono de COM7 @ 57600
  Mavlink Mirror = UDP Client → 127.0.0.1:14551, Write access OFF
  MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551
```

No estado observado, o Mission Planner possuía um listener AutoConnect **Mavlink alt port**, UDP 14551, direção **Inbound**. Ele recebe tráfego destinado ao Mission Planner e não encaminha a `COM7`; precisa ser desabilitado para o gateway conseguir fazer bind em `udpin:127.0.0.1:14551`. O mirror só é iniciado depois de o Mission Planner conectar à `COM7` a 57600.

O baseline de leitura mantém `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false`. Nesse estado, não se envia heartbeat de GCS, pedido de intervalo, missão, comando, modo ou armamento. Registrar `REAL_HARDWARE_ACKNOWLEDGED=true`, habilitar **Write access** no mirror e definir `ALLOW_MISSION_UPLOAD=true` requer sessão posterior autorizada e permite somente upload/releitura desarmados; `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false` continuam bloqueando comandos e início. Mesmo em etapa futura, o software não envia armamento.

No adaptador MAVLink, `MAVLINK_TARGET_SYSTEM_ID` e `MAVLINK_TARGET_COMPONENT_ID` filtram globalmente todas as mensagens operacionais. Fora do diagnóstico passivo e somente com escrita autorizada, o gateway pode solicitar `AUTOPILOT_VERSION` e intervalos dos tipos de telemetria necessários, sem alterar parâmetros de segurança. A conexão serial usa porta e baud explícitos; `python -m app.tools.list_ports` lista candidatas sem selecionar uma automaticamente.

Para auditoria, cada amostra registra fonte e frescor. Em 17 de agosto de 2026, a primeira tentativa direta encontrou a COM7 ocupada pelo Mission Planner. Depois de liberar a porta, dois diagnósticos passivos receberam heartbeat real de `sysid=1`, `compid=1`, modo `STABILIZE` e `armed=false`; um ciclo limitado publicou sete heartbeats normalizados no backend. Não foram solicitados intervalos nem enviados missão/comandos. Ao final, o link foi desconectado: não havia porta serial nem listeners UDP 14550/14551, o Mission Planner estava fechado e o diagnóstico terminou com `VEHICLE_PORT_NOT_FOUND`/exit 2. O snapshot atual é `HARDWARE_REAL`, `ERROR`, modo `direct`, COM7/57600 e três gates falsos. Forwarding, GPS/bateria/EKF/home ao vivo, upload/releitura, armamento e voo permanecem não comprovados.

## Abortamento e RTL

O admin solicita; backend verifica papel/estado e registra; gateway valida conexão e emite apenas o comando permitido pelo adaptador. A decisão entre RTL, pouso ou intervenção manual considera estado/área/ArduPilot e procedimento humano; não há `except` que converta falha em sucesso.
