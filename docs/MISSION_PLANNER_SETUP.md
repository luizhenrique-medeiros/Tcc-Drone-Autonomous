# Mission Planner, Pixhawk e MAVLink

Este guia prepara conexão; ele não registra nenhum heartbeat, upload, bancada ou voo como executado. Nunca tente abrir a mesma porta COM simultaneamente em dois programas.

## Topologia recomendada no Windows

Para a primeira bancada em um único computador, use **Mission Planner como dono da COM e encaminhe MAVLink por UDP ao gateway**:

```text
Pixhawk/radio → COM (Mission Planner) → UDP 127.0.0.1:14550
                                      → drone_gateway → backend → admin
```

Motivos: Mission Planner já identifica firmware/COM/baud, mantém a GCS visível ao operador e evita disputa da serial. O gateway permanece responsável pelos comandos que o sistema autoriza e filtra o `sysid/compid` alvo. A documentação oficial do Mission Planner informa que o encaminhamento local pode distribuir o stream e que UDP é preferível a TCP para esse uso.

Se for necessário mais de um consumidor/saída ou isolamento maior, use a topologia com roteador:

```text
Pixhawk/radio → COM (MAVProxy/MAVLink Router)
                 ├─ UDP 14550 → drone_gateway
                 └─ UDP 14551 → Mission Planner
```

A conexão direta do gateway à COM só deve ser usada quando Mission Planner estiver fechado ou receber uma saída de outro roteador; o gateway atual não atua como roteador MAVLink.

