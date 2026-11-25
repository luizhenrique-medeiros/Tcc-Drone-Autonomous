# Conexão e acompanhamento passivo PX4

O QGroundControl opera a aeronave e pode encaminhar os dados recebidos em uma
direção por UDP. O gateway ouve nesse destino e publica observações na API.
Na conexão direta do QGroundControl, somente ele abre a porta física. Se a
instalação usa um roteador, somente o roteador abre a porta física. Nenhuma
segunda COM é exigida para o acompanhamento.

Mantenha `ALLOW_MISSION_UPLOAD`, `ALLOW_FLIGHT_COMMANDS`,
`ALLOW_MISSION_START`, `ALLOW_VEHICLE_ARM` e `ALLOW_TELEMETRY_REQUESTS`
em `false`. Use `scripts/start_gateway.ps1 -ObserveOnly` para o serviço
contínuo. `-DiagnoseOnly` recebe por um intervalo limitado e termina.

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
3. Execute `scripts/start_gateway.ps1 -ObserveOnly`. Para a instalação local
   com encaminhamento QGroundControl, use `udpin:127.0.0.1:14445` quando esse
   for o destino configurado no QGroundControl.
4. Em **Telemetria**, confira a origem, os IDs do veículo e o horário da
   atualização. Leituras ausentes continuam indisponíveis. O gateway não
   solicita posição, taxas de mensagens, parâmetros nem lista de missões.

O snapshot de saúde usa o mesmo intervalo no gateway e no backend para
altitude relativa, de -1000 a 100000 m. Ele mantém a altitude relativa e a
altitude AMSL em campos distintos, conforme as referências reportadas pelo PX4.

Na amostragem de bancada de 24/11/2026, 22 snapshots do encaminhamento UDP
14445 trouxeram `HEARTBEAT`, `GLOBAL_POSITION_INT`, `EXTENDED_SYS_STATE`
e `MISSION_CURRENT`. O PX4 informou veículo desarmado, em solo, sem missão
e fora do modo de missão. Nessa amostra ficaram sem evidência o identificador
nativo do plano, a sequência e a quantidade de itens válidas, além de
`MISSION_ITEM_REACHED`. As transições de voo foram testadas por reprodução
de mensagens. Nenhum voo foi realizado para obter a amostra de bancada.

Fonte: [configuração MAVLink do QGroundControl](https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/mavlink.html).

## Modo bancada no painel

Em **Configurações → Ativar modo bancada**, a opção vale para a sessão do
navegador e inicia desativada. Quando a leitura atual confirma hardware
desarmado, heartbeat e conexão passiva, posição, GPS, Home e RTL aparecem como
informativos. Avisos conhecidos de fix e PDOP do GPS desse veículo ficam na
trilha de eventos. As proteções do PX4 e os controles do gateway continuam
em vigor.

## Operação no QGroundControl

No painel, baixe o `.plan` da revisão e abra o arquivo em **Plan → Open**.
Revise o plano antes de qualquer ação operacional. O QGroundControl é a única
interface do fluxo vigente para upload, armamento, início, retorno e
desarmamento. Veja o [fluxo administrativo](ADMIN_FLOW.md).

O perfil experimental `px4_bench_arm` foi retirado da inicialização e da API
operacionais. O código e os testes com transporte substituído foram
preservados como histórico do ensaio. Uma segunda conexão serial usada naquele
experimento deixou de fazer parte da operação.

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

## Integridade da missão observada

Registre a revisão salva no QGroundControl quando precisar de trilha de
auditoria. O download e o registro do arquivo são independentes do estado
da Pixhawk. Se faltarem evidências de que a observação se refere àquela
revisão, o painel mantém somente a observação geral do veículo.

A releitura ativa pela ferramenta experimental `px4_bench_readback` pertence
ao histórico da migração. A inicialização operacional não atende solicitações
dessa ferramenta. A conferência da missão armazenada na Pixhawk é realizada
pelo operador no QGroundControl.
