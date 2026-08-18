# Mission Planner e formato de missão

## Geração

Para pedido aprovado, o backend cria uma versão imutável com origem, decolagem, destino, espera/entrega, retorno e pouso. Coordenadas vêm do ponto final validado; altitude vem de configuração, nunca do cliente.

## Exportação QGC WPL 110

O arquivo texto começa com `QGC WPL 110`. Cada linha representa índice, current, frame, command, params 1–4, latitude, longitude, altitude e autocontinue, separados por tab. O exportador registra SHA-256, versão, data e administrador.

O formato ser aceito pelo Mission Planner não torna a rota segura. O operador deve:

1. baixar a versão exibida no painel;
2. abrir/importar em Flight Plan;
3. conferir home, frames, comandos, altitude, geofence, terreno, destino, retorno e pouso;
4. salvar evidência e marcar a mesma versão como revisada;
5. não autorizar se houver divergência.

## Topologias MAVLink reais

Há duas topologias explícitas. Ambas representam hardware real e exigem bancada isolada, hélices removidas e operador presente; nenhuma delas autoriza upload, modo de voo, armamento ou decolagem por si só.

| Modo | Caminho | Dono da serial | Configuração do gateway |
|---|---|---|---|
| `direct` | Pixhawk/rádio → `COM7` → gateway | somente o gateway; Mission Planner desconectado e sem processo segurando a porta | `MAVLINK_MODE=direct`, `MAVLINK_CONNECTION=COM7`, `MAVLINK_BAUD=57600` |
| `mission_planner_forward` | Pixhawk/rádio → `COM7` → Mission Planner → UDP Client → gateway | Mission Planner | `MAVLINK_MODE=mission_planner_forward`, `MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551`, `MAVLINK_BAUD=57600` |

O baud é aplicado à serial; em UDP ele não altera o transporte, mas permanece registrado para a troca controlada de topologia. Para o primeiro diagnóstico, use em ambos os modos:

```dotenv
REAL_HARDWARE_ACKNOWLEDGED=false
ALLOW_MISSION_UPLOAD=false
ALLOW_FLIGHT_COMMANDS=false
ALLOW_MISSION_START=false
```

### Sequência observada em 17 de agosto de 2026

O Windows enumerou `COM7` como **Silicon Labs CP210x USB to UART Bridge/CP2102**, VID/PID `10C4:EA60`, e o Mission Planner 1.3.83 estava usando `COM7` a 57600 baud. Uma primeira tentativa estritamente passiva falhou com acesso negado. Depois de fechar/liberar o Mission Planner, dois diagnósticos passivos diretos receberam heartbeat real do autopiloto: system/component `1/1`, modo `STABILIZE`, veículo desarmado. Um ciclo integrado de 15 segundos publicou sete heartbeats no backend. Nenhum desses passos enviou bytes de escrita MAVLink.

Também foi observado no Mission Planner o item de AutoConnect **Mavlink alt port**, UDP 14551, direção **Inbound**. Esse listener espera datagramas destinados ao Mission Planner: ele **não** encaminha o stream da `COM7` para o gateway. Depois, o Mission Planner foi fechado e os listeners 14550/14551 desapareceram, mas o Mavlink Mirror não chegou a ser configurado/validado.

No estado final, o cabo/link não está enumerado como porta serial. O dispositivo PnP aparece apenas como histórico/`Unknown`, o diagnóstico passivo retorna `VEHICLE_PORT_NOT_FOUND` com exit 2 e o snapshot do backend registra `HARDWARE_REAL`, `ERROR`, `direct`, COM7/57600 e as três flags falsas. O heartbeat anterior continua válido como evidência daquele ensaio, não como saúde atual.

### Corrigir o forwarding no Mission Planner

1. Mantenha o veículo desarmado, remova as hélices e pare o gateway.
2. No Mission Planner, desative o listener de AutoConnect **Mavlink alt port** em UDP 14551, direção **Inbound**. Na versão em que a entrada não é exposta na interface, feche o Mission Planner, faça backup de `Documents\Mission Planner\config.xml`, altere somente `Enabled` para `false` nessa entrada e reabra o programa.
3. Confirme no Windows que o Mission Planner deixou de ouvir em UDP 14551 antes de iniciar o gateway.
4. Selecione `COM7`, 57600 e conecte o Mission Planner ao veículo.
5. Abra `SETUP` → `Advanced` → `Mavlink Mirror`. A rota alternativa documentada é `Ctrl+F` → `MAVLink`/Forwarding.
6. Selecione **UDP Client**, informe destino `127.0.0.1` e porta `14551`. O campo de baud da janela não controla UDP.
7. Deixe **Write access** desmarcado e clique em **Connect**. Assim, o primeiro marco é somente Mission Planner → gateway.
8. Inicie o gateway com `MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551` e as quatro flags seguras acima.
9. Só depois de heartbeat/telemetria ao vivo, IDs, frescor, revisão da missão, checklist e autorização válidos, uma sessão separada pode registrar `REAL_HARDWARE_ACKNOWLEDGED=true`, habilitar **Write access** e definir `ALLOW_MISSION_UPLOAD=true` para upload desarmado. Mantenha `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false`. Não arme nem voe nesse ensaio.