Referências oficiais: [ferramenta de forwarding do Mission Planner](https://ardupilot.org/planner/docs/common-mp-tools.html), [opções do MAVProxy](https://ardupilot.org/mavproxy/docs/getting_started/starting.html) e [solicitação de mensagens ArduPilot](https://ardupilot.org/dev/docs/mavlink-requesting-data.html).

## Dados que precisam ser fornecidos/observados

Não adote valores de exemplo como se pertencessem ao equipamento:

- modelo exato da controladora;
- veículo/frame e firmware ArduPilot, com versão;
- COM mostrada pelo Windows/Mission Planner;
- baud do link USB ou rádio;
- tipo/modelo do rádio;
- conexão USB, rádio, TCP ou UDP;
- `system id` e `component id` vistos no MAVLink Inspector;
- endpoint UDP escolhido;
- modo de voo e estado de armamento;
- home, GPS, EKF, bateria e mensagens de pre-arm;
- parâmetros `SERIALn_*` relevantes já existentes, apenas para registro;
- logs TLOG/dataflash e mensagens de erro.

O gateway não altera parâmetros para contornar pre-arm, EKF, GPS, bateria, geofence ou failsafes.

## Descoberta assistida de portas

Com o ambiente do gateway instalado, liste portas sem abri-las:

```powershell
cd drone_gateway
.\.venv\Scripts\python.exe -m app.tools.list_ports
```

Compare o resultado antes/depois de conectar a controladora. A listagem é uma ajuda; VID/PID/nome não prova que a porta pertence à Pixhawk. Confirme no Gerenciador de Dispositivos e no Mission Planner.

## Configuração por topologia

### B — Mission Planner encaminhando UDP (recomendada primeiro)

1. Mission Planner abre a COM/baud corretos.
2. Pressione `Ctrl+F`, abra a ferramenta MAVLink/Forwarding.
3. Escolha UDP para `127.0.0.1`, porta `14550`.
4. Só permita controle remoto quando a sessão de teste exigir e o checklist estiver aprovado.
5. Configure o gateway:

```powershell
$env:MAVLINK_MODE='real'
$env:MAVLINK_CONNECTION='udpin:0.0.0.0:14550'
$env:MAVLINK_TARGET_SYSTEM_ID='ID_OBSERVADO'
$env:MAVLINK_TARGET_COMPONENT_ID='COMPONENTE_OBSERVADO'
$env:REAL_HARDWARE_ACKNOWLEDGED='true'
$env:ALLOW_MISSION_START='false'
.\scripts\start_gateway.ps1
```

Comece com `ALLOW_MISSION_START=false`: conexão, health e upload podem ser avaliados sem autorizar início automático. O processo nunca arma o veículo.

### C — MAVProxy como roteador

Exemplo estrutural (substitua COM/baud observados):

```powershell
mavproxy.py --master=COM_REAL,BAUD_REAL `
  --out=udp:127.0.0.1:14550 `
  --out=udp:127.0.0.1:14551
```

Configure gateway em `udpin:0.0.0.0:14550` e Mission Planner para receber UDP 14551. Não execute esse exemplo com placeholders.

### A — Gateway direto à serial

Feche Mission Planner antes de abrir a porta:

```powershell
$env:MAVLINK_MODE='real'
$env:MAVLINK_CONNECTION='COM_REAL'
$env:MAVLINK_BAUD='BAUD_REAL'
$env:MAVLINK_TARGET_SYSTEM_ID='ID_OBSERVADO'
$env:MAVLINK_TARGET_COMPONENT_ID='COMPONENTE_OBSERVADO'
$env:REAL_HARDWARE_ACKNOWLEDGED='true'
$env:ALLOW_MISSION_START='false'
.\scripts\start_gateway.ps1
```

Para monitorar ao mesmo tempo, migre à topologia B/C; não tente a mesma COM em paralelo.

## Guia rápido de ligação

Cada passo deve ser marcado manualmente com data/operador/resultado:

1. remover hélices e isolar a bancada;
2. conectar a Pixhawk por USB ou rádio conforme o procedimento do hardware;
3. abrir Mission Planner;
4. identificar COM e baud reais;
5. verificar modelo, firmware e versão;
6. conectar e confirmar heartbeat;
7. abrir MAVLink Inspector e anotar `sysid/compid` e taxas;
8. verificar GPS e satélites;
9. verificar EKF e mensagens de pre-arm;
10. verificar bateria/fonte e tensão;
11. verificar home e posição;
12. configurar forwarding/roteador, sem compartilhar COM;
13. preencher `.env`/variáveis do gateway, ainda com início bloqueado;
14. iniciar banco/backend/admin;
15. iniciar gateway e validar badge `HARDWARE REAL`, versão e timestamps;
16. gerar e baixar a missão `.waypoints`;
17. abrir no Mission Planner, revisar rota/altitudes/comandos e registrar hash/versão;
18. autorizar somente após checklist humano e autorização de voo ainda válida;
19. executar upload e download/verificação da missão com hélices removidas;
20. somente em procedimento separado e aprovado, realizar teste controlado e depois voo em área autorizada.

## Missão e evidência

O backend gera QGC WPL 110, versão e SHA-256. O admin registra exportação, abertura/revisão e autorização; o gateway faz upload MAVLink, baixa a missão e compara contagem/conteúdo. Não há automação de cliques do Mission Planner.

Preserve para cada ensaio:

- commit do código;
- `.waypoints`, versão e hash;
- versão do firmware/autopiloto;
- topologia, endpoint, COM/baud e IDs;
- autorização/checklist;
- logs backend/gateway;
- TLOG/dataflash;
- horário e resultado de upload/ACK/releitura/RTL;
- distinção entre fake, SITL, bancada e voo.

## Erros comuns

| Sintoma | Causa provável | Ação segura |
|---|---|---|
| acesso negado/porta ocupada | outro processo abriu a COM | feche o concorrente ou use forwarding/roteador |
| sem heartbeat | COM/baud/endpoint incorreto, link sem energia ou forwarding ausente | verificar cada camada; não iniciar missão |
| campos `--` | mensagem ainda não recebida/stream ausente | conferir MAVLink Inspector e logs; não preencher manualmente |
| telemetria stale | link/forwarding parou | bloquear autorização e restabelecer conexão |
| `sysid/compid` ignorado | stream pertence a outro sistema | configurar IDs observados; nunca desativar o filtro para “funcionar” |
| upload diverge | missão relida não corresponde ao hash/conteúdo | abortar o fluxo, exportar/revisar novamente |
| pre-arm/EKF/GPS falha | condição física/configuração do veículo | corrigir no procedimento oficial; o software não contorna |

## Estado atual

Preparação em código e documentação não equivale a teste. Nesta revisão não houve Mission Planner aberto, heartbeat físico, Pixhawk, bancada ou voo observado.
