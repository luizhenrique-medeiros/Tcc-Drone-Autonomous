# Migração PX4 e QGroundControl: trabalho em andamento

O site prepara e disponibiliza arquivos de missão. A revisão operacional,
o upload à Pixhawk e as ações de voo são realizados pelo operador no
QGroundControl. O PX4 aplica as proteções nativas.
O checkpoint anterior é o commit `64e63c7e2bf9058011067912cef090380947d5be`.

## Acompanhamento no painel

Em **Operações**, o cartão **Veículo observado** exibe o último modo, estado
de armamento e posição informados. Também lista as mensagens MAVLink que
chegam pelo enlace de observação: respostas de comando e de missão,
waypoint atual, waypoint alcançado e mensagens de estado. Os eventos ficam
associados ao veículo, sem atribuição automática a um pedido. Um ACK
observado pode corresponder a um comando do QGroundControl.

O painel inclui controles de upload, ARM, START e RTL no ensaio PX4 SITL.
A exposição está condicionada à API em ambiente de teste e a um veículo SITL.
O gateway da Pixhawk permanece em recepção. O QGroundControl segue como a
interface de operação manual do equipamento.

### Bloqueios de transmissão verificados no código

| Camada | Comportamento atual |
| --- | --- |
| Painel | `MissionPage.tsx` oferece rascunho, registro e download da revisão. O cartão de comandos aparece para uma revisão atual na API de teste e um veículo PX4 SITL. |
| API administrativa | `authorize_flight`, `request_vehicle_arm` e `request_safety_action` aplicam `_require_non_hardware_vehicle`. O vínculo da revisão ao artefato de upload PX4 só está disponível em `APP_ENV=test` com `PX4_SITL_PLAN_VALIDATION`. |
| Fila, vínculo e estados | `gateway_mission_artifact` e `claim_mission` aplicam a mesma restrição de hardware. `pending_commands` filtra origem simulada. O heartbeat real retorna `HARDWARE_OBSERVATION_ONLY`. Telemetria e status vinculados a uma missão usam o gateway do claim. O contrato legado de ARM/START depende de estado, autorização, modo e verificações próprias da simulação. |
| Drone Gateway | `Settings.validate_mavlink_safety` mantém os modos `qgroundcontrol_forward` e `mavlink_router` como recepção. Upload e comandos PX4 estão restritos ao ensaio em container SITL com interface de rede única de loopback. `MissionExecutor.run_cycle` publica apenas observações na configuração passiva. |
| Ambiente da Pixhawk | O supervisor Windows inicia o gateway de observação com as permissões de transmissão desativadas. `MAVLINK_MODE`, `MAVLINK_CONNECTION`, `MAVLINK_FORWARD_SOURCE` e `GATEWAY_RUNTIME` definem a topologia e a origem declarada. Modos de hardware são recusados no gateway Docker. A configuração mantém confirmação explícita de hardware e credenciais próprias do gateway. |

### Evidência de integração em 24/11/2026

- No PX4 SITL com SIH e somente loopback, o roteiro de revisão verificou
  o upload do `.plan`, o ACK e a releitura dos itens. Os campos de
  preflight e RTL da autorização legada vieram de dados de teste.
- No mesmo simulador, o gateway de observação recebeu `MISSION_CURRENT`
  do PX4, e a API administrativa registrou o evento no veículo.
- A Pixhawk publicou heartbeat fresco, modo `POSCTL`, estado desarmado
  e `MISSION_CURRENT` após a atualização do gateway de observação no host.
  O ensaio físico foi somente de recepção. ARM e START pelo painel, upload
  real pelo site e associação automática do progresso ao pedido continuam
  sem validação.

## Comandos no ensaio isolado

A API do ensaio usa `APP_ENV=test`, `PX4_SITL_PLAN_VALIDATION=true`,
banco separado e uma identidade própria de gateway. O gateway deve estar
no mesmo namespace de rede do PX4 SITL, apenas com interface de loopback
e sem dispositivos físicos. O supervisor Windows continua no perfil de
observação e não é utilizado pelo ensaio.

