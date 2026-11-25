# Protocolo backend–gateway

## Recepção operacional PX4

```text
Pixhawk ↔ QGroundControl → encaminhamento UDP → gateway → API/painel
```

O gateway publica heartbeat com o snapshot recebido e envia observações
com identificação do veículo, origem e timestamps. Altitude relativa e AMSL
têm campos distintos. `current_ground_speed_m_s` é nulo quando a velocidade
atual não está disponível. Trate os campos ausentes e a idade da amostra
independentemente. O backend só associa progresso observado a uma missão
quando a evidência identifica a mesma revisão de forma inequívoca.

O runtime de observação ignora o journal de execução e a fila de comandos e
recusa as opções de escrita. O transporte não envia heartbeat GCS, pedidos
de taxa, consultas de parâmetros, transferências de missão ou comandos à
aeronave. Veja [Conexão PX4](CONEXAO_DRONE_PX4.md).

### Observação automática do voo

| Mensagem | Evidência utilizada |
|---|---|
| `HEARTBEAT` | Bit armado e modo PX4. Armado em solo exige estado do detector de pouso. Selecionar o modo Missão ou receber um índice em solo não indica execução. |
| `EXTENDED_SYS_STATE` | Estado de solo, decolagem, em voo e pouso em andamento. O pouso observado exige retorno a solo informado pelo PX4. |
| `GLOBAL_POSITION_INT` | Posição, altitude relativa ao Home e velocidade horizontal. Com estado de solo indisponível, o voo pode ser estimado quando armado, com referência recente de solo, ganho de pelo menos 3 m e velocidade horizontal de pelo menos 1,5 m/s sustentados por amostras ao longo de pelo menos 2 s. A estimativa não produz pouso. |
| `MISSION_CURRENT` | Sequência, número de itens, modo da missão, estado e identificador nativo, quando presentes e válidos. A execução requer evidência aérea e modo Missão. Estado pausado exige indicação explícita, mesmo se a aeronave estiver em espera. |
| `MISSION_ITEM_REACHED` | Item informado como alcançado. O gateway acrescenta IDs da origem e, quando válido, o identificador nativo do último `MISSION_CURRENT`. O backend deduplica itens na sessão e só os relaciona à missão se o vínculo estiver válido. |

No QGroundControl 5.1.5 para PX4, o Home planejado fica fora da lista transmitida.
No arquivo canônico, Takeoff, Waypoint e RTL correspondem aos índices MAVLink
0, 1 e 2. Revisões podem ter itens diferentes. O mapeamento é nomeado no painel
somente quando a evidência de releitura identifica a revisão e os itens. O
`mission_id` MAVLink é um identificador da controladora. O SHA-256 identifica
bytes do arquivo local. Alterações de ID, quantidade informada ou revisão
suspendem o vínculo dos itens após o início observado. A associação manual
permite acompanhar índices brutos, com correspondência pendente de verificação.
Veja [conjunto MAVLink Common](https://mavlink.io/en/messages/common.html#MISSION_CURRENT)
e [ajuste de sequência no QGroundControl 5.1.5](https://github.com/mavlink/qgroundcontrol/blob/v5.1.5/src/MissionManager/PlanManager.cc#L53-L85).

Durante execução, com posição válida em amostras de pelo menos 2 s a até 8 m
do destino, o painel pode indicar proximidade estimada. A confirmação pelo
waypoint exige `MISSION_ITEM_REACHED` com a sequência verificada. Uma saída em
RTL na sequência anterior ao destino, com vínculo verificado e sem lacuna
observada, permite identificar retorno antecipado. Nos demais retornos, a
passagem pelo destino pode ficar sem confirmação. Conclusão normal exige
destino confirmado, estado completo informado pelo PX4, pouso e desarmamento.
O pedido só conclui por confirmação administrativa de recebimento.

Na reconexão, os eventos refletem somente os estados observados. Leituras
ausentes não geram transições e o mapa separa trechos com amostras ausentes
ou intervalos maiores que 5 s. A visualização usa até 600 snapshots do voo
e 80 eventos recentes. O acompanhamento não utiliza um percentual de
distância, duração ou itens.

## Contratos históricos de simulação

As seções seguintes documentam estados e contratos legados cobertos em
testes isolados. Elas preservam a referência do protocolo de escrita.

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

O percentual recebido é preservado, nunca substituído por 100%. Em
`SYS_STATUS`/`BATTERY_STATUS`, percentual desconhecido (`-1`) ou fora de 0–100
limpa a leitura anterior; tensão desconhecida também permanece `null`, conforme
o [contrato MAVLink](https://mavlink.io/en/messages/common#BATTERY_STATUS).
Telemetria vencida não satisfaz preflight. Backend e gateway usam mínimo padrão
de 40%, recusam percentual ausente/abaixo do limite e mantêm ARM/START separados.

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
  relidas coincidentes com essa Home (tolerância de 1e-6 grau) e altitude MSL
  recebida em milímetros, convertida para metros (tolerância de 0,05 m).
  A distância Home–origem planejada deve respeitar `MAX_ORIGIN_DEVIATION_M`
  (30 m por padrão), o mesmo limite do preflight. A normalização é exclusiva do
  item zero: os pontos de voo/retorno/pouso mantêm comparação rigorosa com a rota
  autorizada. Home ausente, vencida, inválida, fora do limite ou divergente da
  releitura bloqueia; nenhuma Home, rota, hash ou revisão é alterada;
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

## Modos e evidência anterior

`simulation` usa o fake determinístico. A escrita PX4 para testes exige o
perfil SITL com isolamento de rede. Para observação real use
`qgroundcontrol_forward` ou o roteador UDP documentado em
[Conexão PX4](CONEXAO_DRONE_PX4.md). O perfil experimental `px4_bench_arm`
fica fora do runtime operacional.

Em 20 de agosto de 2026, uma sessão de recepção direta ArduPilot em COM7/57600
publicou 129 snapshots `HARDWARE_REAL`. A amostra ficou desatualizada após
encerrar o processo. O encaminhamento 14551 expirou porque a porta estava
configurada como Inbound. Nenhum dado MAVLink foi transmitido pelo gateway.

## Abortamento e RTL

No ensaio isolado, os endpoints legados verificam papel, estado e vínculo com o simulador. Na operação real, o operador controla retorno e intervenção pelo QGroundControl.
