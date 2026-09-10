# Protocolo backend–gateway

## Versão substituída durante pré-voo

Em `WAITING_OPERATOR_ARM`, somente com os quatro gates locais falsos, heartbeat
fresco, origem SITL/HARDWARE_REAL e STABILIZE desarmado, o executor consulta
`POST /gateway/missions/{id}/release-retired-version`. O backend só reconhece
versão/hash/gateway presentes na revisão administrativa auditada. A resposta
é validada contra o journal e o estado físico é relido antes de liberá-lo.
Resultado perdido, divergente ou veículo armado conserva o journal; nenhum
comando MAVLink é enviado. O fluxo não se aplica a START incerto ou execução.
O reconhecimento no servidor antecede a limpeza local; retry é idempotente.
O arquivo antigo na Pixhawk não é apagado por esse procedimento. A próxima
versão depende de exportação/revisão/autorização e upload/releitura próprios.

## Confiança e direção

O gateway chama a API por HTTPS/rede controlada usando `X-Gateway-API-Key` e `X-Gateway-ID`;
o backend vincula a identidade ao `GATEWAY_ID` configurado e não confia no ID autodeclarado do
payload. O gateway nunca acessa PostgreSQL. O backend decide elegibilidade/autorização; ArduPilot
decide estado físico em execução. Todo request crítico carrega correlação e identificador idempotente.

## Ciclo

```text
heartbeat → listar AUTHORIZED → claim atômico → preflight local
→ upload started → MAVLink upload/ACK → UPLOADED
→ releitura/comparação → VERIFIED → ARM administrativo normal
→ COMMAND_ACK + heartbeat armed → START administrativo separado
→ revalidação → EXECUTING
→ PAUSE/CONTINUE opcionais → telemetria/eventos → entrega → retorno → conclusão
```

`claim` consome uma autorização vigente da mesma versão. Se outro gateway já assumiu, retorna conflito. Repetir a mesma chave pelo mesmo gateway devolve o resultado conhecido.

Em `VERIFIED`, o mesmo `claim` relê a autoridade consumida atual para o gateway
vinculado. Renovação administrativa emite novo registro sem alterar artefato ou
causar upload. Antes de ARM/START com prazo local vencido, o executor busca esse
claim, exige novo ID vigente e compara missão inteira (exceto status) e arquivo
com o journal. Falha fecha a operação. Ver [API](API.md).

Em `WAITING_OPERATOR_ARM`, `read_telemetry` publica amostras passivas com horário
original de `GLOBAL_POSITION_INT`, sem avaliar progresso ou exigir gates de
mutação. Posição vencida/ausente não gera substituto fictício. O fake identifica
suas amostras como `SIMULATION`.

O aceite mundial do ponto no checkout não amplia o raio operacional: antes de upload ou início, o gateway rejeita a missão cuja rota ou waypoints excedam `MAX_MISSION_DISTANCE_M`.

