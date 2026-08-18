# Mission Planner, Pixhawk e MAVLink no Windows

Este procedimento prepara a integração com a Pixhawk 6C sem armar, iniciar missão ou alterar parâmetros. O gateway é o único componente do projeto que usa Pymavlink. Backend, admin e Flutter recebem apenas contratos HTTP/WebSocket normalizados.

## Estado observado em 17 de agosto de 2026

- o Windows enumerou `COM7` como Silicon Labs CP210x, VID/PID `10C4:EA60`;
- o Mission Planner 1.3.83 estava conectado em `COM7` a 57600 baud e mostrava Pixhawk 6C/ArduCopter 4.6.3;
- uma primeira abertura passiva da `COM7` falhou com acesso negado porque a porta estava ocupada;
- depois de liberar a serial, dois diagnósticos passivos receberam heartbeat real `sysid=1`, `compid=1`, modo `STABILIZE` e veículo desarmado;
- um ciclo integrado limitado publicou sete heartbeats no backend, sem envio de missão/comando;
- o Mission Planner mantinha UDP 14551 como **Inbound**, não como espelhamento da serial;
- um TLOG anterior contém MAVLink real de system `1`, component `1`, mas não equivale a heartbeat ao vivo no gateway;
- no estado final, a COM7 não está enumerada, o Mission Planner está fechado, não há listeners 14550/14551 e o diagnóstico retorna `VEHICLE_PORT_NOT_FOUND`/exit 2;
- nenhum upload, armamento, motor ou voo foi executado.

## Baseline obrigatório

Mantenha no `.env`:

```env
MAVLINK_BAUD=57600
MAVLINK_SOURCE_SYSTEM_ID=254
MAVLINK_SOURCE_COMPONENT_ID=190
REAL_HARDWARE_ACKNOWLEDGED=false
ALLOW_MISSION_UPLOAD=false
ALLOW_FLIGHT_COMMANDS=false
ALLOW_MISSION_START=false
```

Com `REAL_HARDWARE_ACKNOWLEDGED=false`, o modo físico fica somente em recepção. O diagnóstico também é sempre passivo por padrão. Nenhuma dessas etapas substitui bancada sem hélices e checklist.

## Modo A — serial direta

Use somente quando o Mission Planner e qualquer outro consumidor estiverem completamente desconectados da COM7:

```env
MAVLINK_MODE=direct
MAVLINK_CONNECTION=COM7
MAVLINK_BAUD=57600
```

```text
Pixhawk 6C → COM7 → Pymavlink/drone_gateway → FastAPI → WebSocket → admin/cliente
```

Antes de iniciar, liste as portas e confirme que a COM7 continua presente:

```powershell
cd drone_gateway
.\.venv\Scripts\python.exe -m app.tools.list_ports
.\.venv\Scripts\python.exe -m app.tools.mavlink_diagnose --connect --observe-seconds 5
```

O diagnóstico deve diferenciar porta ausente, porta ocupada/acesso negado, serial aberta sem MAVLink e timeout de heartbeat. Campo não recebido aparece como indisponível; nunca é preenchido com exemplo.

## Modo B — Mission Planner aberto

Use quando o Mission Planner deve continuar como único dono da COM7:

```env
MAVLINK_MODE=mission_planner_forward
MAVLINK_CONNECTION=COM7
MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551
MAVLINK_BAUD=57600
```

```text
Pixhawk 6C → COM7 → Mission Planner → UDP Client 127.0.0.1:14551
                                              ↓
                                      Pymavlink/drone_gateway
```

### Evitar o listener Inbound na UDP 14551

1. Quando reabrir o Mission Planner, localize o AutoConnect **Mavlink alt port** configurado como UDP 14551, direção **Inbound**, e desabilite-o. Esse listener recebe datagramas para o Mission Planner; ele não encaminha dados da COM7. No estado final da auditoria não havia listener, pois o Mission Planner estava fechado.
2. Se a versão não expuser esse item na interface, feche o Mission Planner, faça backup de `Documents\Mission Planner\config.xml`, mude somente `Enabled` para `false` nessa entrada e reabra o programa.
3. Confirme que nenhum processo está ouvindo na porta antes de iniciar o gateway:

```powershell
Get-NetUDPEndpoint -LocalPort 14551 -ErrorAction SilentlyContinue
```

