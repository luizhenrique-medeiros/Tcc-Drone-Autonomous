# Hardware real

## Estado e princípio

Este documento prepara a integração, mas não confirma montagem. O único controlador explicitamente informado é a **Pixhawk 6C** com **ArduPilot**. Modelo de frame, GPS, rádio, receptor, ESC, motor, hélice, bateria, power module e mecanismo de entrega ainda precisam de part numbers e diagrama aprovados. Não se inventam pinagens nem parâmetros.

Em 20 de agosto de 2026, o Windows enumerou `COM7` como interface **Silicon Labs CP210x**. O
Mission Planner 1.3.83 identificou ArduCopter 4.6.3/Pixhawk 6C em 57600 baud. Esses dados
identificam o link visto no computador, mas não substituem conferência física da placa, do cabo e
do rádio.

## Inventário a confirmar

| Componente | Função | Informação necessária antes de ligar |
|---|---|---|
| Pixhawk 6C | autopiloto | revisão, firmware suportado, alimentação correta |
| GPS + bússola | posição/heading | modelo, orientação e cabo/porta confirmados |
| telemetria | link Mission Planner/gateway | modelo, frequência legal, níveis e porta |
| receptor/rádio RC | controle e intervenção | protocolo, bind, failsafe e operador |
| power module/bateria | alimentação/medição | química, células, tensão/corrente, conectores |
| ESCs/motores/hélices | propulsão | compatibilidade elétrica/mecânica e sentido |
| frame/trem de pouso | estrutura | carga útil, CG, fixação e vibração |
| mecanismo de carga | entrega | massa, alimentação, retenção, fail-safe |

## Conexão em bancada

1. Produzir diagrama físico com manuais oficiais dos part numbers.
2. Inspecionar polaridade, tensão, isolamento, fixação e continuidade.
3. Alimentar Pixhawk por fonte/power module apropriado; USB não alimenta propulsão.
4. Conectar Mission Planner, identificar placa/firmware e salvar backup de parâmetros.
5. Calibrar sensores conforme procedimento oficial no local adequado.
6. Confirmar RC/failsafes, geofence e RTL com hélices removidas.
7. Testar gateway apenas para leitura/heartbeat; depois upload sem armar.
8. Testar motores individualmente sem hélices e com contenção/área segura.

Antes do item 7, mantenha explicitamente `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false`, `ALLOW_MISSION_START=false` e `ALLOW_VEHICLE_ARM=false`. O primeiro ensaio do gateway recebe bytes/heartbeat/telemetria e fecha a conexão; não envia heartbeat de GCS, `COMMAND_LONG`, missão, mudança de modo ou armamento.

## Pixhawk, ArduPilot e Mission Planner

Firmware/frame e parâmetros só são definidos após a montagem. O software não desativa `ARMING_CHECK`, geofence ou failsafes, nem força EKF/GPS. Mission Planner permanece ferramenta de calibração, mensagens, logs e operação. Dois programas não devem disputar a mesma COM.

As duas topologias reais aceitas são:

```text
direct:
Pixhawk/rádio → COM7 @ 57600 → gateway
Mission Planner desconectado/fechado

mission_planner_forward:
Pixhawk/rádio → COM7 @ 57600 → Mission Planner
                                    └─ UDP Client 127.0.0.1:14551
                                       → gateway em udpin:127.0.0.1:14551
```

Use `MAVLINK_MODE=direct`, `MAVLINK_CONNECTION=COM7` e `MAVLINK_BAUD=57600` somente depois de confirmar que a porta está livre. Para preservar a estação de solo visível ao operador, prefira `MAVLINK_MODE=mission_planner_forward` e `MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551`.

O listener AutoConnect **Mavlink alt port**, UDP 14551 **Inbound**, que estava ativo no Mission Planner, não é forwarding da `COM7`: ele ocupa a porta esperando entrada. Desative-o antes; depois conecte o Mission Planner à `COM7`, abra `SETUP` → `Advanced` → `Mavlink Mirror`, selecione **UDP Client** para `127.0.0.1:14551`, deixe **Write access** desligado e só então inicie o gateway. O procedimento detalhado e as fontes oficiais estão em [Mission Planner e formato de missão](MISSION_PLANNER_INTEGRATION.md).

