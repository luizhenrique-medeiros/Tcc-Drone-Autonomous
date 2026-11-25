# Verificação do ambiente habitual e da Pixhawk em solo

Verificação de 24/11/2026. Os horários no texto usam Brasília. Os arquivos
JSON preservam os horários UTC originais.

## Ambiente verificado

| Componente | Identificação |
|---|---|
| Painel habitual | http://localhost:5173, serviço Compose `admin`, bundle `index-JIIlTx1P.js` |
| API utilizada pelo navegador | http://localhost:8000/api/v1, serviço Compose `backend`, `APP_ENV=development` |
| Banco da API | `db:5432/drone_delivery`, PostgreSQL 17 com PostGIS 3.5.2, volume `drone-delivery_postgres_data` |
| Gateway do host | `python -m app.main`, PID 28996 após a verificação, iniciado pelo script `-ObserveOnly` |
| Perfil | `AUTOPILOT_SYSTEM=PX4`, `MAVLINK_MODE=qgroundcontrol_forward`, `MAVLINK_CONNECTION=udpin:127.0.0.1:14445`, `MAVLINK_FORWARD_SOURCE=HARDWARE_REAL` |
| Identidade do veículo | `dev-gateway-01`, `academic-vehicle-01`, UUID `8543d035-cd69-4860-840b-74fd7925c18c`, sistema/componente MAVLink 1/1 |
| Encaminhamento | UDP de `127.0.0.1:62088` para `127.0.0.1:14445`, porta de origem vinculada ao QGroundControl 5.1.5 no Windows, PID 2244 na amostra |

O QGroundControl do Windows já estava conectado. O Windows enumerou a COM4
como **PX4 FMU v6C.x** no barramento USB. A correlação combina a
identificação USB, o processo que encaminha o UDP e a origem cadastrada.
O UID único da placa e o handle de abertura da COM ficaram sem confirmação.
O gateway abriu somente o socket UDP. A sessão de revisão do plano foi
executada à parte, com QGroundControl 5.1.5 em container sem rede e sem
dispositivo físico.

O painel e a API foram reconstruídos a partir dos arquivos locais sobre
`f2ee398`. O SHA-256 de `flight_observations.py` no container coincide
com o arquivo local (`9ce2fe1e…23d285`). O gateway foi reiniciado a partir
da árvore local, com `app/main.py` em `37e6d1ac…8f5b5e`,
`app/core/config.py` em `dfce078a…883fea` e
`app/mavlink/pymavlink_gateway.py` em `05f1c938…b9290`.

Antes da atualização, o banco já estava em
`0013_observed_flights (head)`. A revisão foi reconferida após a
atualização. Sem migração pendente, o banco e seu volume foram mantidos.
O painel isolado da demonstração continuou em 15173, com API em 18082 e
banco separado. O veículo `px4-sih-pdemo`
(`a7edb7d0-0001-4ce3-a438-11be31f1c935`, origem `SITL`) e os dois
pedidos daquele ambiente foram encontrados apenas no banco isolado.
O simulador, o QGroundControl de simulação e seu gateway permanecem parados.

### Passividade, perda de dados e retomada

A instrumentação temporária do socket Python do gateway observou de
21:43:58 a 21:50:36 **155.520 datagramas recebidos** e **zero tentativas de
envio MAVLink** nos métodos de envio instrumentados. O ponto instrumentado
bloqueava qualquer tentativa detectada nesse enlace. A recepção incluiu
`HEARTBEAT`, `GLOBAL_POSITION_INT`, `EXTENDED_SYS_STATE` e
`MISSION_CURRENT`. A amostra ficou sem `MISSION_ITEM_REACHED` e sem
mensagem de versão que identificasse a placa por UID. Em separado, o log
`httpx` registrou **191 POST de heartbeat com HTTP 200** e **18 POST de
observações com HTTP 204** na API. A medição corresponde ao processo
instrumentado. Em configuração, os cinco controles `ALLOW_*` de comando,
transferência e consulta estavam desabilitados. O gateway habitual foi
restabelecido pelo script oficial após a amostra.
[Contadores e identificação da origem](evidencias/verificacao-bancada-px4/gateway-physical-passivity.json).