O Mission Planner encaminha para apenas um destino nessa ferramenta. Mais consumidores exigem roteador MAVLink explícito, como MAVProxy, com portas distintas.

## Inspeção e diagnóstico somente leitura

Abra `SETUP` → `Advanced` → `MAVLink Inspector` ou `Ctrl+F` → `MAVLink Inspector` e registre `sysid`, `compid`, tipo e taxa das mensagens. No gateway, o diagnóstico inicial deve apenas abrir o transporte, receber e fechar em bloco `finally`; não deve chamar nenhum método `*_send`, enviar heartbeat de GCS, `COMMAND_LONG`, `COMMAND_INT`, missão, mudança de modo ou armamento.

Classifique o resultado sem transformar ausência em sucesso:

| Resultado | Interpretação |
|---|---|
| porta não enumerada | dispositivo/driver/cabo ausente; `NO-GO` |
| acesso negado | serial ocupada, como ocorreu com Mission Planner na `COM7`; usar forwarding ou liberar a porta |
| porta abre, zero bytes | link/baud/alimentação incorretos ou veículo sem stream |
| bytes, mas nenhuma mensagem MAVLink válida | protocolo/baud/link incompatível |
| mensagens válidas, mas heartbeat alvo expira | IDs/roteamento/veículo incorretos; não declarar conectado |
| heartbeat e telemetria alvo recentes | evidência ao vivo somente daquele ensaio; ainda não prova upload, armamento ou voo |

O heartbeat é difundido periodicamente pelos componentes MAVLink, normalmente perto de 1 Hz. O gateway considera apenas o heartbeat recebido do `system/component` alvo e marca desconectado/stale quando ele expira; abrir a porta ou receber qualquer byte não basta. Enquanto **Write access** e as flags de escrita estiverem desligados, o gateway apenas observa as taxas já existentes. Se uma etapa futura permitir escrita, escolha um único responsável pelas taxas: `MAV_CMD_SET_MESSAGE_INTERVAL` exige comando e `COMMAND_ACK`, e não deve competir com `REQUEST_DATA_STREAM` do Mission Planner.

## Upload MAVLink

Upload permanece bloqueado quando `ALLOW_MISSION_UPLOAD=false`. Após autorização válida, flag habilitada deliberadamente e, no modo encaminhado, **Write access** habilitado, o gateway aguarda heartbeat do system/component configurado, solicita versão/streams, refaz preflight e usa o protocolo de missão MAVLink com timeout.

O upload envia `MISSION_COUNT`; responde a cada `MISSION_REQUEST_INT` com o `MISSION_ITEM_INT` da sequência solicitada; e só registra sucesso após `MISSION_ACK.type=MAV_MISSION_ACCEPTED`. ACK negativo ou fora do alvo falha a operação. Em seguida, o gateway relê com `MISSION_REQUEST_LIST` → `MISSION_COUNT` → pares `MISSION_REQUEST_INT`/`MISSION_ITEM_INT`, confere tipo, quantidade, ordem e campos permitidos, e finaliza a recepção com `MISSION_ACK`. `MISSION_REQUEST`/`MISSION_ITEM` são legados; um pedido legado recebido deve ser respondido com item `MISSION_ITEM_INT`. Não se envia `MISSION_CLEAR_ALL` indiscriminadamente.

Toda mensagem que exige resposta possui timeout e retry limitado. A especificação recomenda 1500 ms como timeout geral, 250 ms para itens e no máximo cinco tentativas; a configuração local pode ser mais conservadora, mas, ao esgotar tentativas, deve cancelar e voltar a idle sem publicar upload confirmado. Para comandos permitidos em etapas futuras, associe o `COMMAND_ACK` ao comando e ao alvo: `MAV_RESULT_ACCEPTED` confirma aceite, não necessariamente conclusão; `MAV_RESULT_IN_PROGRESS` exige aguardar o ACK final.

