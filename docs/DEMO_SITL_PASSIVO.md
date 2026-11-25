# Demonstração do acompanhamento passivo em PX4 SITL

## Resultado

Ensaio concluído em 24/11/2026 (horário de Brasília). O pedido foi submetido
pela API pública de pedidos. O painel aprovou o pedido, preparou a revisão e
baixou o arquivo. O QGroundControl abriu esse mesmo arquivo e fez o upload ao
PX4 SIH. O piloto automático executou a missão, retornou, pousou e desarmou. O
painel avançou automaticamente depois da associação inicial. O pedido ficou
em `MISSION_READY` e continuou oferecendo a confirmação administrativa da
entrega.

O destino foi apresentado como **proximidade estimada por posição**. O PX4
enviou `MISSION_ITEM_REACHED` para 0 e 2, e `MISSION_CURRENT` para 0, 1 e 2.
O painel manteve o vínculo `OPERATOR` e encerrou o voo com a conclusão normal
da revisão sem confirmação no site.

## Ambiente

| Componente | Configuração verificada |
|---|---|
| PX4 | SITL 1.18.0 c0, commit `6d1773f4c1ca7d218074ea71a26f05abd46e2bf1`, SIH Quad X, `PX4_SIM_MODEL=sihsim_quadx` |
| QGroundControl | 5.1.5 Linux, sessão de teste Xvfb `:99` |
| Banco | PostgreSQL 17.5 / PostGIS 3.5, banco `demo`, volume `devcore-pdemo-pg` |
| API | FastAPI do projeto, `APP_ENV=demo`, revisão Alembic `0013_observed_flights`, [API de teste](http://127.0.0.1:18082/ready) |
| Painel | React do projeto, [painel de teste](http://127.0.0.1:15173), Chrome 158.0.8127.37 |
| Gateway | Adaptador do projeto com pymavlink 2.4.50, `qgroundcontrol_forward`, fonte declarada `SITL`, alvo MAVLink 1/1 |
| Rede | `devcore-pdemo-observe` interna, IP local ao namespace para MAVLink. O proxy web é o único membro também ligado à rede `devcore-pdemo-http`. |
| Enlaces | PX4 `127.0.0.1:18570` ↔ QGroundControl `127.0.0.1:14550`. QGroundControl → gateway `127.0.0.1:14558`. Gateway → API `http://devcore-pdemo-api:8000`. |

O namespace de PX4, QGroundControl e gateway não tinha rota padrão. As duas
publicações do proxy eram TCP em loopback. Nenhuma interface serial ou rádio
foi mapeada. A inicialização do PX4 chamou o binário diretamente para
manter os destinos no namespace de teste. O entrypoint da imagem padrão
pode trocar o destino para o host no Docker Desktop. Os mapas usaram o
traçado local, sem camada de imagens de satélite no ensaio isolado.
[SIH no PX4](https://docs.px4.io/main/en/sim_sih/).
[Encaminhamento MAVLink no QGroundControl](https://docs.qgroundcontrol.com/Stable_V5.0/en/qgc-user-guide/settings_view/mavlink.html).

## Pedido e plano executado

- Pedido `d3a1cf2a-36b0-47ea-8f53-618c4dcea0bf`.
- Missão `a48ffbb0-6a95-43d9-b1d8-7e6c99e0a2dd`, revisão **1**.
- [Arquivo baixado, aberto e carregado pelo QGroundControl](evidencias/demo-sitl-passivo/pedido-d3a1cf2a-36b0-47ea-8f53-618c4dcea0bf-v1-591e7411.plan).
- SHA-256 `591e741160bea4c7380b8222027a21a3696b2e2b1d6d83310ef9f0a6c965a1e8`, conferido na resposta de exportação, no download do navegador e na cópia dentro da sessão de QGroundControl.
- Origem e Home planejado **47.397742, 8.545594**, **489,42 m AMSL**. Destino **47.398100, 8.545750**, a aproximadamente **41,5 m**.
- Decolagem e waypoint configurados a **10 m relativos ao Home**. O waypoint foi transmitido com **5 s** no primeiro parâmetro. O último item foi RTL. O PX4 observou o perfil nativo de retorno e subiu a cerca de **30 m relativos** antes da descida.

O primeiro arquivo exportado no banco de teste usou a base padrão do projeto.
Descartei esse arquivo antes de qualquer upload. Corrigi as variáveis
`MAPS_DEFAULT_LATITUDE` e `MAPS_DEFAULT_LONGITUDE` do backend de ensaio e gerei
o pedido acima com origem no Home confirmado do SIH. O QGroundControl
executou os bytes exportados sem edição.

## Linha do tempo

Horários arredondados a segundos em **Brasília**. A trilha completa usa UTC.

| Horário | Estado ou evento | Evidência |
|---|---|---|
| 21:16:58 | Upload aceito pelo PX4 | Três `MISSION_ITEM_INT` do QGroundControl. `MISSION_ACK=0`. |
| 21:18:47 | Associação no painel | Administrador vinculou veículo SITL, pedido e revisão 1. Veículo conectado, desarmado e em solo. |
| 21:19:06 | Armado em solo | `HEARTBEAT` armado e `EXTENDED_SYS_STATE=1`. Sem execução ou item atual exibido nessa fase. |
| 21:19:11 | QGroundControl iniciou | `SET_MODE` para PX4 Auto/Mission. `MISSION_CURRENT` informou estado 3 e modo 1. |
| 21:19:12 | Decolando | `EXTENDED_SYS_STATE=3`. |
| 21:19:22 | Em voo e missão em execução | `EXTENDED_SYS_STATE=2`, heartbeat modo Missão e item atual 1. Item 0 informado como alcançado. |
| 21:19:35 | Proximidade do destino estimada | Posição a até 8 m em amostras sucessivas durante o item 1. |
| 21:19:37 | PX4 informou itens concluídos | `MISSION_CURRENT` mudou para 2 e estado 5. Item 2 informado como alcançado. |
| 21:19:38 | Retorno automático observado | Heartbeat em RTL. |
| 21:19:57 | Pousando | `EXTENDED_SYS_STATE=4`. |
| 21:20:28 | Pousado | `EXTENDED_SYS_STATE=1`. |
| 21:20:30 | Desarmado e voo encerrado | Heartbeat desarmado, pouso observado e sessão encerrada. |

O QGroundControl enviou a solicitação de armamento e a entrada em modo
Missão. A captura dessas ações não mostra solicitação manual de RTL ou
pouso. O log do PX4 registrou retorno, pouso e desarmamento por pouso.
O painel persistiu **123 pontos** do trajeto final. A confirmação de entrega
permaneceu disponível, com **0** eventos `ORDER_DELIVERY_CONFIRMED`.

## Mapeamento dos itens

A comparação usou os bytes exportados, os rótulos da interface do QGroundControl
e as mensagens de upload capturadas. As coordenadas e os parâmetros de cada
item foram conferidos separadamente dos índices.

| Etapa | Item no QGroundControl | Índice MAVLink | Evidência |
|---|---|---:|---|
| Decolagem | Takeoff | 0 | `MISSION_ITEM_INT.command=22`, frame 3, origem, altitude 10 m. `MISSION_CURRENT` e `MISSION_ITEM_REACHED`. |
| Destino e espera | Waypoint | 1 | Comando 16, frame 3, coordenadas do destino, 10 m e `param1=5`. O status nativo informou item atual 1. A captura registrou cerca de 4,66 s a até 8 m durante esse item. O PX4 encaminhou o avanço, sem `MISSION_ITEM_REACHED` do índice 1. |
| Retorno | Return To Launch | 2 | Comando 20, frame 2. `MISSION_CURRENT=2`, item 2 alcançado e heartbeat RTL. |

Com a missão carregada, `MISSION_CURRENT.total=3` e o identificador nativo
`4256334088` coincidiu com `MISSION_ACK.opaque_id`. O SHA-256 identifica
o arquivo local. O painel manteve a associação administrativa e os índices
MAVLink brutos. A comparação da captura ficou registrada como evidência
externa do ensaio. Antes da execução, o índice 0 foi observado em solo sem
disparar progresso no painel.

A [investigação posterior do waypoint](VERIFICACAO_BANCADA_PX4.md#investigação-do-waypoint-sitl)
comparou o ULog, os dois enlaces capturados e os eventos da API.

## Instrumentação e capturas

- [Resumo da captura e contadores](evidencias/demo-sitl-passivo/captura-resumo.json) e [estado final da API com eventos e trajeto](evidencias/demo-sitl-passivo/voo-final.json).
- QGroundControl em [plano carregado](evidencias/demo-sitl-passivo/qgc-plano.png), [armado em solo](evidencias/demo-sitl-passivo/qgc-armado.png), [início](evidencias/demo-sitl-passivo/qgc-inicio.png), [retorno](evidencias/demo-sitl-passivo/qgc-retorno.png), [pousando](evidencias/demo-sitl-passivo/qgc-pousando.png) e [encerrado](evidencias/demo-sitl-passivo/qgc-final.png).
- Painel em [exportação](evidencias/demo-sitl-passivo/painel-exportacao.png), [armado em solo](evidencias/demo-sitl-passivo/painel-armado.png), [decolando](evidencias/demo-sitl-passivo/painel-decolagem.png), [execução](evidencias/demo-sitl-passivo/painel-execucao.png), [retorno](evidencias/demo-sitl-passivo/painel-retorno.png) e [voo encerrado](evidencias/demo-sitl-passivo/painel-final.png). [Pedido com confirmação de entrega disponível](evidencias/demo-sitl-passivo/pedido-apos-voo.png).

A captura no loopback do namespace usou `tcpdump` nos enlaces UDP
14550 e 14558. Ela recebeu do QGroundControl **280 HEARTBEAT**, **13.991
GLOBAL_POSITION_INT**, **280 EXTENDED_SYS_STATE**, **280 MISSION_CURRENT**
e **22 MISSION_ITEM_REACHED** de 1/1. O `strace -f -yy -e trace=%network`
acompanhou o processo e as threads do gateway. Registrou **103.625 leituras**
bem-sucedidas do socket UDP 14558 e **zero envios desse socket**. A captura
também contou **zero datagramas originados em 14558**. A instrumentação registrou
**1.084 chamadas de envio TCP para a porta HTTP 8000**, incluindo o tráfego
normal de heartbeat e observações. A captura bruta e o rastreio ficaram em
`%TEMP%\devcore-passive-sitl-demo`.

## Correções e testes

- `drone_gateway/app/core/config.py` permite a observação QGroundControl com
  origem SITL em container quando a escuta é em loopback. As opções de
  transmissão continuam bloqueadas e o encaminhamento real segue no host.
- `drone_gateway/app/mavlink/pymavlink_gateway.py` preserva o identificador
  nativo também no encaminhamento de SITL.
- `backend/app/modules/missions/flight_observations.py` permite associar
  e acompanhar o PX4 SITL com a proveniência correta. O trajeto é buscado
  pela origem da sessão.
- `FlightTrackingPanel.tsx` e `OperationsPage.tsx` oferecem acompanhamento
  do PX4 SITL e identificam a origem na seleção de veículo.
- Passaram 6 testes direcionados no backend, 36 no gateway e 6 no painel,
  além de Ruff, ESLint e dos builds usados no ensaio. As imagens e os testes
  de demonstração foram executados em ambiente separado da operação real.

## Repetir neste computador

Os containers e o volume de teste foram preservados. Use os nomes de teste
abaixo. O arquivo `%TEMP%\devcore-passive-sitl-demo\api.env` contém o acesso
administrativo local e a origem configurada. As credenciais do ensaio ficam
fora do repositório.

```powershell
docker start devcore-pdemo-db devcore-pdemo-api devcore-pdemo-web
Invoke-RestMethod http://127.0.0.1:18082/ready
docker start devcore-pdemo-qgc
docker exec -d devcore-pdemo-qgc Xvfb ':99' -screen 0 '1440x1000x24' -nolisten tcp
docker exec -d -u 1000:1000 -e HOME=/tmp/pdemo-user -e XDG_RUNTIME_DIR=/tmp/pdemo-runtime -e XDG_CONFIG_HOME=/tmp/pdemo-config devcore-pdemo-qgc sh -c 'cd /opt/squashfs-root && dbus-run-session -- ./AppRun > /tmp/qgc-demo.log 2>&1'
docker start devcore-pdemo-px4 devcore-pdemo-gateway
```

O PX4 foi criado com `--network container:devcore-pdemo-qgc`,
`--entrypoint /opt/px4/bin/px4` e `-d` na imagem
`px4io/px4-sitl@sha256:4f53405ea997c0e003f1eadefd1bfa2b6a632d3774e073d2eaa0851de3f34b86`.
O arquivo de configuração da sessão QGC em
`/tmp/pdemo-config/QGroundControl/QGroundControl.ini` conserva
`forwardMavlink=true` e `forwardMavlinkHostName=127.0.0.1:14558`.
Gateway com `PX4_SITL_PLAN_VALIDATION=false` e os cinco controles `ALLOW_*`
desabilitados. Somente o QGroundControl usa o enlace bidirecional de voo.

1. No [painel de teste](http://127.0.0.1:15173), aprove um novo pedido,
   prepare a missão e baixe o plano. Use o cliente normal ou a API pública
   apontando para o endereço da API de teste. O destino da demonstração
   fica próximo do Home SIH. Para colocar o arquivo no seletor do QGC,
   copie-o com `docker cp` para
   `devcore-pdemo-qgc:/tmp/pdemo-user/Documents/QGroundControl/Missions/`.
2. Na sessão gráfica isolada, selecione **Plan → Open**. Revise os itens e
   pressione **Upload**. Volte para **Fly**. A sessão Xvfb pode ser inspecionada
   com `docker exec devcore-pdemo-qgc import -window root /tmp/qgc-tela.png`
   e `docker cp devcore-pdemo-qgc:/tmp/qgc-tela.png .`. Neste ensaio as
   interações no QGroundControl foram executadas com `xdotool` nessa sessão.
3. Na missão do painel, registre **Acompanhar esta missão → PX4 SIH Quad X
   (SITL)**. No QGroundControl, abra o indicador **Ready**, selecione **Arm**
   e mantenha pressionado para confirmar. Após observar **Armado em solo**,
   use **Start Mission** e confirme no QGroundControl antes do desarmamento
   automático em solo.
4. Acompanhe o painel sem alterar os estados. Aguarde o RTL, pouso e
   desarmamento. Confira o status do pedido e deixe a entrega sem confirmação.

Para registrar uma nova captura, inicie antes do upload na sessão de teste:

```powershell
docker exec -d devcore-pdemo-qgc tcpdump -Z root -i lo -U -s 0 -w /tmp/mavlink-repeticao.pcap 'udp and (port 14550 or port 14558)'
```

Depois de verificar o desarmamento, encerre a simulação e o gateway. O
frontend, a API e o banco podem continuar disponíveis para rever o voo.

```powershell
docker stop devcore-pdemo-gateway devcore-pdemo-px4
docker exec devcore-pdemo-qgc pkill -TERM -x Xvfb
docker stop devcore-pdemo-qgc
docker stop devcore-pdemo-web devcore-pdemo-api devcore-pdemo-db
```