Durante a parada temporária do receptor, o painel exibiu **Telemetria
desatualizada. Último estado conhecido.** e conservou a leitura de
21:50:46. Após reiniciar o gateway, o painel voltou ao estado atual e
persistiu um evento de intervalo e um de retomada, ambos na mesma
associação. [Dados desatualizados](evidencias/verificacao-bancada-px4/05-painel-desatualizado.png)
· [Leitura restabelecida](evidencias/verificacao-bancada-px4/06-painel-restabelecido.png)
· [Resposta da API](evidencias/verificacao-bancada-px4/flight-resume.json).
A última consulta ao banco às 21:54:51 registrou heartbeat e conexão
ativos, com a Pixhawk desarmada em `LOITER`.

## Pedido de bancada

O pedido **TESTE DE BANCADA PX4 · revisão local** foi criado pela API do
cliente e aprovado, preparado e exportado pelo painel habitual.

- Pedido `62c5041a-b985-425a-bb6a-4d7c5d30762e`.
- Missão `657c05a9-c523-44d2-a899-1591f3598abf`, revisão **1**.
- Arquivo `pedido-62c5041a-b985-425a-bb6a-4d7c5d30762e-v1-39089c76.plan`.
- SHA-256 `39089c765f443cc21bb8ad66f7a032458ffdb5a608cbc593cf53eb759522a5ff`.

O hash do download coincidiu com o cabeçalho da API e com o arquivo aberto
na sessão de revisão do QGroundControl. O QGroundControl mostrou **Takeoff →
Waypoint → Return To Launch**, o trecho de 37,6 m e a altitude relativa
de 10 m no waypoint. Os campos do arquivo confirmam origem
`-23.117500, -46.550200`, destino `-23.117180, -46.550080`, altitude de
10 m relativa à origem nos dois primeiros itens (`frame=3`), 5 s de
espera no waypoint (`param1=5`) e retorno programado (comando 20).
A altitude AMSL da origem ficou sem preenchimento. O upload estava
indisponível na sessão de revisão.
[Exportação no painel](evidencias/verificacao-bancada-px4/01-painel-exportacao.png)
· [Plano aberto no QGroundControl](evidencias/verificacao-bancada-px4/02-qgc-revisao-local.png)
· [Waypoint e altitude](evidencias/verificacao-bancada-px4/02b-qgc-waypoint.png)
· [Plano baixado](evidencias/verificacao-bancada-px4/pedido-62c5041a-b985-425a-bb6a-4d7c5d30762e-v1-39089c76.plan).

Às 21:49:46, o administrador registrou **Acompanhar esta missão** para a
revisão 1 e a Pixhawk. O evento `FLIGHT_ASSOCIATED` contém o ator, o
veículo, a revisão, o evento de exportação e o hash do plano. A relação
com qualquer missão a bordo permaneceu **declarada pelo administrador**.
O estado observado foi *Em solo*, *Desarmado* e `LOITER`. Houve
posição, altitude relativa e velocidade reportadas, com oscilações na
bancada. Essas leituras não verificam a precisão da posição ou altitude.
A bateria ficou indisponível no snapshot conferido e a sequência da
missão permaneceu indisponível. A distância foi exibida nas amostras
que permitiram o cálculo. [Acompanhamento em solo](evidencias/verificacao-bancada-px4/03-painel-solo.png)
· [Mapa e eventos](evidencias/verificacao-bancada-px4/07-painel-posicao.png)
· [Associação na API](evidencias/verificacao-bancada-px4/flight-associate.json).

O pedido ficou `MISSION_READY`, com voo em `WAITING` e
**Entrega aguardando confirmação**. O banco registrou zero eventos de
decolagem, execução ou confirmação da entrega para o pedido e zero
comandos na fila para a missão. O painel
agora mostra o resultado do voo também no detalhe do pedido, em campo
distinto da entrega física. [Tela do pedido de bancada](evidencias/verificacao-bancada-px4/04-painel-pedido-e-entrega.png).

A intervenção física consistiu em observar a telemetria que o
QGroundControl já encaminhava. A interface gráfica do Windows estava
indisponível para automação. A abertura do arquivo ocorreu na sessão
isolada, preservando o planejamento do QGroundControl do Windows. O
ensaio registrou zero uploads, comandos à Pixhawk ou alterações de
parâmetros e firmware.

## Investigação do waypoint SITL

