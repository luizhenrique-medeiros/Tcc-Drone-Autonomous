# Protocolo backend–gateway

## Confiança e direção

O gateway chama a API por HTTPS/rede controlada usando `X-Gateway-API-Key`; nunca acessa PostgreSQL. O backend decide elegibilidade/autorização; ArduPilot decide estado físico em execução. Todo request crítico carrega correlação e identificador idempotente.

## Ciclo

```text
heartbeat → listar AUTHORIZED → claim atômico → preflight local
→ upload started → MAVLink upload/ACK → upload confirmed
→ execução autorizada → telemetria/eventos → entrega → retorno → conclusão
```

`claim` consome uma autorização vigente da mesma versão. Se outro gateway já assumiu, retorna conflito. Repetir a mesma chave pelo mesmo gateway devolve o resultado conhecido.

O aceite mundial do ponto no checkout não amplia o raio operacional: antes de upload ou início, o gateway rejeita a missão cuja rota ou waypoints excedam `MAX_MISSION_DISTANCE_M`.

Solicitações administrativas de `RTL`/`ABORT` viram comandos persistidos. O gateway consulta `/gateway/commands/pending`, acusa recebimento e publica `COMPLETED` ou `FAILED` por `event_id`; a transição física da missão continua sendo reportada separadamente. Um comando para missão que o processo não reconhece como ativa falha e exige intervenção, em vez de agir sobre veículo incerto.

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
  "origin_longitude": -46.5502
}
```

`source` é sempre um dos valores `UNKNOWN`, `SIMULATION`, `SITL` ou `HARDWARE_REAL`; somente o gateway determina essa origem a partir do modo configurado. `received_at` é carimbado no servidor e `is_stale` é derivado do limite de frescor. Ausência/desatualização não vira `connected=true`. Campo desconhecido é `null` e falha na verificação que o exige.

## Telemetria normalizada

`event_id`, missão, veículo, `occurred_at`, `received_at`, `source`, `is_stale`, latitude, longitude, altitude relativa, velocidade, bateria, GPS, modo, armamento e estado. Campos físicos ausentes permanecem `null`; não são convertidos em zero ou `false`. MAVLink bruto não cruza o contrato nem é persistido indiscriminadamente. A frequência de envio pode exceder a de persistência; amostras antigas não substituem o snapshot.

## Estado e mapeamento

- upload: `UPLOADING → UPLOADED` somente após ACK; timeout/ACK negativo → `FAILED` ou estado recuperável definido;
- execução: `DESTINATION_REACHED` exige o item de destino; `DELIVERY_CONFIRMED` significa somente que a sequência `MAV_CMD_DO_GRIPPER` foi alcançada/ultrapassada e **não comprova a entrega física do pacote**; `RETURNING` exige o início do retorno; `COMPLETED` exige `LAND` final alcançado, veículo desarmado e posição fresca próxima da origem;
- abortamento: `ABORTED` registra comando/resultado/estado físico;
- RTL é comando operacional e evento; não deve falsificar entrega/conclusão.

O gateway propõe no máximo uma transição operacional por ciclo, não pula revisão/autorização e não reenvia missão terminal/consumida. O progresso e o `event_id` pendente ficam em journal atômico persistente para retomada idempotente.

## Timeouts, retry e reconexão

- heartbeat e comandos têm timeout configurável;
- consultas HTTP usam backoff exponencial limitado e respeitam cancelamento;
- status crítico é idempotente; eventos usam UUID único;
- após queda do backend, o ArduPilot mantém a missão; ao reconectar, o gateway publica snapshot e reconcilia sem reexecutar;
- perda MAVLink gera alerta e segue failsafe/configuração do veículo, nunca alteração automática de parâmetros.

## Modos

`simulation` usa fake determinístico, sem socket, e publica `SIMULATION`. `sitl` usa pymavlink com conexão de desenvolvimento e publica `SITL`. `real` exige confirmação explícita, operador e checklist e publica `HARDWARE_REAL`. O mesmo DTO é usado nos três, mas evidências permanecem rotuladas; valor ausente ou legado é `UNKNOWN` e nunca recebe prontidão operacional.

No adaptador MAVLink, `MAVLINK_TARGET_SYSTEM_ID` e `MAVLINK_TARGET_COMPONENT_ID` filtram globalmente todas as mensagens operacionais. O gateway solicita `AUTOPILOT_VERSION` e intervalos dos tipos de telemetria necessários, sem alterar parâmetros de segurança. A conexão serial usa porta e baud explícitos; `python -m app.tools.list_ports` lista candidatas sem selecionar uma automaticamente.

## Abortamento e RTL

O admin solicita; backend verifica papel/estado e registra; gateway valida conexão e emite apenas o comando permitido pelo adaptador. A decisão entre RTL, pouso ou intervenção manual considera estado/área/ArduPilot e procedimento humano; não há `except` que converta falha em sucesso.