No painel do ensaio, abra uma missão com revisão atual e o veículo PX4 SITL
selecionado. Confirme **Enviar missão**. Aguarde a releitura e o estado
**Missão verificada**. Confirme **Armar drone** separadamente. Após a resposta
do PX4 e um heartbeat com armamento confirmado, confirme **Iniciar missão**.
A ação de início solicita apenas o modo Missão e exige armamento já observado.
**Solicitar retorno** é uma ação separada durante a execução. Use **Operações**
para acompanhar telemetria, eventos e progresso vinculado ao pedido.

Cada resposta administrativa identifica o comando. A fila distingue o
recebimento pelo gateway do resultado. O armamento depende do ACK e de um
heartbeat posterior. Início e retorno dependem de ACK e confirmação do modo.
Um timeout fica registrado e não provoca reenvio automático de ARM, START ou RTL
no SITL. A chegada ao waypoint indica avanço da rota, sem comprovar entrega
física.

### Validação do fluxo administrativo em SITL

O roteiro `scripts/px4_sitl_plan_validation.py` exercitou os mesmos endpoints
do painel com PX4 SIH executando em SITL, em namespace somente loopback.
O caso positivo passou por upload explícito, readback da revisão, ACK e
heartbeat armado, mudança para modo Missão, chegada ao waypoint, retorno
solicitado, pouso e desarmamento. O pedido recebeu o progresso da missão
vinculada. O ensaio não usou campos sintéticos de aptidão para o caso positivo.

Os cenários negativos verificaram cliente sem credencial administrativa,
confirmação falsa, START com veículo desarmado, gateway desconectado e
ausência de ACK após uma perda de pacote induzida. A repetição HTTP com a
mesma chave devolveu o mesmo registro. Um teste unitário injetou ACK
negativo para verificar a apresentação da rejeição e a ausência de reenvio.

### Preparação da validação em bancada

Registre a versão do firmware, a identidade da controladora, o plano conferido
e os resultados do ensaio SITL. A etapa física requer o operador responsável
presente, hélices removidas, procedimentos de bancada e revisão no
QGroundControl. Confirme primeiro a leitura e a identidade do veículo. A
validação de comandos físicos permanece separada e pendente. A instalação
operacional preserva a configuração de recepção.

### Releitura na Pixhawk pelo gateway Windows

Foi acrescentada uma consulta local e explícita que usa o enlace existente do
MAVProxy. A verificação em 24/11/2026 recebeu da Pixhawk PX4, IDs MAVLink 1/1,
os três itens do plano da revisão `f1f36467…`. O gateway recusou a identidade
2/1 antes de solicitar a missão e apontou divergência de coordenadas no
item 0 ao comparar com `1.plan`. Uma nova leitura conferiu o plano revisado.
O ensaio cobriu ida e volta de mensagens de leitura. As solicitações de
upload, ARM, START e RTL permanecem fora do perfil físico.