A análise cobre o voo `9765f290-8b2b-4189-841f-fdf17bcaacb0`, a missão
`a48ffbb0-6a95-43d9-b1d8-7e6c99e0a2dd`, revisão 1, e o veículo
`px4-sih-pdemo` (1/1). O identificador nativo `4256334088` e o
[arquivo exportado](evidencias/demo-sitl-passivo/pedido-d3a1cf2a-36b0-47ea-8f53-618c4dcea0bf-v1-591e7411.plan)
referem-se a essa sessão. O hash do plano está no relatório da
[demonstração](DEMO_SITL_PASSIVO.md). A janela analisada foi de
21:16:56 a 21:20:36.

| Camada | Evidência para os índices 0, 1 e 2 |
|---|---|
| PX4 SITL, ULog `mission_result` | As amostras de `seq_reached` mudam de `-1` para `0` e depois `2`. Houve `seq_current=1`. O alinhamento ao PCAP foi estimado pelo relógio de boot. |
| PCAP, PX4 18570 → QGC 14550 | `MISSION_CURRENT` em 142, 16 e 58 pacotes, respectivamente. `MISSION_ITEM_REACHED` em 11, 0 e 11 pacotes. O primeiro `CURRENT=1` apareceu às 21:19:22,126. |
| PCAP, QGC → gateway 14558 | Os mesmos totais por índice para ambas as mensagens. O primeiro `CURRENT=1` encaminhado apareceu às 21:19:22,127. |
| Gateway e API | A API persistiu `MAVLINK_MISSION_CURRENT` em 2, 1 e 1 eventos de atualização. As observações brutas de item alcançado persistidas foram 11, 0 e 11. |
| Eventos e painel | Um `FLIGHT_ITEM_REACHED` para 0 e um para 2, após deduplicação. Um `FLIGHT_DESTINATION_ESTIMATED` às 21:19:35,345 e zero confirmações do destino. O painel guardou **Proximidade estimada por posição**. |

O índice 1 como item atual está documentado desde o PX4. Sua confirmação
explícita já está ausente nas amostras do ULog e no primeiro enlace
capturado, antes do encaminhamento. **causa não demonstrada pelas evidências disponíveis**.
O registro disponível não cobre cada transição interna do firmware.
A ausência não fornece evidência de descarte no QGroundControl, gateway
ou API. A chegada permaneceu estimada. A investigação dispensou novo voo
e alteração de processamento.
[Comparação dos registros](evidencias/verificacao-bancada-px4/waypoint-verification.json)
· [Estado final arquivado](evidencias/demo-sitl-passivo/voo-final.json).

## Retomar após reiniciar o Windows

1. Abra o Docker Desktop. Na raiz do repositório, execute:

   ```powershell
   docker compose up -d db backend admin
   docker compose ps
   Invoke-RestMethod http://localhost:8000/ready
   ```

2. Abra o QGroundControl habitual com a conexão PX4 existente e confirme
   o encaminhamento para `127.0.0.1:14445`. O gateway usa o perfil da
   tabela. O script fixa `ALLOW_MISSION_UPLOAD`, `ALLOW_FLIGHT_COMMANDS`,
   `ALLOW_MISSION_START`, `ALLOW_VEHICLE_ARM` e
   `ALLOW_TELEMETRY_REQUESTS` em `false`. Execute em outro terminal,
   uma instância por porta:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_gateway.ps1 -ObserveOnly
   ```

3. Abra o [painel habitual](http://localhost:5173), confira a origem
   *Hardware real* e a atualização recente. Para outro pedido, aprove,
   prepare e baixe o plano, revise-o no QGroundControl e associe a
   revisão correspondente ao veículo. O vínculo do pedido de teste
   permanece registrado e deve ser substituído pela revisão operacional
   quando for acompanhar outro pedido.

## Regressões da revisão

- Backend: 26 testes de `test_observed_flights.py` e
  `test_qgroundcontrol_draft.py`, com Ruff e build Docker.
- Painel: 9 testes de `mission-planning.test.tsx` e
  `vehicle-observations.test.tsx`, com ESLint e build local e Docker.
  Os casos cobrem estado de solo, voo encerrado com entrega pendente e
  histórico de associação substituída antes do voo.
- Gateway: 20 testes direcionados de UDP local, encaminhamento passivo e
  bloqueios de consultas e comandos.
- Navegador no ambiente habitual: aprovação, preparação, exportação com
  verificação de hash, associação, perda e retomada de telemetria.
  O QGroundControl isolado abriu o arquivo exportado em revisão local.