Antes da bancada, registrar sem estimativa: revisão exata da Pixhawk, firmware/versão do ArduPilot, frame, Windows utilizado, conexão USB ou rádio, modelo/frequência do rádio, porta COM, baud, endpoint UDP/TCP encaminhado, parâmetros `SERIALx_*` relevantes, system/component ID observados, mensagem de heartbeat e logs de conexão. Abra `SETUP` → `Advanced` → `MAVLink Inspector` para comparar IDs e taxas com o diagnóstico do gateway.

### Diagnóstico passivo observado

- diagnóstico e gateway host abriram `COM7`/57600 diretamente, somente para recepção, entre
  11:14:04Z e 11:19:05Z;
- o alvo respondeu como `sysid=1`, `compid=1`, modo `STABILIZE` e `armed=false` durante todo o
  período;
- foram publicados 129 snapshots `HARDWARE_REAL`; REST e WebSocket do admin mostraram a origem
  real e, após a parada, o snapshot ficou corretamente stale;
- bateria ficou em 74–75%; GPS chegou a fix 3/5 satélites, mas terminou fix 1/0;
- EKF/preflight permaneceram falsos e home/origin ausentes: o resultado é `NO-GO`;
- o modo passivo não enviou heartbeat GCS, pedido de intervalo, missão, comando, mudança de modo
  ou armamento; todos os gates ficaram falsos;
- forwarding 14551 expirou sem heartbeat porque a porta estava configurada como Inbound;
- upload, ACK/releitura, ensaio de motor, armamento e voo permanecem não comprovados.

Em 17 de agosto, ensaios anteriores já haviam comprovado heartbeat direto e depois porta ausente;
essa fotografia histórica não substitui a sessão mais completa de 20/08 nem a saúde atual.

Acesso negado significa porta ocupada, não falha do autopiloto. Porta aberta sem bytes, bytes sem quadros MAVLink válidos e quadros sem heartbeat do alvo são falhas diferentes e devem ser registradas separadamente. Nenhuma delas autoriza escrita ou voo.

## Energia e propulsão

Calcular corrente máxima, capacidade, C-rating, autonomia com reserva, peso, empuxo e CG a partir dos componentes reais. `MIN_BATTERY_PERCENT` do software não substitui limites de célula/tensão definidos pela equipe. Bateria danificada, inchada, quente ou fora de balanceamento interrompe o ensaio.

## Telemetria e RF

Confirmar frequência/potência permitidas no local, antenas afastadas de interferência, baud/porta e coexistência com RC/GPS. Perda de link deve acionar comportamento previamente testado no SITL e bancada; gateway não assume que internet e rádio falharão juntos.

## Mecanismo de entrega

Definir retenção mecânica, massa/CG, comando, confirmação e estado seguro sem carga. Falha não pode liberar carga sobre pessoas/animais. Acionamento real só entra depois do voo básico validado e análise de risco.

## Limitações atuais

- nenhuma pinagem validada;
- nenhum frame/propulsão/bateria identificado;
- `COM7`, 57600 baud e o descritor CP210x foram observados no Windows, mas o tipo físico do link USB/rádio ainda precisa ser confirmado;
- o gateway recebeu telemetria real em serial direta, mas o processo foi encerrado e o snapshot
  atual é stale; o êxito não torna o veículo preflight-ready;
- o TLOG existente comprova apenas uma sessão anterior, não saúde atual do veículo;
- frame, rádio, endpoint encaminhado em funcionamento e parâmetros `SERIALx_*` ainda não foram confirmados operacionalmente;
- forwarding do Mission Planner, GPS final adequado, EKF/preflight, home/origin, upload e releitura
  não foram comprovados;
- nenhuma calibração, motor, voo manual, missão autônoma ou entrega real comprovados.

Use [Checklist](PREFLIGHT_CHECKLIST.md), [Segurança](SECURITY.md) e [Plano de demonstração](DEMO_PLAN.md) para registrar evidências.