4. No Mission Planner, selecione `COM7`, `57600` e clique em **CONNECT**.
5. Abra `SETUP` → `Advanced` → `Mavlink Mirror` (em algumas versões, `Ctrl+F` → `MAVLink`).
6. Selecione **UDP Client**, destino `127.0.0.1`, porta `14551`.
7. Deixe **Write access** desmarcado no primeiro ensaio. Isso permite validar apenas recepção.
8. Execute `scripts\start_gateway.ps1 -DiagnoseOnly` e confirme heartbeat, IDs, modo, armamento e telemetria.

A ferramenta oficial de forwarding do Mission Planner está descrita em [Advanced Tools](https://ardupilot.org/planner/docs/common-mp-tools.html).

## Subir a integração

Para hardware no Windows, execute o gateway no host. O container Linux do profile `gateway` é destinado a simulação/SITL e não deve tentar abrir a COM7.

```powershell
docker compose up -d db backend admin
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1
```

Abra:

- admin: `http://localhost:5173`;
- cliente Flutter Web: `http://localhost:5174`;
- OpenAPI: `http://localhost:8000/docs`.

O painel deve mostrar a fonte `HARDWARE_REAL`, topologia, COM/endpoint, baud, system/component, idade do heartbeat, modo, armado, GPS, bateria, EKF, posição e motivo da falha. Ausência ou stale precisa bloquear prontidão.

No snapshot final desta rodada, o esperado é `ERROR`, modo `direct`, `COM7`/57600,
`connected=false`, `heartbeat=false` e os três gates falsos, porque a porta está ausente. Não use
o heartbeat anterior para tornar esse snapshot saudável.

## Liberar apenas upload em uma sessão posterior

Somente depois de heartbeat e telemetria ao vivo, SITL, revisão da rota e checklist de bancada:

1. remova as hélices e confirme o veículo desarmado;
2. registre a versão/hash autorizados;
3. no modo encaminhado, habilite **Write access** no Mavlink Mirror;
4. defina `REAL_HARDWARE_ACKNOWLEDGED=true` e `ALLOW_MISSION_UPLOAD=true`;
5. mantenha `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false`;
6. faça upload, aguarde `MISSION_ACK`, releia a missão e compare o conteúdo;
7. reverta `ALLOW_MISSION_UPLOAD=false` ao terminar.

`UPLOADED` registra o ACK; `VERIFIED` somente pode ser publicado após a releitura e comparação. Upload nunca significa início de voo.

Não habilite início junto com upload. Em uma etapa posterior e distinta, `START` ainda exige
`ALLOW_FLIGHT_COMMANDS=true`, `ALLOW_MISSION_START=true`, missão `VERIFIED`, heartbeat/preflight
atuais e armamento físico pelo operador. O gateway não envia armamento. `PAUSE` e `CONTINUE`
exigem o gate geral de comandos e ACK do autopiloto.

## MAVLink Inspector

No Mission Planner, abra o MAVLink Inspector e compare `HEARTBEAT`, `GPS_RAW_INT`, `GLOBAL_POSITION_INT`, `SYS_STATUS`, `BATTERY_STATUS`, `EKF_STATUS_REPORT`, `HOME_POSITION`, `MISSION_CURRENT` e `STATUSTEXT` com os timestamps do admin. Uma mensagem vista apenas no Mission Planner não prova que chegou ao gateway.

## MAVProxy como alternativa

MAVProxy é opcional e não está instalado neste computador. Ele pode ser o único dono da COM e criar saídas separadas, conforme [Telemetry Forwarding](https://ardupilot.org/mavproxy/docs/getting_started/forwarding.html). Não o adicione entre as camadas se serial direta ou Mavlink Mirror resolverem.

## Diagnóstico rápido

| Resultado | Interpretação | Ação segura |
|---|---|---|
| COM7 ausente | porta/cabo/driver não enumerado | reconectar e confirmar no Gerenciador de Dispositivos |
| acesso negado/ocupada | outro processo abriu a serial | fechar o concorrente ou usar o modo encaminhado |
| UDP 14551 ocupada | listener Inbound ainda ativo | desabilitar o listener; não disputar a porta |
| conexão aberta, sem heartbeat | endpoint/baud/forwarding/energia incorretos | conferir cada camada; não habilitar upload |
| campo indisponível ou stale | mensagem não chegou dentro do prazo | comparar Inspector/logs; bloquear prontidão |
| ACK rejeitado/timeout | comando ou protocolo não confirmado | interromper, preservar logs e investigar |
| releitura divergente | missão armazenada não corresponde à aprovada | não iniciar; revisar/exportar novamente |

O protocolo oficial de conexão Python está em [Pymavlink](https://mavlink.io/en/mavgen_python/) e o upload/releitura em [Mission Protocol](https://mavlink.io/en/services/mission.html).