Solicitações administrativas de ARM, `START`, `PAUSE`, `CONTINUE`, `RTL` ou `ABORT` viram comandos persistidos. ARM só entra por `POST /api/v1/admin/missions/{id}/arm`; o endpoint genérico recusa essa ação. O gateway consulta `/gateway/commands/pending`, rejeita comando acima de `GATEWAY_COMMAND_MAX_AGE_SECONDS`, acusa recebimento e publica `COMPLETED` ou `FAILED` por `event_id`; a transição física da missão continua sendo reportada separadamente. Um comando para missão que o processo não reconhece como ativa falha e exige intervenção, em vez de agir sobre veículo incerto.

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
  "vehicle_arm_enabled": false,
  "connection_error": null
}
```

`source` é sempre um dos valores `UNKNOWN`, `SIMULATION`, `SITL` ou `HARDWARE_REAL`; somente o gateway determina essa origem a partir do modo configurado. `received_at` é carimbado no servidor e `is_stale` é derivado do limite de frescor. Ausência/desatualização não vira `connected=true`. Campo desconhecido é `null` e falha na verificação que o exige. `gps_fix_type` aceita todo o enum `GPS_FIX_TYPE` padronizado pelo MAVLink, de `0` a `8`; a elegibilidade continua exigindo valor `3` ou superior e o mínimo configurado de satélites.

## Telemetria normalizada

`event_id`, missão, veículo, `occurred_at`, `received_at`, `source`, `is_stale`, latitude, longitude, altitude relativa, velocidade, bateria, GPS, modo, armamento e estado. Campos físicos ausentes permanecem `null`; não são convertidos em zero ou `false`. MAVLink bruto não cruza o contrato nem é persistido indiscriminadamente. A frequência de envio pode exceder a de persistência; amostras antigas não substituem o snapshot.

## Estado e mapeamento

- upload: `UPLOADING → UPLOADED` somente após ACK; `UPLOADED → VERIFIED` somente após releitura/comparação integral; timeout, ACK negativo ou divergência nunca viram sucesso;
- armamento: missão permanece `VERIFIED`/em espera; ARM normal exige missão ativa/reivindicada, heartbeat/preflight atuais, origem `SITL` ou `HARDWARE_REAL`, modo `STABILIZE`, veículo desarmado e `ALLOW_VEHICLE_ARM=true`, `ALLOW_FLIGHT_COMMANDS=true` e `ALLOW_MISSION_START=true`; receber/persistir o comando não significa que o veículo armou;
- início: `VERIFIED → EXECUTING` exige `START` persistido, heartbeat/preflight atuais, `ALLOW_FLIGHT_COMMANDS=true`, `ALLOW_MISSION_START=true` e heartbeat já confirmando `armed=true`; `START` não inclui ARM;
- pausa: estados executáveis → `PAUSED` somente após ACK de `MAV_CMD_DO_PAUSE_CONTINUE`; `CONTINUE` só é permitido em `PAUSED` e retorna a `EXECUTING` após ACK;
- execução: `DESTINATION_REACHED` exige o item de destino; `DELIVERY_CONFIRMED` significa somente que a sequência `MAV_CMD_DO_GRIPPER` foi alcançada/ultrapassada e **não comprova a entrega física do pacote**; `RETURNING` exige o início do retorno; `COMPLETED` exige `LAND` final alcançado, veículo desarmado e posição fresca próxima da origem;
- abortamento: `ABORTED` registra comando/resultado/estado físico;
- RTL é comando operacional e evento; não deve falsificar entrega/conclusão.

O gateway propõe no máximo uma transição operacional por ciclo, não pula revisão/autorização e não reenvia missão terminal/consumida. O progresso e o `event_id` pendente ficam em journal atômico persistente para retomada idempotente.

## Armamento normal

O backend só cria ARM para missão `VERIFIED`, já reivindicada pelo gateway ligado ao mesmo veículo, e depois de validar o payload administrativo estrito, o snapshot fresco/completo e os três gates operacionais. O gateway repete identidade, fase, idade, origem, saúde, preflight, modo e gates antes de transmitir. Qualquer valor ausente, nulo, stale ou divergente falha fechado.

O recebimento drena rajadas sem o antigo limite de 50 mensagens por ciclo: cada
leitura normal tem orçamento de 100 ms e teto de 10.000 mensagens. Antes de ARM,
a mesma rotina dispõe de no máximo 1 segundo (ou do timeout de comando, se menor),
com o mesmo teto. Só observar a fila vazia permite prosseguir; atingir qualquer
limite marca a conexão como `STALE`, impede tratar campos enfileirados como atuais
e bloqueia ARM antes da transmissão. Não há descarte/flush de pacotes, mudança
de taxa do autopiloto ou supressão de pre-arm para superar esse bloqueio.
Mensagens e ACKs anteriores são consumidos antes da transação; modo, armamento e
`SYS_STATUS` são reavaliados após a drenagem, e um ACK antigo nunca confirma o ARM
novo. A recuperação da fila restaura apenas a leitura, sem reenviar comandos.

Antes da escrita MAVLink, o gateway persiste `ACKNOWLEDGED`, distinguindo “recebi a solicitação” de “o veículo armou”. A única transmissão permitida é:

```text
MAV_CMD_COMPONENT_ARM_DISARM
param1 = 1   # arm normal
param2 = 0   # sem force/bypass
param3..7 = 0
```

Não há comando de safety-off, mudança de modo, alteração de parâmetro nem valor mágico de force. O ACK é aceito somente quando corresponde ao comando e aos alvos da transação; `MAV_RESULT_IN_PROGRESS` mantém a espera pelo resultado final. `MAV_RESULT_ACCEPTED` ainda não conclui ARM: o gateway aguarda um heartbeat posterior do autopiloto alvo com `MAV_MODE_FLAG_SAFETY_ARMED`, publica imediatamente esse health no backend e só então solicita `COMPLETED`. O backend também exige esse snapshot novo/fresco com `armed=true` e origem permitida antes de aceitar a conclusão.

Retry de transporte, quando aplicável, é limitado à mesma transação ainda sem resultado. Depois de timeout, ACK negativo, falha ou resultado incerto, não há nova tentativa lógica nem rearmamento automático. Na reconciliação, ARM `PENDING` que encontra `armed=true` é concluído sem nova escrita; ARM `ACKNOWLEDGED` após restart só conclui se o heartbeat atual confirma `armed=true`, caso contrário falha como resultado incerto e não é reenviado. Desarmamento posterior atualiza telemetria/evento e nunca dispara ARM.

## Timeouts, retry e reconexão

- heartbeat e comandos têm timeout configurável; porta aberta ou bytes sem heartbeat do `system/component` alvo não definem conexão;
- consultas HTTP usam backoff exponencial limitado e respeitam cancelamento;
- status crítico é idempotente; eventos usam UUID único;
- após queda do backend, o ArduPilot mantém a missão; ao reconectar, o gateway publica snapshot e reconcilia sem reexecutar;
- se `PAUSE`/`CONTINUE` foi confirmado pelo veículo e a publicação HTTP falhou, a fase persistida
  permite concluir o mesmo comando `ACKNOWLEDGED` sem reenviá-lo ao autopiloto;
- se ARM ficou `ACKNOWLEDGED`, a retomada usa apenas heartbeat para reconciliar; ausência de `armed=true` falha sem reenvio;
- perda MAVLink gera alerta e segue failsafe/configuração do veículo, nunca alteração automática de parâmetros.

Um componente MAVLink difunde heartbeat periodicamente, normalmente perto de 1 Hz. O gateway usa o heartbeat recebido do alvo para presença/frescor e não confunde seu próprio heartbeat de GCS com o do autopiloto. No diagnóstico somente leitura não há transmissão do gateway. Quando uma sessão bidirecional for autorizada, heartbeat de GCS usa source system/component próprios e não altera o alvo configurado.

`MAV_CMD_SET_MESSAGE_INTERVAL` é um comando e exige `COMMAND_ACK`; não faz parte do diagnóstico passivo. Em operação bidirecional, Mission Planner ou gateway deve ser o único responsável pelas taxas para evitar disputa com `REQUEST_DATA_STREAM`. Todo comando permitido casa o ACK com comando/alvo; `MAV_RESULT_ACCEPTED` é aceite, `MAV_RESULT_IN_PROGRESS` exige aguardar o ACK final, e ausência/resultado negativo após retry é falha.

No Mission Protocol, upload segue `MISSION_COUNT` → pares `MISSION_REQUEST_INT`/`MISSION_ITEM_INT` → `MISSION_ACK` aceito. A verificação baixa a missão com `MISSION_REQUEST_LIST` → `MISSION_COUNT` → pares `MISSION_REQUEST_INT`/`MISSION_ITEM_INT` e emite o ACK final do receptor. Tipo, sequência, contagem e alvo são conferidos; `MISSION_REQUEST`/`MISSION_ITEM` são legados e não são originados pelo gateway, mas um `MISSION_REQUEST` legado recebido durante o upload é atendido com `MISSION_ITEM_INT`. Toda espera possui timeout/retry limitado; como referência de interoperabilidade, a especificação recomenda 1500 ms no geral, 250 ms para itens e no máximo cinco tentativas. Esgotamento cancela a operação e retorna a idle sem publicar sucesso.

### Equivalência na releitura ArduCopter

A comparação preserva contagem, sequência, comando, `autocontinue`, parâmetros,
coordenadas e altitude. Normaliza somente representações equivalentes:

- frames globais `0/5`, relativos à Home `3/6` e relativos ao terreno `10/11`
  são pares equivalentes; não se troca uma referência de altitude por outra;
- `current` recebido deve ser `0` ou `1`, mas representa estado de execução e não
  precisa repetir o marcador do arquivo enviado;
- o item zero canônico (`NAV_WAYPOINT`, altitude relativa zero) pode ser devolvido
  como Home absoluta. Nesse caso exige `HOME_POSITION` recente do alvo, coordenadas
  coincidentes com a origem planejada e altitude MSL recebida em milímetros,
  convertida para metros. Ausência, vencimento, mudança da Home ou altitude
  divergente bloqueiam a verificação; a Home nunca é alterada para fazer o teste passar;
- `DO_GRIPPER` pode retornar frame global ou de missão e posição zerada, pois não
  contém posição operacional. Comando e quatro parâmetros continuam comparados;
- `LOITER_TIME.param3` e `LAND.param4` enviados com valor padrão `0` podem retornar
  exatamente `1`: o AP_Mission persiste flags de direção nesses campos. A exceção
  é restrita a esses dois pares comando/campo e ao padrão zero; não aceita `-1`,
  outros valores, parâmetros não padrão ou mudanças nos demais campos.

As tolerâncias posicionais continuam absolutas: `1e-6` grau e `0,05 m` na altitude.
Essas equivalências não validam a GeoFence, não comprovam entrega física e não
habilitam upload, ARM ou START. A conversão de Home não se aplica a outros itens.

Referências fixadas na versão analisada:
[AP_Mission do ArduCopter 4.6.3](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/AP_Mission/AP_Mission.cpp)
e [MissionItemProtocol_Waypoints](https://github.com/ArduPilot/ardupilot/blob/Copter-4.6.3/libraries/GCS_MAVLink/MissionItemProtocol_Waypoints.cpp).
Os testes usam doubles determinísticos, inclusive uma missão completa de sete itens;
não constituem upload/releitura executados contra SITL ou Pixhawk.

## Modos

`simulation` usa fake determinístico, sem socket, e publica `SIMULATION`. `sitl` usa Pymavlink com conexão de desenvolvimento e publica `SITL`. Para compatibilidade, `real` continua representando hardware com conexão explícita; as duas topologias reais preferidas são `direct` e `mission_planner_forward`, ambas publicando `HARDWARE_REAL` somente a partir de amostras ao vivo. O mesmo DTO é usado, mas evidências permanecem rotuladas; valor ausente ou legado é `UNKNOWN` e nunca recebe prontidão operacional.

No Compose, `GATEWAY_RUNTIME=container` usa variáveis `GATEWAY_CONTAINER_*` separadas e recusa
`real`, `direct` e `mission_planner_forward`. O launcher Windows define runtime host; somente ele
pode abrir COM7 ou o endpoint local encaminhado pelo Mission Planner.

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

O baseline de leitura mantém `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false`, `ALLOW_MISSION_START=false` e `ALLOW_VEHICLE_ARM=false`. Nesse estado, não se envia heartbeat de GCS, pedido de intervalo, missão, comando, modo ou armamento. Registrar `REAL_HARDWARE_ACKNOWLEDGED=true`, habilitar **Write access** no mirror e definir `ALLOW_MISSION_UPLOAD=true` requer sessão posterior autorizada e permite somente upload/releitura desarmados; os outros três gates continuam falsos. Uma sessão posterior de ARM exige habilitar deliberadamente `ALLOW_VEHICLE_ARM`, `ALLOW_FLIGHT_COMMANDS` e `ALLOW_MISSION_START`, além de satisfazer todos os checks; esses valores nunca são inferidos de ambiente, conexão ou estado da UI.

No adaptador MAVLink, `MAVLINK_TARGET_SYSTEM_ID` e `MAVLINK_TARGET_COMPONENT_ID` filtram globalmente todas as mensagens operacionais. Fora do diagnóstico passivo e somente com escrita autorizada, o gateway pode solicitar `AUTOPILOT_VERSION` e intervalos dos tipos de telemetria necessários, sem alterar parâmetros de segurança. A conexão serial usa porta e baud explícitos; `python -m app.tools.list_ports` lista candidatas sem selecionar uma automaticamente.

Para auditoria, cada amostra registra fonte e frescor. Em 20 de agosto de 2026, uma sessão
receive-only direta em COM7/57600 publicou 129 snapshots `HARDWARE_REAL`: alvo `1/1`,
`STABILIZE`, `armed=false`, bateria 74–75%, GPS máximo fix 3/5 satélites e final fix 1/0,
EKF/preflight falsos e home/origin ausentes. REST/WS refletiram a origem e, após parar,
`is_stale=true`. Nenhum intervalo, missão, comando ou byte de escrita foi enviado. O forwarding
14551 expirou sem heartbeat porque estava configurado como Inbound. Upload/releitura, ensaio de
motor, armamento e voo permanecem não comprovados.

## Abortamento e RTL

O admin solicita; backend verifica papel/estado e registra; gateway valida conexão e emite apenas o comando permitido pelo adaptador. A decisão entre RTL, pouso ou intervenção manual considera estado/área/ArduPilot e procedimento humano; não há `except` que converta falha em sucesso.