Upload não equivale a início. O ACK gera `UPLOADED`; somente a releitura equivalente gera `VERIFIED`. O início exige comando administrativo `START`, autorização consumida, heartbeat/preflight atuais, `ALLOW_FLIGHT_COMMANDS=true`, `ALLOW_MISSION_START=true` e veículo já armado pelo operador. O gateway nunca arma no startup, health check, upload ou START. `PAUSE` e `CONTINUE` também exigem o gate geral, estado compatível e ACK. Mission Planner permanece aberto para monitoramento, mensagens e logs.

## SITL

SITL valida parsing, upload, ACK, telemetria, chegada, retorno, perda de link e abortamento antes do hardware. Scripts usam WSL 2 quando necessário. Resultados ficam separados dos testes unitários.

## Pixhawk real

`MAVLINK_MODE=direct` ou `MAVLINK_MODE=mission_planner_forward`, conexão explícita e confirmação externa são necessários. A topologia recomendada e os comandos auxiliares também estão em [MISSION_PLANNER_SETUP.md](MISSION_PLANNER_SETUP.md). Validar primeiro comunicação e sensores; os marcos posteriores — motores sem hélices, voo manual, missão curta sem carga e carga leve/mecanismo — exigem procedimentos e evidências separados. Parâmetros e pinagem não são definidos por este software sem confirmação da montagem.

### Estado da evidência

| Evidência | Estado em 17 de agosto de 2026 |
|---|---|
| enumeração Windows de `COM7`, descritor e VID/PID | observada ao vivo |
| Mission Planner ocupando `COM7` e listeners UDP 14550/14551 | observado ao vivo |
| primeira abertura passiva de `COM7` | falhou por acesso negado enquanto Mission Planner era o dono |
| dois diagnósticos passivos diretos posteriores | heartbeat real `1/1`, `STABILIZE`, `armed=false` |
| ciclo real limitado → backend | sete heartbeats normalizados com HTTP 200, sem comandos/escrita |
| estado final da porta | COM7 ausente; diagnóstico exit 2 `VEHICLE_PORT_NOT_FOUND`; snapshot `ERROR` |
| mensagens ArduPilot em TLOG anterior | evidência histórica até 07:55; não prova conexão atual |
| heartbeat/telemetria pelo forwarding 14551 | ainda não comprovados; Mission Planner fechado e sem listeners no estado final |
| upload/ACK/releitura no hardware | ainda não comprovados |
| armamento, motor, voo ou entrega real | não executados/comprovados nesta revisão |

## Limites

Não automatizamos a GUI do Mission Planner, não ignoramos pre-arm, não mudamos parâmetros para “fazer funcionar” e não afirmamos upload/voo real sem log/evidência. Telemetria normalizada complementa, não substitui, a estação de solo.

## Fontes oficiais

- [Mission Planner Advanced Tools: MAVLink Inspector e forwarding](https://ardupilot.org/planner/docs/common-mp-tools.html)
- [ArduPilot SITL: Mavlink Mirror, UDP Client e write access](https://ardupilot.org/dev/docs/using-sitl-for-ardupilot-testing.html#using-mission-planner-forwarding)
- [Pymavlink: conexão serial Windows, heartbeat e recepção](https://mavlink.io/en/mavgen_python/)
- [MAVLink Heartbeat/Connection Protocol](https://mavlink.io/en/services/heartbeat.html)
- [MAVLink Mission Protocol: upload, download, ACK, timeout e retry](https://mavlink.io/en/services/mission.html)
- [MAVLink Command Protocol: `COMMAND_ACK` e comandos longos](https://mavlink.io/en/services/command.html)
- [ArduPilot: solicitação de mensagens e `MAV_CMD_SET_MESSAGE_INTERVAL`](https://ardupilot.org/dev/docs/mavlink-requesting-data.html)
- [ArduCopter: mensagens MAVLink suportadas](https://ardupilot.org/copter/docs/ArduCopter_MAVLink_Messages.html)
- [ArduPilot: configuração dos links de telemetria MAVLink](https://ardupilot.org/copter/docs/common-mavlink-configuration.html)
- [ArduCopter: failsafe de GCS](https://ardupilot.org/copter/docs/gcs-failsafe.html)
- [ArduPilot: roteamento MAVLink](https://ardupilot.org/dev/docs/mavlink-routing-in-ardupilot.html)
- [MAVProxy: forwarding para múltiplas saídas](https://ardupilot.org/mavproxy/docs/getting_started/forwarding.html)