Consulte [Conferência da missão na bancada](CONEXAO_DRONE_PX4.md#conferência-da-missão-na-bancada)
para executar a leitura com outro arquivo revisado.

### Vínculo do progresso físico ao pedido

O gateway mantém o identificador nativo recebido na releitura em
`MISSION_COUNT` e o relaciona às mensagens posteriores de
`MISSION_CURRENT`. O backend só registra o item observado na linha do
tempo da missão se a origem for física, os identificadores corresponderem
e o hash estiver associado a uma única revisão atual. O vínculo preserva
os estados de negócio do pedido. O operador continua usando o
QGroundControl para controlar o veículo.

Em 24/11/2026, a Pixhawk física desarmada devolveu o identificador
`2452731608` na releitura dos três itens da revisão `f1f36467…` e voltou
a informá-lo em `MISSION_CURRENT`. A API registrou o item 1 na missão e
no pedido correspondentes. O pedido permaneceu em `MISSION_READY` e
nenhum comando de voo foi transmitido durante essa validação.

O gateway existente usa pymavlink e o protocolo de missões MAVLink, que podem ser
reaproveitados, mas a lógica de revisão, origem, modos e verificações contém
hipóteses específicas do ArduPilot. `QGC WPL 110` não é um arquivo `.plan`.
O backend mantém pedidos e missões; o gateway é o único adaptador MAVLink;
o Flutter para Android/Web e o painel React são aplicações separadas.

Existe uma API experimental autenticada `POST /api/v1/admin/missions/{id}/qgroundcontrol-draft`
que gera um rascunho `.plan` com três itens: Takeoff na origem planejada,
um Waypoint nas coordenadas confirmadas do pedido com espera de 5
segundos (`MAV_CMD_NAV_WAYPOINT.param1`) e Return To Launch (RTL).
A exportação está disponível com ou sem telemetria. Com posição atual, ela
é usada como referência para a origem. Sem posição atual, o arquivo usa as
coordenadas já planejadas na missão. No cartão **Revisão da missão**, use
**Baixar plano do QGroundControl** e abra o arquivo em **Plan → Open** para
conferir a origem e a rota. A altitude AMSL vem da telemetria ou do valor
manual opcional `home_amsl_m`. Na ausência de ambos, ela é deixada em branco
para revisão no QGroundControl. O hash `X-Draft-SHA256` identifica os bytes
gerados. O rascunho não é vinculado à versão existente, não é a missão revisada,
não é aberto automaticamente no QGroundControl nem enviado ao veículo.
O rascunho usa a mesma origem tanto para Takeoff quanto para o
Home planejado. A revisão exige que esses pontos coincidam na precisão das
coordenadas MAVLink. No painel, o marcador H mostra o Home recebido do PX4 em
telemetria atual. A configuração do RTL e o pré-voo são apresentados à parte.
O rascunho inclui **Return To Launch** como último item, com o comando MAVLink
20, frame 2 e os sete parâmetros reservados em zero, como no arquivo salvo
pelo QGroundControl Daily. O item RTL não leva coordenadas de retorno e o
comportamento em voo depende da configuração do PX4.
Um waypoint perto do Home seguido de Land (21) não é aceito como RTL (20).
Se o plano salvo terminar com Land, o painel informa qual comando precisa ser
revisto no QGroundControl.

A rotina de RTL do gateway PX4 verifica heartbeat, armamento e Home atual
antes de enviar o comando nativo de retorno. Depois do ACK, exige um novo
heartbeat no modo RTL. Em PX4 SIH com rede Docker isolada, a rotina confirmou
o modo e o simulador pousou e desarmou a 0,7 m do Home informado. O teste usou
a rotina interna do adaptador em um voo simulado próximo ao Home. O fluxo pelo
site e o destino da Pixhawk física ainda precisam de validação. A configuração
atual continua em modo passivo e a chamada pública rejeita o envio.
O painel permite enviar o arquivo `.plan` salvo no QGroundControl para registro
da revisão declarada por um administrador. O backend valida uma sequência
limitada de Takeoff, waypoints e RTL, preserva o destino do pedido e registra
o conteúdo e o hash em evento de auditoria, associados à versão atual da missão.
O registro por si só preserva a revisão e não autoriza o voo. Somente no
ensaio isolado `PX4_SITL_PLAN_VALIDATION`, a autorização pode apontar para o
evento de revisão e guardar o SHA-256 do artefato PX4. O gateway recebe esse
artefato no claim e confere o hash e os itens antes do upload. A revisão legada
permanece indisponível para missões com revisão QGroundControl. A autorização
com Pixhawk permanece bloqueada, inclusive se mudar a versão da missão. As
operações de registro, revisão e autorização bloqueiam a linha da missão
para evitar intercalar decisões sobre versões diferentes.

O cartão **Revisão da missão** mostra **Baixar plano revisado para o
QGroundControl** quando o arquivo registrado corresponde à versão atual.
O download recupera o arquivo original da auditoria e confere seu SHA-256.
Abra o arquivo baixado em **Plan → Open** no QGroundControl. O operador faz o
upload à Pixhawk pelo QGroundControl.

Os endpoints legados de autorização e comandos permanecem disponíveis para
testes e simulação. O painel oferece aprovação administrativa do pedido,
exportação, registro da revisão e acompanhamento da telemetria.
O painel mostra o registro da revisão do `.plan` mesmo após recarregar a
página. Se a versão ou o hash da missão mudou, indica que a revisão é antiga.
No ambiente normal, as ações de revisão legada e autorização ficam
indisponíveis nessa missão. O registro da revisão continua disponível nos
estados aceitos pela API.
Um arquivo real salvo pelo operador na versão Daily continha um item inicial
`MAV_CMD_SET_CAMERA_MODE` (530) e altitude AMSL da origem nula. O validador de
registro aceita essa configuração inicial e preserva a altitude desconhecida,
sem inferir valor. O mesmo arquivo não continha RTL; a pedido do operador foi
mantido intacto, e a revisão para o fluxo planejado ainda o rejeita pela ausência
de RTL. O reconhecimento de câmera no registro não prova suporte ao seu upload.
Posteriormente o operador salvou uma nova versão do mesmo arquivo com RTL. A
leitura local reconheceu os comandos 530, 22, 16 e 20 e aceitou sua estrutura;
a altitude AMSL permanece nula. O teste usou o waypoint do próprio arquivo como
destino esperado e não comprova que corresponda a algum pedido ou que o plano
tenha sido enviado, confirmado no veículo ou autorizado para voo.
O painel solicita a altitude AMSL ao operador quando o gateway não a informa.
O botão
de revisão legado continua vinculado à missão antiga, não ao rascunho `.plan`.

Nesta etapa, `AUTOPILOT_SYSTEM=PX4` seleciona heartbeats PX4 e força conexão
passiva. Upload, comandos, armamento e requisições de telemetria são recusados
na configuração. O sistema só pode observar mensagens já transmitidas; os
campos ausentes permanecem indisponíveis. A identidade configurada no backend
é publicada como `Não identificado` enquanto não há heartbeat válido. No modo
PX4, heartbeats posteriores com outro tipo de autopiloto são ignorados.
No modo de simulação a identidade e o estado são simulados. Não houve alteração de
parâmetros da Pixhawk, instalação de dependências ou remoção de integrações.

O modo `qgroundcontrol_forward` recebe telemetria via UDP no host e não abre
porta serial. Ele proíbe todos os gates de envio, pois o encaminhamento do
QGroundControl é unidirecional. Um teste usa MAVLink real em UDP loopback com
heartbeat sintético e verifica que o gateway não responde; isso não valida
QGroundControl, SITL ou hardware.

Teste de viabilidade: PX4 SIH em container com `--network none`, MAVProxy 1.8.75
compartilhando somente essa rede e dois clientes pymavlink locais em portas
distintas. Ambos receberam heartbeat e enviaram `MAV_CMD_REQUEST_MESSAGE`, com
`COMMAND_ACK` aceito. Isso demonstra um roteamento bidirecional no simulador;
os clientes não eram o QGroundControl nem o gateway real. Não houve ARM, START,
conexão com a Pixhawk ou mudança de parâmetros. É preciso integrar uma topologia
compartilhada e testá-la com os clientes reais antes de habilitar comandos.

Em uma sessão de bancada posterior, MAVProxy 1.8.75 foi iniciado no host com
COM7 a 57600 baud e saídas locais UDP 14555 e 14600. O QGroundControl foi
reconectado pelo link `DEVcore UDP` na porta 14555; a porta 14600 recebeu um
heartbeat PX4 desarmado em diagnóstico passivo. O backend também recebeu um
snapshot fresco via encaminhamento do QGroundControl. A sessão do roteador é
temporária, as conexões automáticas Pixhawk e SiK no QGroundControl foram
desligadas para liberar a serial e o link `radio` original foi preservado.
A recepção observada não valida o retorno de comandos do gateway pelo roteador;
os gates PX4 permanecem desativados e o preflight não foi confirmado no backend.
O checklist do QGroundControl mostrou `Not Ready` e aviso de bateria abaixo de
40%, sem leitura independente que confirme a carga real. Nenhum ARM ou START
foi enviado durante esta configuração.

O modo `mavlink_router` do gateway recebe dados de um roteador local por `udpin`
em `127.0.0.1`, identificando corretamente a topologia. A origem permanece
`UNKNOWN` até ser declarada pelo operador. Embora o roteador aceite tráfego nos
dois sentidos, este modo do gateway é deliberadamente passivo e rejeita todos os
gates de envio até a validação completa PX4. Não processa comandos nem claim.
O modo foi testado recebendo heartbeat do PX4 SIH por MAVProxy em rede isolada,
e o teste de ARM foi recusado. Na bancada foi iniciado um gateway no host com
origem `HARDWARE_REAL` declarada e `udpin:127.0.0.1:14600`; o backend recebeu
estado atualizado, desarmado e com todos os gates de comando desligados. Isso
valida a recepção pela nova topologia, mas não o envio do gateway ao veículo.
Em validação posterior, um PX4 SIH foi iniciado com rede Docker `none`, e um
MAVProxy compartilhou apenas essa rede. O gateway `mavlink_router` recebeu o
heartbeat e recusou ARM com os gates desligados. Após fechar o socket do gateway,
um cliente pymavlink independente ocupou a mesma porta UDP, enviou apenas
`MAV_CMD_REQUEST_MESSAGE` para `AUTOPILOT_VERSION` e recebeu `COMMAND_ACK`
aceito e `AUTOPILOT_VERSION` do simulador. Isso valida ida e volta do transporte
nessa topologia simulada, não o envio pela lógica do gateway/site. Nenhum ARM,
upload ou START foi enviado. O teste não acessou o hardware real.
Em 24/11/2026, foi exercitado no SIH isolado o método privado do adaptador que
solicita `AUTOPILOT_VERSION`, pelo mesmo socket do gateway e pelo MAVProxy; o
simulador retornou `COMMAND_ACK` aceito e a mensagem solicitada. Para esse teste
somente, o processo de teste alterou os sinalizadores internos após conectar ao
simulador. Nenhum gate ou configuração de produção foi habilitado. A proteção
do método foi reforçada para não emitir a consulta quando a conexão é passiva
ou a solicitação de telemetria está desabilitada. Isso comprova o método e a
topologia no teste controlado, mas não um caminho público habilitado no gateway,
nem uma requisição originada no site, nem o retorno de comando no hardware real.

Em 24/11/2026, outro teste do protocolo usou PX4 SIH em container com rede
`none` (imagem `px4io/px4-sitl` digest
`sha256:4f53405ea997c0e003f1eadefd1bfa2b6a632d3774e073d2eaa0851de3f34b86`),
MAVProxy na mesma rede isolada e `scripts/px4_sitl_protocol_probe.py`. Uma
missão sintética com Takeoff, waypoint e RTL inicialmente foi rejeitada no RTL
quando enviado com frame global relativo, com `MISSION_ACK` 10. No adaptador,
RTL PX4 agora exige frame 2 (`MAV_FRAME_MISSION`) e campos reservados zerados;
itens posicionais continuam exigindo frame 3. Após a mudança, o simulador
aceitou o upload e a releitura comparou os três itens. Uma segunda releitura
com waypoint esperado alterado foi rejeitada por divergência de coordenadas.
O teste chama métodos internos e altera apenas o indicador passivo em memória
do processo de teste isolado; não habilita os gates públicos, não usa arquivo
`.plan`, não testa revisão humana, autorização ou fluxo via site e não envia
ARM ou START. O tratamento dos valores nulos do `.plan` ainda precisa ser
definido e validado antes de integrar essa revisão ao plano executável.

O registro da revisão também verifica que existe ao menos um waypoint, que os
parâmetros dos pontos são numéricos ou, para orientação, nulos, e que eventual
altitude exibida coincide com o valor do item. O RTL deve usar frame 2,
continuação automática e apenas campos reservados nulos ou zero. A aceitação
continua sendo somente um registro de auditoria: não converte nulos em valores
MAVLink, não vincula o plano à autorização e não comprova upload ou voo seguro.
O evento e a resposta da revisão incluem os itens ordenados e seus sete
parâmetros exatamente como recebidos, incluindo valores nulos e o item opcional
de câmera. Essa representação é evidência da revisão, não é a missão executável
nem um substituto do hash do arquivo completo.

O registro gera um candidato preliminar em JSON determinístico, identificado
por SHA-256 e contendo os hashes do `.plan` e da missão legada e a versão da
missão. Para o drone do projeto, que não tem câmera, o item inicial 530 é
omitido da rota e os itens restantes são numerados a partir de zero. O arquivo
original e o item de câmera continuam na auditoria da revisão. Os parâmetros
reservados nulos de RTL tornam-se zero e a orientação dos itens posicionais
permanece nula. O evento guarda o candidato, seu hash e se omitiu o item.
Para gerar o candidato de uma revisão anterior à mudança, registre novamente
o arquivo, caso a missão ainda aceite revisão.
O artefato candidato fica na auditoria. No ensaio isolado, a autorização
armazena o ID do evento e o hash do candidato, e o claim projeta a rota revisada
sem sobrescrever o arquivo legado. Fora do ensaio, o gateway PX4 segue passivo.
Em teste com PX4 SIH isolado, o candidato de um plano sintético que continha o
item de câmera passou pela verificação do hash, upload e releitura dos três
itens da rota usando `scripts/px4_sitl_protocol_probe.py`. O teste não passou
pelo endpoint de autorização nem pelo executor operacional.

Em 24/11/2026, `scripts/px4_sitl_plan_validation.py` validou a sequência de
APIs de pedido, rascunho, revisão de um waypoint, autorização e claim.
O executor normal obteve ACK de upload, releu Takeoff, waypoint e RTL e
registrou `VERIFIED` em um PX4 SIH com somente loopback. A configuração de
teste usa `APP_ENV=test`, banco separado e os gates de ARM e START desligados.
O roteiro também verifica que o waypoint exportado tem espera de 5 segundos
antes de confirmar a releitura da rota.
O ensaio forneceu RTL e campos de checklist indisponíveis como dados sintéticos,
sem alterar os critérios do gateway e do backend em operação normal.
A validação não envolveu a Pixhawk, nem armamento ou voo simulado.
Na bancada, o supervisor da rota dedicada COM7 passou a declarar
`HARDWARE_REAL`. A telemetria confirmou heartbeat, drone desarmado, GPS e
Home frescos com todos os gates desligados. Preflight e configuração de RTL
continuaram sem confirmação na telemetria do site. No QGroundControl Daily,
os sensores e GPS passaram no checklist local, mas a tela indicou
`Not Ready` e mostrou alerta de bateria abaixo de 40%. O site mantém a
leitura de bateria indisponível quando ela não é recebida.

No ensaio de bancada seguinte, o backend registrou quatro amostras
`armed=true` da Pixhawk e confirmou o desarmamento posterior. O operador
realizou o armamento no QGroundControl. A função **Plan → Download** releu
da Pixhawk os itens Takeoff, Waypoint e Return To Launch da revisão 1
(hash do plano começando em `38a8b435`). A comparação da cópia salva pelo
QGroundControl encontrou diferença de posição de cerca de 1 cm em cada
ponto, altitudes e parâmetros equivalentes, e nenhum rally point. O Home
recebido ficou a cerca de 1,16 m da coordenada de decolagem revisada.
Essa releitura de bancada é evidência da rota armazenada.

Uma nova releitura em bancada pelo QGroundControl confirmou que a Pixhawk
armazenava os três comandos do plano revisado de hash iniciado por
`f1f36467b85bd34c`. A comparação conferiu comandos, frames, continuação
automática e parâmetros, incluindo a espera de 5 segundos no waypoint.
A posição foi comparada com tolerância de 0,0000002 grau. O ensaio leu a
missão existente, sem novo upload, armamento, início de missão ou transição
do pedido.

O QGroundControl identificou firmware PX4 1.17.0 e exibiu retorno direto
ao Home ou ponto de recuperação mais próximo, com subida configurada em
1 m. O checklist continuou indicando `Not Ready`. A origem de bateria
estava desativada na configuração e o painel seguiu sem confirmação de
preflight e RTL pela telemetria. A integração dessas evidências e a
validação do fluxo completo permanecem necessárias para a autorização real.

O adaptador também distingue orientação não especificada (`null` no contrato
interno) de orientação zero para Takeoff e waypoint PX4. Na transmissão
MAVLink, `null` torna-se NaN; na releitura, apenas NaN corresponde ao valor
nulo. Outros comandos não recebem essa conversão e o formato legado WPL rejeita
orientação nula. Em PX4 SIH isolado, upload e releitura preservaram orientação
não especificada, e uma comparação com orientação zero foi rejeitada. Isso não
faz a conversão integral do `.plan`, nem valida o item de câmera para upload.
Referências: [MAVLink MISSION_ITEM_INT](https://mavlink.io/en/messages/common.html#MISSION_ITEM_INT)
e [orientação em missões PX4](https://docs.px4.io/v1.18/en/flying/missions.html).

Em 23/11/2026, uma observação passiva recebeu heartbeat PX4 e posição do
QGroundControl em `localhost:14445` sem abrir serial ou enviar comandos. A
origem física do fluxo não foi estabelecida independentemente, e bateria,
versão do firmware e EKF não estavam disponíveis. O QGroundControl exibiu
`Pre-Flight Error`; não se deve inferir prontidão para voo. O backend e banco
responderam ao health check, mas o gateway Docker em execução usava uma imagem
antiga em simulação, sem cabeçalho de identidade exigido pelo backend, recebendo
HTTP 401. A integração até o painel não está validada.

Na continuação, o container antigo de gateway foi parado sem remover volumes,
e o gateway atualizado foi iniciado em sessão local com `qgroundcontrol_forward`,
todos os gates de envio desabilitados e UDP `127.0.0.1:14445`. O backend aceitou
heartbeats HTTP 200 e persistiu uma leitura PX4. A origem é `UNKNOWN` porque o
encaminhamento não distingue simulador de equipamento físico. A sessão local não
é uma instalação como serviço. O painel autenticado foi conferido visualmente:
apresentou a leitura PX4, heartbeat, GPS e origem desconhecida, com bateria e
EKF indisponíveis e comandos desabilitados. O container do painel ainda exibe
rótulos legados por usar uma imagem anterior às alterações no código.
Nesse modo o executor publica saúde, sem consumir comandos ou alterar journal
de missão; não use esta topologia unidirecional para enviar MAVLink ao veículo.
Em 23/11/2026 o operador confirmou que a fonte atual é a Pixhawk física. Na
sessão local foi definida a origem declarada `HARDWARE_REAL`; a origem continua
`UNKNOWN` por padrão e deve ser novamente confirmada se a fonte mudar. A leitura
`ESTIMATOR_STATUS` avalia flags recebidas e expira; não altera parâmetros nem
substitui as verificações do PX4. A proteção geofence é independente do plano;
o requisito legado no backend/gateway ainda bloqueia, e a migração desse gate
para a nova operação foi posteriormente removido conforme solicitação do operador.
Upload e comandos PX4 continuam bloqueados.

Por solicitação do operador, a condição adicional de EKF deixou de bloquear
backend, gateway e painel; a leitura recebida continua exibida como diagnóstico.
O preflight real do PX4 permanece obrigatório, bem como os demais checks. Isso
não altera nem desativa verificações na controladora. O encaminhamento do
QGroundControl permanece passivo e upload/comandos PX4 não foram habilitados.

Em 23/11/2026, o operador confirmou que a geofence está desativada e solicitou
que não seja requisito do sistema. Backend, gateway e painel deixaram de exigir
sua confirmação; nenhum parâmetro da Pixhawk foi alterado. As demais verificações
continuam independentes. Na observação passiva, `ESTIMATOR_STATUS.flags=959`
incluiu `ESTIMATOR_CONST_POS_MODE` (128); o estimador transmite dados, mas isso
não comprova uma solução de navegação válida. A posição mostrada no mapa não
elimina a necessidade de verificar o estado do PX4 no QGroundControl.
Em seguida, `docker compose build gateway` recriou a imagem; um container
isolado sem rede confirmou a presença do cabeçalho `X-Gateway-ID`. O novo
container não foi iniciado, para não concorrer com o gateway local, e a
comunicação da nova imagem com o backend ainda precisa de teste separado.

Pendências críticas: adaptar geração e revisão de missão, exportação `.plan`,
convenções de HOME e comparação de itens, checks, modos, progresso, painel e
contratos; testar fluxo completo no PX4 SITL antes de habilitar qualquer comando.
Há referências antigas no código e na documentação. A versão instalada do PX4
e a topologia física ainda não foram identificadas.

O adaptador de protocolo agora rejeita, antes de enviar `MISSION_COUNT`, itens
PX4 fora da lista restrita de comandos ou do frame relativo, incluindo o
`DO_GRIPPER` da rota legada. A releitura PX4 não aceita as normalizações de
HOME e parâmetros específicas do ArduPilot. Esses caminhos foram exercitados
com mensagens simuladas, mas continuam inacessíveis para upload pelo bloqueio
de configuração PX4. A lista não comprova compatibilidade com a versão do drone.

No PX4 1.17, o bit de pré-arm de `SYS_STATUS` reflete o modo atual. O painel
exibe esse sinal como diagnóstico do modo observado. O gateway descarta
o sinal e a amostra de preflight quando o modo muda. A confirmação operacional de preflight
continua exigindo o contrato de saúde e a validação do fluxo PX4.
O gateway também exibe os parâmetros `RTL_TYPE`, `RTL_RETURN_ALT`,
`RTL_DESCEND_ALT`, `RTL_LAND_DELAY`, `RTL_CONE_ANG` e `RTL_MIN_DIST`
dos `PARAM_VALUE` recebidos do alvo MAVLink. A referência de [RTL do PX4 1.17](https://docs.px4.io/v1.17/en/flight_modes/return)
descreve como o ângulo do cone e a distância ao destino afetam o retorno.
Os inteiros usam a codificação byte a byte do PX4. Os parâmetros que não
chegarem permanecem ausentes e os que chegarem expiram em 60 segundos. Sua
leitura não substitui a verificação da configuração operacional de RTL.
O gateway permanece passivo. Os parâmetros legados `FENCE_ENABLE` e `RTL_ALT`
continuam exclusivos do ArduPilot.

Na validação da Pixhawk 1.17.0, o site recebeu o sinal de pré-arm do modo
`POSCTL` e os quatro parâmetros de retorno após **Parameters → Tools →
Refresh** no QGroundControl. Foram recebidos tipo 0, altitude de retorno
de 1 m, altitude de descida de 1 m e espera de 0 s. As confirmações
operacionais permaneceram ausentes e o veículo desarmado.

Após a atualização do diagnóstico, uma releitura passiva da mesma Pixhawk
também exibiu o ângulo do cone de 45° e o raio de 10 m. O backend continuou
reportando `PREFLIGHT_NOT_RECEIVED` e `RTL_STATE_UNKNOWN`.

Em teste isolado com `px4io/px4-sitl:latest`, o `SYS_STATUS` chegou com o bit
de pre-arm saudável e sem os bits de presença e habilitação. O painel pode
mostrar essa leitura sob o modo atual. O QGroundControl também usa o
protocolo MAVLink de eventos de saúde e armamento. A recepção, metadados e
sumários completos por modo ainda devem ser implementados e validados antes
de considerar o preflight de missão confirmado.

O gate de ARM deixou de depender de `ALLOW_MISSION_START`: ARM continua exigindo
seus próprios gates e condições, enquanto START mantém seu gate separado. A
mudança não habilita ARM ou START PX4, nem altera a conexão passiva existente.
O painel identifica explicitamente que o ARM PX4 ainda não foi validado e que
a exigência `STABILIZE` é uma regra legada pendente de adaptação. Isso não muda
o modo da controladora nem substitui os bloqueios existentes no backend/gateway.

Referências: [modo missão PX4 multicóptero](https://docs.px4.io/main/en/flight_modes_mc/mission),
[protocolo de missão MAVLink](https://mavlink.io/en/services/mission.html),
[formato Plan do QGroundControl](https://docs.qgroundcontrol.com/master/en/qgc-dev-guide/file_formats/plan.html).
