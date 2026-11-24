# Diagnóstico passivo PX4

Esta etapa não prepara nem envia missões. Descubra a versão PX4, a conexão e o
baud rate com o operador. Uma porta serial deve pertencer a apenas um processo;
o QGroundControl pode encaminhar telemetria recebida a um destino UDP. Esse
encaminhamento é unidirecional e não transmite comandos ao veículo. Para
consultas bidirecionais de bancada, use a rota serial dedicada do MAVProxy
descrita abaixo.
Não suponha que dois aplicativos possam abrir a mesma COM simultaneamente.

No ambiente do gateway, configure `AUTOPILOT_SYSTEM=PX4`, a conexão real e os
cinco controles `ALLOW_MISSION_UPLOAD`, `ALLOW_FLIGHT_COMMANDS`,
`ALLOW_MISSION_START`, `ALLOW_VEHICLE_ARM` e `ALLOW_TELEMETRY_REQUESTS` como
`false`. Confira também os valores existentes no `.env`, pois valores ativos
impedem a inicialização. Para listar portas sem abrir a conexão:

```powershell
cd drone_gateway
.\.venv\Scripts\python.exe -m app.tools.list_ports
```

Após confirmar a topologia, `scripts/start_gateway.ps1 -DiagnoseOnly` executa
diagnóstico de recepção passiva. Não se pode inferir o estado de segurança nem
uma missão válida pela ausência de mensagens. Consulte `docs/BUILD_AND_RUN.md`
para iniciar banco, backend, painel e aplicação cliente; essas instruções ainda
contêm aspectos legados que precisam ser revisados para a migração.

## Recepção passiva do QGroundControl

1. Conecte o QGroundControl ao veículo segundo a configuração existente, sem
   abrir a mesma serial no gateway. Em Configurações > MAVLink, habilite o
   encaminhamento para um endereço e porta UDP escolhidos para este computador.
2. No ambiente do gateway, configure `AUTOPILOT_SYSTEM=PX4`,
   `MAVLINK_MODE=qgroundcontrol_forward` e `MAVLINK_CONNECTION=udpin:ENDEREÇO:PORTA`,
   com endereço local de escuta e porta correspondentes ao destino configurado
   no QGroundControl. Substitua os marcadores pelos valores efetivamente usados.
   `MAVLINK_FORWARD_SOURCE` é `UNKNOWN` por padrão. Configure `HARDWARE_REAL`
   ou `SITL` somente após o operador confirmar a origem; isso é declaração
   operacional, não detecção automática do equipamento.
3. Mantenha todos os cinco controles `ALLOW_*` listados acima em `false` e
   execute `scripts/start_gateway.ps1 -DiagnoseOnly`. O modo é exclusivamente
   passivo mesmo que a confirmação de hardware esteja habilitada.
4. Confira se o diagnóstico recebeu heartbeat PX4 e identifique system/component
   ID. Leituras não transmitidas permanecem indisponíveis. A recepção do
   heartbeat não valida GPS, bateria ou segurança do voo.

Fonte: [configuração MAVLink do QGroundControl](https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/mavlink.html).

## Supervisão local da conexão PX4

Para a topologia local testada, `scripts/install_px4_supervisor.ps1` registra a
tarefa de logon `DevCore PX4 Observacao` para o usuário atual. Ela supervisiona
o MAVProxy em COM7/57600, com destinos UDP locais 14555 (QGroundControl) e
14600 (gateway). O QGroundControl usa a conexão UDP configurada; não deve abrir
a COM7 ao mesmo tempo. Caso a porta esteja ocupada ou o dispositivo ausente,
o roteador tenta novamente a cada 15 segundos.

O supervisor desta rota dedicada COM7 inicia o gateway no host em
PX4/`mavlink_router`, com a origem `HARDWARE_REAL` declarada e todos os
controles de envio desativados. Essa declaração vale para a instalação física
confirmada. Um encaminhamento genérico mantém a origem padrão `UNKNOWN`.
Banco, backend e painel dependem do Docker Desktop e das políticas de reinício
dos respectivos containers; a tarefa não inicia o Docker Desktop. O gateway
Docker simulado não deve ser executado simultaneamente com o gateway do host.

Consulte o estado em `Get-ScheduledTask -TaskName 'DevCore PX4 Observacao'` e
os logs em `%LOCALAPPDATA%\DevCoreMavlinkRouter\logs`. Os arquivos de saída
são substituídos quando o respectivo processo é reiniciado; durante uma sessão
longa ainda podem crescer e precisam de gerenciamento. Parar a tarefa encerra
a supervisão, mas não necessariamente seus processos filhos: identifique-os
antes de encerrá-los. Após alteração dos scripts, reinicie a tarefa para aplicar
o novo código. O registro da tarefa e a retomada do gateway foram verificados
na sessão atual; o reinício do Windows ainda precisa ser testado.

Em 24/11/2026, verificou-se que o MAVProxy encerrava ao iniciar em tarefa
oculta porque criava um prompt que exigia console. O lançador
`scripts/px4_router_daemon.py` fornece entrada e saída inertes ao prompt e
executa o MAVProxy em modo não interativo. Após reiniciar a tarefa, o roteador
reconectou à COM7; em seguida, após encerrar os processos do roteador, a
supervisão os reiniciou e o backend voltou a registrar heartbeat e `armed=false`.
O log do roteador também exibiu `fence breach`; isso não comprova por si só a
situação do geofence e deve ser esclarecido no QGroundControl antes de qualquer
teste físico. Nenhum ARM ou início de missão foi enviado.

## Conferência da missão na bancada

O supervisor Windows disponibiliza um diretório local de solicitações em
`%LOCALAPPDATA%\DevCoreMavlinkRouter\bench`. A ferramenta entrega uma
solicitação ao gateway de observação já conectado. Ela não abre COM7 nem
uma segunda escuta UDP. A consulta usa somente o protocolo de leitura da
missão, com timeout e identificação explícita do sistema/componente PX4.
O ACK transmitido pelo gateway encerra a leitura.

1. Com o operador presente e as hélices removidas, confira no QGroundControl
   que o veículo está desarmado e anote seus IDs MAVLink.
2. Salve em disco o `.plan` revisado que deseja comparar. Durante a leitura,
   aguarde para iniciar outra transferência de missão no QGroundControl.
3. Na raiz do repositório, execute a ferramenta, substituindo os argumentos
   pelo arquivo e pelos IDs confirmados no passo 1.

```powershell
.\drone_gateway\.venv\Scripts\python.exe -m app.tools.px4_bench_readback `
  'C:\caminho\missao-revisada.plan' --system-id 1 --component-id 1
```

`verified: true` significa que a contagem, as sequências, os comandos,
os frames, os parâmetros e as coordenadas recebidas foram conferidos com
o arquivo identificado pelo `plan_sha256`. Uma divergência sai com código
1 e preserva o plano da controladora. A leitura inclui identidade e integridade
do plano, com escopo distinto da verificação operacional de voo.

O perfil de leitura exige PX4 no host, origem física e enlace
`mavlink_router`. As permissões de transmissão operacional do backend e
do gateway continuam bloqueadas. O QGroundControl segue disponível para
diagnóstico e operação manual. Consulte o [protocolo de missões MAVLink](https://mavlink.io/en/services/mission.html).
