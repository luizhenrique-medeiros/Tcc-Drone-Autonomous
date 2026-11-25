# Migração PX4 e QGroundControl

## Fluxo vigente

O cliente confirma o destino, o painel aprova o pedido e gera a revisão. Em
**Revisão da missão → Baixar missão para QGroundControl**, o administrador baixa
um `.plan` identificado por pedido e revisão. O arquivo usa Home/decolagem
da origem planejada, Waypoint no destino selecionado com espera de 5 s e RTL.
Decolagem e Waypoint usam altitude relativa ao Home. Se a altitude AMSL do
Home planejado não for informada, revise-a no QGroundControl.

O operador abre, revisa e opera a Pixhawk pelo QGroundControl. A opção
**Registrar arquivo revisado** guarda o arquivo salvo e seu hash na auditoria.
Exportação e registro de revisão são evidências de arquivo. O PX4 conserva
a autoridade sobre o estado e os comandos da aeronave.

O [gateway operacional](CONEXAO_DRONE_PX4.md) recebe telemetria passivamente.
O painel mostra campos recebidos, atualidade e progresso somente quando há
evidência suficiente de vínculo com uma única revisão. O administrador
confirma a entrega com evidência, separadamente de qualquer observação do voo.

## Histórico de integração

Os registros abaixo descrevem ensaios anteriores ou isolados. Controles de
protocolo e ARM experimental foram preservados nos testes. A interface normal
e o gateway operacional não montam esse fluxo.

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

### Protocolo legado em SITL isolado

O laboratório validou autorização, claim, upload, ARM, START e RTL com
`APP_ENV=test` e `PX4_SITL_PLAN_VALIDATION=true`, isolado da rede do host e
da aeronave. O contrato de comandos fica coberto nesse ambiente. Os cartões
experimentais estão fora do painel operacional.

### Validação do fluxo administrativo em SITL

A regressão completa de `scripts/px4_sitl_plan_validation.py` terminou com
código 0 no PX4 SIH isolado no Docker Desktop. Conferiu autorização de
administrador, idempotência HTTP, upload do plano revisado e releitura
`VERIFIED`. A API recusou confirmação falsa, START desarmado e ARM sem
enlace. A perda simulada do pacote ARM registrou timeout com uma tentativa.
ARM, START e RTL receberam ACK e estado posterior no simulador. A missão
registrou o waypoint, transitou para retorno e terminou com pouso e
desarmamento. Esse ensaio usou uma API de teste, banco descartável e
containers sem portas publicadas nem dispositivos físicos mapeados.

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

### Experimento de ARM em bancada

O perfil `px4_bench_arm` foi desenvolvido e testado com transporte substituído.
A nova divisão de responsabilidades retirou da instalação regular a preparação
desse perfil e a segunda serial. Consulte o [fluxo vigente](#fluxo-vigente).

### Releitura na Pixhawk pelo gateway Windows

Foi acrescentada uma consulta local e explícita que usa o enlace existente do
MAVProxy. A verificação em 24/11/2026 recebeu da Pixhawk PX4, IDs MAVLink 1/1,
os três itens do plano da revisão `f1f36467…`. O gateway recusou a identidade
2/1 antes de solicitar a missão e apontou divergência de coordenadas no
item 0 ao comparar com `1.plan`. Uma nova leitura conferiu o plano revisado.
O ensaio cobriu ida e volta de mensagens de leitura. As solicitações de
upload, ARM, START e RTL permanecem fora do perfil físico.

A consulta ativa descrita acima é registro histórico. O gateway operacional somente recebe mensagens.

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

O exportador operacional usa a revisão planejada e registra
`QGROUNDCONTROL_PLAN_EXPORTED`. O endpoint de rascunho anterior, que permitia
usar a posição atual como origem, foi preservado para compatibilidade.
`QGC WPL 110` também foi preservado como formato legado. O operador utiliza
o arquivo `.plan` pelo fluxo vigente.
