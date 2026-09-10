# Estado das integrações

## Revisão de origem após reposicionamento — 10/09/2026, 13:16–13:35 UTC

- Implementado `revise-origin` no domínio/backend e painel, com versão/hash
  esperados, confirmação do ponto definitivo e motivo. Preserva destino,
  altitude e pedido; arquiva JSON/arquivo completos anteriores em SystemEvent.
  Exige observação, desarmamento/saúde frescos, sem comandos pendentes nem START.
- Gateway reconhece a versão substituída por endpoint autenticado/idempotente;
  resposta vinculada e nova leitura física antecedem liberação do journal.
  Não há novo schema, acesso direto ao banco ou mudança de MAVLink/parâmetros.
- Regressões executadas: backend **88 aprovadas + 1 opcional pulada**, gateway
  **181 aprovadas**, admin **119 aprovadas**; Ruff, format, ESLint e build Vite
  aprovados. Flutter não foi alterado nem teve sua suíte repetida nesta etapa.
  Permanece aviso conhecido de tamanho do bundle e depreciação Starlette/httpx.
- SITL nativo isolado, sistema 42 em TCP 5890: upload de sete itens, ACK e
  releitura completos; liberação do journal com resposta HTTP simulada; nova
  releitura real (cache local de verificação removido somente no ensaio)
  confirmou a missão original ainda presente. Instrumentação confirmou zero
  clear/upload/ARM/START/parâmetro na liberação. Sem voo. Script e logs em
  `%TEMP%/devcore-sitl-origin-5c3e8a01322449368cb2a764e561f25e/`.
- Backend/admin reconstruídos e implantados; `/ready` 200, containers healthy,
  `pip check` aprovado. Gateway recuperado pelo supervisor em observação com
  quatro gates falsos. Nenhuma dependência ou extensão nova necessária.
- Às **13:33:42 UTC**, missão `89d7dcd8` passou a **v2/GENERATED** pelo painel,
  com origem/retorno GPS `-23.1186131,-46.5812321`, destino preservado
  `-23.1185679,-46.5812476`, distância só de ida **5,27 m**, altitude **10 m**.
  Hash v2: `5d9c2cd16510130b8fa64dcd2d7341385c4727d9850a9b1d3616820c2ac29f89`.
  Eventos `MISSION_ORIGIN_REVISED` e `MISSION_RETIRED_VERSION_RELEASED`
  confirmados; journal liberado pelo próprio executor, sem edição manual.
- Exportada às **13:34:10 UTC**; download em
  `Downloads/missao-89d7dcd8-85d2-4e8b-bc34-028911355c0b (2).waypoints`,
  SHA256 conferido contra backend. Estado `EXPORTED_TO_MISSION_PLANNER`,
  revisão ainda nula; nenhuma autorização v2, upload físico, ARM ou START novo.
- Pendente operacional: revisar a nova rota no Mission Planner e conferir Home
  após mudança de local. Home continuava `-23.1185925,-46.5812463`, diferente da
  nova origem. A tolerância da releitura não foi ampliada e Home/RTL não foram
  alterados. Bateria **45%** às 13:34:45 UTC, perto do mínimo configurado de 40%.
  Esta revisão de software não comprova voo e não torna a missão pronta para START.
- Às **13:37:17 UTC**, veículo continuava desarmado, quatro gates falsos e bateria
  **44%**, sem comandos novos desde 13:16. Cliente reconectado após reload
  passou a mostrar **Exportada para revisão**, sem reutilizar telemetria v1 como
  nova amostra. Sem claim v2, a ausência de telemetria da missão é esperada;
  saúde passiva do veículo continua no painel.
- Arquivos desta alteração: backend `missions/service.py`, `missions/schemas.py`,
  routers `admin.py`/`gateway.py` e `core/config.py`; gateway `models.py`,
  `clients/backend_client.py`, `missions/executor.py`; painel `MissionPage.tsx`,
  `OriginRevisionDialog.tsx`, `origin-revision-readiness.ts` e contratos/adaptadores
  de serviços; testes `test_origin_revision.py` em backend/gateway e
  `origin-revision.test.tsx` no admin. Contratos, arquitetura, requisitos, regras
  de negócio, protocolo, plano de testes e este relatório foram atualizados.

## Retomada após login e snapshot da missão — 10/09/2026, 12:39–12:44 UTC

- Login confirmado ao vivo nas duas aplicações. Missão `89d7dcd8` preservada em
  `VERIFIED`, versão/hash inalterados; nenhum ARM/START novo registrado até
  12:44:20 UTC. Telemetria real atual: conectado, desarmado em `STABILIZE`,
  preflight válido, bateria 63%, 17 satélites. Os avisos físicos anteriores
  continuam no histórico e devem ser reavaliados se reaparecerem.
- Sessão operacional temporária do gateway iniciada às 12:40:22 UTC com
  `ALLOW_VEHICLE_ARM`, `ALLOW_FLIGHT_COMMANDS` e `ALLOW_MISSION_START=true`,
  conforme autorização de bancada já recebida e acoplamento dos gates existente.
  `ALLOW_MISSION_UPLOAD=false`; `.env` e parâmetros físicos não foram alterados.
  Habilitar esses gates não enviou ARM nem START. Não executar rota ou entrega.
  Supervisor reiniciado e reaproveitando o gateway; se precisar substituí-lo,
  o novo processo voltará aos quatro gates fechados.
- Ao parar o supervisor pela sessão de execução do agente, também terminaram
  seus filhos gateway/Flutter: o host encerrou a árvore de processos, apesar
  de o script não implementar esse encerramento. O gateway foi reaberto na
  sessão operacional e o novo supervisor recuperou o Flutter. Não confundir
  essa interrupção do host com comportamento de um CTRL+C em terminal comum.
- Inspeção do cliente encontrou telemetria atual, mas estado da missão
  `Indisponível` após login. Causa: WebSocket publicava somente `order.snapshot`
  ao conectar; `mission.status` dependia de uma nova transição. Correção de
  13 linhas em `backend/app/api/v1/routers/websockets.py`: devolver também a
  missão persistida do pedido autenticado, reutilizando `MissionRead`, sem
  alterar domínio/estado, gerar evento ou comando. Flutter não foi alterado.
- Regressão reproduzida antes da correção (`pong` em vez de `mission.status`)
  e aprovada depois em duas conexões sucessivas, sem comando gerado. Casos de
  pedido sem missão e propriedade mantidos. Backend: **67 aprovados, 1 opcional
  PostgreSQL pulado**, Ruff/format aprovados. Imagem reconstruída/implantada,
  `/ready` 200, container healthy e `pip check` aprovado. Não foram repetidas
  nesta pequena correção as suítes gateway/admin/Flutter da seção anterior.
- Após reload autenticado e abertura do pedido no Chrome, o cliente passou a
  exibir `Missão verificada`, a observação de que essa etapa não inicia voo,
  telemetria `Hardware real`, `Armado: Não` e dado não vencido. Conferência
  visual realizada às 12:44 UTC; painel manteve a mesma missão verificada.
- Renovação aberta no painel com operador `luiz` preenchido e três confirmações
  desmarcadas. Renovação real e novo ARM ainda pendentes do operador; não
  prolongado o registro expirado nem gerado armamento como efeito de reconexão.

## Conexões automáticas e renovação — 10/09/2026, 12:27–12:35 UTC

Implementado sem trocar a arquitetura, a rota, o banco ou parâmetros da Pixhawk:

- `scripts/start_connections.ps1`: DB/backend/admin com readiness, reaproveitamento
  de cliente/gateway, mutex por projeto e recuperação dos processos. Novos
  gateways usam os quatro gates fechados; journal e processos existentes são
  preservados. Docker ainda precisa estar disponível; COM/mirror continuam sob
  responsabilidade do Mission Planner na topologia configurada.
- Backend/painel: renovação explícita de autorização consumida vencida em
  `VERIFIED`, com novo registro auditado, novas confirmações, mesma identidade
  e artefato, saúde atual desarmada e nenhum comando pendente/incerto. Não
  prolonga registro antigo, reenvia missão ou combina ARM/START.
- Gateway: revalidação do claim renovado antes de novo comando humano;
  telemetria passiva publicada enquanto aguarda operador. Painel: reconexão
  WebSocket continua após oito falhas, com atraso limitado e parada em recusa
  de autenticação. Login e proteção de armamento foram preservados.

Evidências executadas:

- `test_all.ps1 -SkipBuilds -FlutterSdkRoot C:\Users\Luiz\Documents\flutter`:
  **exit 0**, 66 testes backend, 171 gateway, 117 admin e 98 Flutter aprovados
  (452 total). Um teste opcional PostgreSQL foi pulado porque
  `SAVED_LOCATIONS_POSTGRES_TEST_URL` não estava configurada. Ruff/format,
  ESLint, Dart format/analyze e Compose validaram. A primeira passagem acusou
  somente formatação de um teste novo; após formatar, a suíte completa passou.
- Imagens backend e admin reconstruídas e implantadas. O build admin mantém
  aviso de bundle grande; não houve erro TypeScript. Nenhuma dependência nova
  nem extensão foi instalada. APK/Web release Flutter não foram reconstruídos
  nesta rodada; o cliente foi recompilado pelo servidor de desenvolvimento.
- `-ValidateOnly` passou com Flutter oficial 3.47.0/Dart 3.13.0. Segunda instância
  do supervisor saiu sem duplicar processos. Recuperação do gateway foi
  observada após encerramento do processo; depois, encerrando somente o processo
  Flutter que possuía 5174, o supervisor recompilou e devolveu HTTP 200 com o
  título esperado, sem intervenção. Não se simulou queda de energia/Windows.
- Missão real `89d7dcd8-85d2-4e8b-bc34-028911355c0b` permaneceu `VERIFIED`, v1,
  SHA `cb435b4d8f45414a51d97ffa32895242225d117cca350a4466f39ecd22d85821`.
  Não foram criados comandos ARM/START novos nesta rodada. As amostras passivas
  têm origem `HARDWARE_REAL`, modo `STABILIZE` e `armed=false`.
- Às 12:34:25 UTC, as últimas 29 amostras em 60 segundos mostravam conexão e
  preflight válidos, todas desarmadas. Entre 12:28:24 e 12:28:39 UTC houve
  `GPS Glitch or Compass error` / `PreArm: GPS glitching`, com bloqueio correto
  na tela; a recuperação posterior não apaga esses avisos nem comprova voo.
- No Chrome, botão e modal de renovação foram abertos, com checklist inicialmente
  desmarcado e confirmação desabilitada. Nenhuma renovação real foi submetida.
  A sessão administrativa expirou depois; foi solicitado login ao usuário.
  Após recompilar/recarregar o cliente, ele também apresentou a tela de login.
  Nenhuma senha ou duração de sessão foi alterada.

Arquivos principais desta rodada: launchers `start_connections.ps1`,
`start_development.ps1`, `start_gateway.ps1` e `compose.yaml`; domínio em
`backend/app/modules/missions/service.py`; executor, interface e adaptadores em
`drone_gateway/app`; componentes de autorização/ARM e `useOperationsStream` no
admin. As regressões e os contratos correspondentes foram atualizados. A base
Flutter permaneceu sem alterações de código.

Limite restante: novo ARM físico exige sessão administrativa válida, revisão
presencial atual, preflight estável e sessão operacional de gates explicitamente
habilitada. O supervisor de conexões fica em observação. Este trabalho não
comprova motores acionados, missão autônoma executada, entrega ou voo real.

## Correção da fila MAVLink em 10 de setembro de 2026

### Evidência de bancada anterior à correção — 11:55–12:02 UTC

- O usuário confirmou revisão externa da versão 1 e, em seguida, as inspeções
  físicas, identificando o operador como `luiz`. Pelo admin foram registradas a
  revisão da missão `89d7dcd8-85d2-4e8b-bc34-028911355c0b` e a autorização separada
  às 11:57:48 UTC, consumida pelo gateway às 11:57:49 UTC.
- Upload físico recebeu `MISSION_ACK` aceito às 11:57:51 UTC. A primeira releitura
  bloqueou em `HOME_POSITION`; a origem observada coincidia com a versão revisada.
  A releitura posterior concluiu às 11:58:20 UTC, publicando `VERIFIED` com os sete
  itens comparados. Nenhum parâmetro/Home/fence foi alterado para fazê-la passar.
- Após habilitação separada dos gates, o operador acionou o botão de ARM do admin.
  As solicitações `73fa8d11-2753-4e5b-a3eb-b148ae1a9080` e
  `61d50a09-7198-4c6d-842f-df24dd3b7c76`, às 12:00:29 e 12:00:57 UTC, terminaram
  `FAILED`: a preparação local atingiu o limite de 500 mensagens sem observar a
  fila vazia. O bloqueio ocorreu antes de `command_long_send` do ARM; o
  `ACKNOWLEDGED` registrado era somente recebimento pelo gateway, não ACK do drone.
- Os quatro gates foram novamente fechados às 12:02 UTC. Missão e journal foram
  preservados como `VERIFIED` / `WAITING_OPERATOR_ARM`. O prazo da autorização
  consumida terminou às 12:02:48 UTC; não foi prorrogado nem reutilizado.

### Implementação e validação — após autorização para corrigir

- Alteração restrita ao adaptador MAVLink, seus testes e documentação. O consumo
  normal de 50 mensagens por ciclo de dois segundos foi substituído por drenagem
  com limites de tempo e quantidade: 100 ms / 10.000 mensagens por leitura;
  preparação ARM até 1 s (limitado também pelo timeout configurado). A fila precisa
  esvaziar; congestionamento persistente publica `STALE` e continua bloqueando.
  Não se descarta a fila, aceita ACK antigo ou remove verificações para armar.
- Foram acrescentados 12 casos de teste. Os 11 casos iniciais reproduziram a falha
  antes da mudança; depois, **162 testes do gateway passaram**. Ruff check,
  Ruff format check (40 arquivos) e `pip check` aprovados. Backend, admin e Flutter
  não foram alterados nem tiveram suas suítes repetidas nesta correção.
- SITL nativo isolado em `tcp:127.0.0.1:5890`, sistema `42/1`, sem backend operacional
  ou vínculo com a COM7/UDP 14551. O primeiro estímulo de rajada não obteve aceite
  da taxa solicitada e parou antes de ARM. Com intervalo de 10 ms aceito, a leitura
  de saúde drenou **828 mensagens**; upload e releitura dos sete itens passaram;
  a preparação do ARM drenou **852 mensagens**. O ARM normal virtual recebeu ACK
  correlacionado e heartbeat armado, seguido por desarme automático confirmado.
- O teste SITL não enviou START, AUTO, throttle ou alteração de parâmetros. A taxa
  temporária de ATTITUDE foi ajustada somente no simulador. A fence virtual estava
  desabilitada por padrão e RTL/versão ausentes no health: a evidência é do adaptador
  e do tratamento de rajadas, não do preflight completo do backend ou de voo real.
- Imagem reconstruída com `docker compose --profile gateway build gateway`, sem
  iniciar o container. Gateway host reiniciado com o código corrigido às 12:10 UTC,
  quatro gates falsos e journal intacto. Entre 12:10:30 e 12:11:29 UTC, 30 snapshots
  físicos permaneceram conectados, desarmados e com os quatro gates fechados.
  Nenhum novo ARM/START físico foi solicitado
  durante a correção. Nova tentativa física permanece pendente de autorização
  válida e verificações atuais; falhas anteriores não são repetidas automaticamente.

## Novo pedido e missão em 10 de setembro de 2026 — 11:45–11:49 UTC

- Após ajuste manual do pino pelo usuário e confirmação explícita, somente
  `MAPS_DEFAULT_LATITUDE` e `MAPS_DEFAULT_LONGITUDE` do `.env` local foram alinhados
  à Home recebida. Backend recriado com `docker compose up -d --no-deps backend`;
  configuração efetiva conferida e `/ready` respondeu com banco pronto. O `.env`
  continua ignorado pelo Git. O ajuste de base aplica-se às novas missões; não
  altera Home física, fence ou destinos de pedidos anteriores.
- Pelo Flutter autenticado foi criado/submetido o pedido
  `36d254fd-22da-4e32-9062-84bb320328f9`, um Combo Burger e PIX simulado, identificado
  expressamente como teste de bancada sem hélices, sem executar rota/decolagem/entrega.
  O novo ponto conserva a precisão do pino; o atalho salvo não foi atualizado.
- No admin, aprovação e preparação foram ações separadas. Missão criada:
  `89d7dcd8-85d2-4e8b-bc34-028911355c0b`, versão 1, sete itens, altitude 10 m,
  distância origem–destino 3,40 m. A origem persistida coincide com a Home autorizada.
  A consulta PostGIS confirmou o segmento inteiro dentro da fence lida nesta sessão,
  com margem mínima 13,02 m; isso não substitui a inspeção física ou revisão no Planner.
- Exportação acionada no painel e registrada às 11:47:39 UTC como
  `EXPORTED_TO_MISSION_PLANNER`. SHA-256 do conteúdo canônico conferido:
  `cb435b4d8f45414a51d97ffa32895242225d117cca350a4466f39ecd22d85821`.
  Gravação do download no disco não foi confirmada; a página interna de downloads
  do Chrome não é acessível pelo controle disponível. O botão de exportação permanece
  no painel para o operador baixar e abrir o arquivo no Mission Planner.
- O Flutter recebeu o andamento "Preparando entrega" e estado "Missão gerada".
  Foi observada uma inconsistência de texto: "A rota foi revisada" aparece embora
  `reviewed_at` permaneça nulo. A revisão está pendente no estado canônico do backend
  e no admin; esse texto não é evidência de revisão. A UI não foi alterada nesta etapa.
- Revisão e claim permanecem nulos; nenhum comando registrado no gateway. Último
  snapshot verificado: `STABILIZE`, desarmado, quatro gates falsos. Nenhum upload
  de missão de voo, ARM, START ou parâmetro físico enviado nesta etapa.
- Validação realizada por UI, configuração efetiva, `/ready`, consultas somente
  leitura de missão/waypoints/saúde, hash e geometria. Não houve mudança de código
  nesta etapa; as suítes automatizadas não foram repetidas. Próximo passo: revisão
  humana da versão 1 no Mission Planner antes da autorização/checklist de bancada.

## Ensaio de bancada em 10 de setembro de 2026 — continuação

Entre 11:31 e 11:40 UTC, após confirmação do operador e login nas duas aplicações:

- Chrome conectado: admin autenticado com telemetria física; Flutter autenticado,
  catálogo e carrinho com um Combo Burger, seleção de região e mapa híbrido MapTiler
  renderizados. O novo pedido ainda não foi confirmado; destino aguarda escolha do
  operador. Não reutilizar o ponto salvo fora da fence nem alterar pedidos antigos.
- Gateway host encaminhado pelo Mission Planner recebeu e publicou saúde real do
  alvo `1/1`: `STABILIZE`, desarmado, GPS fix 3/24–25 satélites, EKF e preflight
  positivos, bateria 88–90%. Home, RTL e fence foram recebidos; versão do autopiloto
  não foi retornada nessa sessão. Essas leituras são snapshots, não prontidão permanente.
- Leitura MAVLink da fence física confirmou quatro vértices de inclusão,
  `FENCE_ENABLE=1`, `FENCE_TYPE=7`, raio 300 m, altitude máxima 30 m, margem 5 m,
  `FENCE_OPTIONS=0` e `RTL_ALT=1500`. Nenhum parâmetro ou polígono foi escrito.
  A origem configurada no backend estava 4,05 m distante da Home atual; ambas dentro
  do polígono, mas a diferença exige alinhamento explícito para a nova missão e sua
  releitura. Não mover a Home física para fazer a verificação passar.
- Encontrado SITL nativo já instalado com Mission Planner, independentemente do WSL.
  Executado em diretório temporário isolado, sistema `42/1`, instância 13,
  `tcp:127.0.0.1:5890`, sem ligação à COM7/UDP 14551 ou ao backend operacional.
  A primeira tentativa recebeu ACK dos sete itens e falhou corretamente na releitura
  de `LOITER_TIME.param3`, antes de qualquer ARM.
- Correção adicional restrita às normalizações padrão `LOITER_TIME.param3: 0 → 1`
  e `LAND.param4: 0 → 1`, conforme AP_Mission; demais valores/parâmetros permanecem
  comparados. Cinco casos de regressão falharam antes da correção. Depois dela,
  **150 testes do gateway aprovados** (16 novos nesta continuação), Ruff check,
  Ruff format check e `pip check` aprovados. Imagem reconstruída com
  `docker compose --profile gateway build gateway`; container não iniciado.
  Suítes de backend, admin e Flutter não repetidas nesta correção do adaptador.
- Repetição no SITL: **upload de sete itens com ACK, releitura integral verificada,
  ARM normal separado com ACK e heartbeat armado, desarme automático observado**.
  Nenhum START, AUTO, throttle, force-arm ou alteração de parâmetros. O probe testa
  o adaptador MAVLink, não o fluxo completo de autorização do backend; sua fence
  virtual estava desabilitada por padrão e a versão não foi recebida. Portanto não
  é prova de preflight integral do sistema, hardware, motores reais ou voo.
- Gateway físico reiniciado com o código atualizado e os quatro gates falsos.
  Nenhum upload de missão de voo, ARM ou START físico foi enviado. Permanecem
  pendentes: escolha do novo destino, alinhamento da origem, criação/exportação,
  revisão humana da versão no Mission Planner e autorização/checklist específicos.

## Retomada inicial em 10 de setembro de 2026 — registro anterior ao ensaio

Branch `final-2`, commit-base `76a6cc3`. A seção abaixo registra somente esta
retomada; as tabelas seguintes preservam o histórico de agosto e não representam
testes repetidos hoje.

- Corrigida a equivalência da releitura no gateway: pares de frames globais,
  `current` como estado de execução, frame não posicional de `DO_GRIPPER` e Home
  absoluta do item zero. A conversão da Home exige `HOME_POSITION` recente,
  origem coincidente e altitude MSL válida; divergências reais continuam bloqueadas.
  Detalhes e fontes fixadas em [DRONE_PROTOCOL.md](DRONE_PROTOCOL.md).
- Gateway: **134 testes aprovados**, incluindo **49 novos casos**; antes da correção,
  a primeira bateria de regressão reproduziu 19 falhas. Ruff, format e `pip check`
  aprovados; imagem Docker do gateway reconstruída, mas serviço não iniciado.
  Uma repetição da suíte encontrou `WinError 32` ao substituir o journal temporário
  em um teste existente de retomada de claim. O teste isolado e a suíte completa
  passaram na repetição seguinte (134/134); a causa do bloqueio de arquivo não foi
  determinada e o código do journal não foi alterado.
- Containers existentes de banco, API e admin reiniciados. `/health`, `/ready` e
  admin responderam HTTP 200. Banco observado em `0007_vehicle_arm_command`.
- Flutter Web iniciado pelo launcher com SDK oficial explícito Flutter 3.47.0 /
  Dart 3.13.0, perfil integrado e MapTiler configurado. `http://localhost:5174`
  respondeu HTTP 200. O SDK não estava no PATH; não se usou o fork interno.
- A missão gerada na sessão anterior continua `EXPORTED_TO_MISSION_PLANNER`,
  versão 1, sem revisão concluída, claim ou comandos registrados. O SHA-256 do
  arquivo exportado confere com o banco. Nenhum pedido, destino ou autorização foi
  alterado para contornar a revisão.
- Diagnóstico **receive-only** em `udpin:127.0.0.1:14551`: COM7 enumerada, porém
  nenhum heartbeat recebido antes do timeout (`VEHICLE_TIMEOUT`). Porta enumerada
  e processo Mission Planner aberto não comprovam conexão MAVLink.
- Browser retornou lista vazia; Computer Use retornou falha de conexão com o pipe
  nativo. Portanto, não houve validação visual do Flutter/admin/Mission Planner.
- Nenhum upload, ARM, START, alteração de parâmetro ou de GeoFence foi enviado.
  SITL não executado: o WSL lista somente `docker-desktop`. As suítes de backend,
  admin e Flutter não foram repetidas nesta alteração restrita ao gateway.

**Pendência operacional naquele momento:** a revisão de 03/09 encontrou o destino aproximadamente
1,64 m fora do polígono de inclusão então recebido do veículo. Essa evidência é
histórica; sem heartbeat e leitura atual da fence não se pode confirmar a condição
de hoje nem liberar a missão. É necessário restaurar o link, validar o destino e a
rota dentro da margem da GeoFence e concluir revisão/checklist e SITL antes de
qualquer autorização operacional. Não mover o destino de um pedido já submetido
nem ampliar/desativar a fence automaticamente.

## Registro histórico — 21 de agosto de 2026

Atualizado em 21 de agosto de 2026, branch `final-1`, commit-base
`b61913995c31933477b2e73910e6d275205d14d2`. **Implementado** significa código e contrato presentes;
**testado** significa comando executado e resultado observado. Teste automatizado, build, HTTP
200, renderização Web, SITL, heartbeat físico, upload e voo são evidências diferentes.

### Resumo em 21/08/2026

| Integração | Implementação | Evidência executada | Estado honesto |
|---|---|---|---|
| PostgreSQL/PostGIS + Alembic | sim | source head `0007_vehicle_arm_command` com roundtrip temporário; último PostgreSQL vivo observado em `0006_mission_start_health` | banco vivo preservado e sem upgrade nesta rodada; pedidos controlados não foram alterados |
| FastAPI | sim | Ruff/format e 56 testes aprovados; 1 opt-in ignorado | warning conhecido Starlette/httpx; nenhum deploy/runtime HTTP novo nesta rodada |
| admin React | sim | ESLint, 20 arquivos/112 testes e build Vite aprovados | warning de chunk >500 kB; novo smoke visual não foi possível |
| Flutter Android/Web | uma base `mobile/` | Flutter 3.47.0/Dart 3.13.0 stable: format 90, analyze e 98 testes; Web release, Wasm dry run e APK debug | CORS integrado e catálogo API foram validados; ainda não prova UI visual, GPS nem aparelho |
| MapTiler/MapLibre | estilo híbrido, busca/reverse e mapas Flutter/admin | style 200, JSON GL v8 `Satellite Hybrid`, 40 camadas; reverse geocode 200/10 resultados | chave exposta precisa ser rotacionada; resposta HTTP não prova mapa renderizado |
| CORS/CSP/worker admin | configuração explícita | preflight Flutter 200; CSP, nosniff, DENY, Referrer-Policy; worker 200 `application/javascript`, 470.280 bytes | headers/MIME não provam renderização do mapa |
| gateway `simulation`/Pymavlink | sim | Ruff/format e 85 testes com doubles | imagem Docker não foi reconstruída; doubles não provam SITL nem hardware |
| protocolo de missão | ACK, releitura, journal e estados `UPLOADED`/`VERIFIED` | testes automatizados | nenhum upload/releitura foi enviado à Pixhawk |
| comandos operacionais | ARM normal dedicado, `START`, `PAUSE`, `CONTINUE`, RTL e ABORT persistidos/ACK-aware | backend, gateway e admin testados | nenhum desses comandos foi enviado ao hardware nesta revisão; gates locais estão falsos |
| conexão serial direta | sim | COM7/57600, ArduCopter 4.6.3/Pixhawk 6C, `sysid=1`, `compid=1`; cinco minutos receive-only | `STABILIZE`, `armed=false`; confirmou link e telemetria, não prontidão ou voo |
| gateway real → backend/admin | sim | 129 snapshots `HARDWARE_REAL`; REST e WS observaram dados reais; após parar, `is_stale=true` | nenhuma escrita MAVLink, claim, missão ou comando ocorreu |
| saúde física observada | sim, conservadora | bateria 74–75%; GPS chegou a fix 3/5 sats e terminou fix 1/0; EKF/preflight falsos; home/origin ausentes | `NO-GO`; todos os gates locais permaneceram falsos |
| forwarding Mission Planner | sim em código/documentação | UDP 14551 estava como Inbound; diagnóstico expirou sem heartbeat | forward E2E não comprovado; configurar Mavlink Mirror UDP Client/write off |
| SITL | preparado | WSL possui somente `docker-desktop`; ArduPilot/MAVProxy ausentes | não executado |
| upload, ARM pelo novo admin, motores, voo e entrega | não executados nesta rodada | somente testes/doubles; relatos de armamento por outro GCS não validam este botão | não validados em hardware pelo fluxo novo |

`UPLOADED` registra o ACK do protocolo de missão. Só a releitura e comparação integral publicam
`VERIFIED`. Esse estado aguarda uma solicitação explícita de ARM normal ou armamento externo e um
`START` separado. O ARM administrativo exige `ALLOW_VEHICLE_ARM=true`,
`ALLOW_FLIGHT_COMMANDS=true`, `ALLOW_MISSION_START=true`, preflight completo e confirmação por ACK
e heartbeat posterior. O início permanece separado e nunca arma implicitamente.
`PAUSE` e `CONTINUE` exigem o gate geral de comandos e ACK do autopiloto.

## Matriz final literal de evidência

| Item solicitado | Resultado em 21/08/2026 | Limite |
|---|---|---|
| IMPLEMENTADO | **SIM** | código, contratos, builds e configuração presentes |
| TESTADO UNITARIAMENTE | **SIM** | 351 testes automatizados aprovados; 1 opt-in ignorado |
| TESTADO COM MOCK MAVLINK | **SIM** | doubles determinísticos; não representam socket/hardware |
| TESTADO COM SITL | **NÃO FOI POSSÍVEL** | somente `docker-desktop` no WSL; ArduPilot/MAVProxy ausentes |
| TESTADO COM MISSION PLANNER | **NÃO** | forwarding E2E falhou: configuração Inbound não encaminhou heartbeat ao gateway |
| TESTADO COM PIXHAWK COM7 | **SIM** | modo passivo/direct, receive-only; nenhum byte MAVLink de escrita |
| TESTADO COM TELEMETRIA REAL | **SIM** | não preflight-ready: GPS degradou; EKF/preflight falsos; home/origin ausentes |
| TESTADO UPLOAD DE MISSÃO | **NÃO** | gate falso; nenhum upload/releitura real |
| TESTADO COM MOTORES DESARMADOS | **NÃO** | nenhum ensaio de motor; somente `armed=false` foi observado passivamente |
| TESTADO EM VOO | **NÃO** | nenhum armamento, decolagem ou voo |

## Ambiente local executado

| Superfície | Endereço/estado |
|---|---|
| admin | `http://localhost:5173`, container healthy |
| API | `http://localhost:8000`, container healthy |
| OpenAPI | `http://localhost:8000/docs` |
| Flutter Web | `http://localhost:5174`, build release servido por HTTP |
| PostgreSQL | `127.0.0.1:5432`, container healthy |
| gateway container | imagem reconstruída; container novo em `Created`/parado, `simulation`, gates falsos |
| gateway físico | processo host parado após o ensaio direto passivo; snapshot final stale |

O launcher `scripts/start_development.ps1` passou no parser Windows PowerShell 5.1 e em
`-ValidateOnly`, tanto sem gateway quanto com simulação confirmada em porta livre 5199; omitir a
confirmação foi recusado. Esses checks não iniciaram serviços.

O controlador visual integrado retornou uma lista vazia de navegadores. Foram verificados
listeners, respostas HTTP e assets, mas não houve novo smoke visual, inspeção de console ou
validação de tiles renderizados nesta rodada. A validação MapLibre/MapTiler no Chrome de 7 de
agosto continua evidência histórica; não deve ser apresentada como repetida agora.

No admin, a resposta da raiz inclui CSP, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` e `Referrer-Policy`; o worker MapLibre respondeu 200 como
`application/javascript` com 470.280 bytes. O WebSocket do admin recebeu
`operations.connected`. Esses checks validam entrega/protocolo, não renderização.

O login administrativo foi repetido com a senha atual do `.env` e continuou retornando 401; a
conta não foi redefinida nem rotacionada. Um JWT efêmero de cliente foi usado somente para validar
REST/CORS: o preflight retornou 200 com origem exata e métodos `GET`, `POST`, `PATCH`, `DELETE` e
`OPTIONS`, uma chamada sem token retornou 401
e `GET /api/v1/products` autenticado retornou quatro produtos. A inspeção preservou três pedidos,
sendo dois pendentes e um `COMPLETED` histórico de simulação.

## Dependências do desktop

| Ferramenta | Versão observada |
|---|---|
| Docker Desktop | 4.86.0 |
| Docker Engine/CLI | 29.7.2 |
| Node.js / npm | 24.19.0 / 11.17.0 |
| Python | 3.13.15 |
| Git for Windows | 2.55.0.windows.3 |
| Flutter / Dart / DevTools globais | 3.47.0 / 3.13.0 / 2.60.0 |
| Android Studio | 2026.1.3, build `AI-261.26222.65.2613.15948027` |
| Android build | API 37, AGP 9.1.1, Gradle 9.3.1 |

O Android Studio não foi atualizado automaticamente pelo `winget`, que informa que o pacote deve
ser atualizado pelo próprio editor. `flutter doctor` ainda aponta command-line tools/licenças do
Android não confirmadas e Visual Studio ausente; isso não impediu os builds Android/Web executados.
Licenças não foram aceitas em nome do usuário.

Foram detectadas atualizações de Docker Desktop 4.87, WSL 2.7.12, VS Code e Java, mas nenhuma foi
aplicada automaticamente. Docker Scout exigiu login e, por isso, não integra a evidência de audit.

Há dois SDKs Flutter no computador, mas os scripts não preferem mais silenciosamente o checkout
interno. A resolução agora segue `-FlutterSdkRoot` → `FLUTTER_ROOT` → `PATH`; o uso de
`./flutter` exige `-AllowBundledFlutterSdk`. O resolvedor valida canal `stable`, Flutter 3.47.x,
Dart 3.13.x e origem comum dos executáveis. O SDK oficial 3.47.0/3.13.0 foi aceito e o fork
pré-release 3.47.0-1.0.pre-84/3.12.2 foi corretamente rejeitado.

## Imagens Docker

| Imagem | Digest observado |
|---|---|
| `postgis/postgis:17-3.5` | `sha256:83e9999dc3ad8390c210e76130c3a16365ef4f957bb55200d22b7937cfbcb321` |
| `python:3.13-slim` | `sha256:ffb752e139c0a19692a43af8d8523b274222dd68eebad5d583b45c2201c6e30a` |
| `node:24-alpine` | `sha256:d32cdf619f63fe0471182d08996dd516c6275bb5fd31ae06e55a570bd9e1ad43` |
| `nginx:1.28.3-alpine` | `sha256:a8b39bd9cf0f83869a2162827a0caf6137ddf759d50a171451b335cecc87d236` |

Backend, admin e gateway foram reconstruídos com `--pull` e essas tags. Os IDs locais finais das imagens
da aplicação começam por `220aaddad0` (backend, 11:32:27Z), `0f8c4855` (admin, 11:32:28Z) e
`85340a31ab` (gateway, 11:32:28Z). O container do gateway foi recriado e permanece em
`Created`/parado, com o volume persistente
preservado. Os digests e IDs são a fotografia local da rodada e podem mudar após novo build ou
quando uma tag mutável for publicada novamente.

## Qualidade, auditorias e artefatos

- backend: 56 testes aprovados e 1 opt-in ignorado; Ruff e format aprovados;
- gateway: 85 testes aprovados; Ruff e format aprovados;
- admin: 20 arquivos/112 testes aprovados, ESLint e build Vite aprovados;
- Flutter: 98/98 testes aprovados com SDK oficial global stable Flutter 3.47.0/Dart 3.13.0;
  format verificou 90 arquivos/0 mudanças, analyze terminou sem issues, Web release e dry run
  Wasm foram aprovados;
- total: **351 testes automatizados aprovados**, mais 1 opt-in ignorado; a bateria orquestrada
  final terminou com exit 0 e selecionou o SDK oficial stable;
- `npm audit`, completo e de produção: zero vulnerabilidades conhecidas; `npm ci --dry-run` e
  `npm ls` aprovados;
- `pip check` e `pip-audit` do backend e gateway, tanto nos venvs quanto nas imagens finais:
  zero incompatibilidades/vulnerabilidades conhecidas.

O único arquivo mobile alterado pelas atualizações foi `mobile/pubspec.lock`: MapLibre direto
0.26.2, mais archive 4.1.0, code_assets 2.0.0, dbus 0.7.15, hooks 2.2.0, image 4.9.2,
objective_c 9.6.0, record_use 1.1.1 e vm_service 15.3.0. SHA-256 do lock:
`A11E35E0E411D5B7BD81E81B6F66E222134C504230D187847AB086C6FB5C3EC5`.

Artefatos atuais:

- Flutter Web integrado (`DEMO_MODE=false`, MapTiler configurado pelo `.env` ignorado):
  40 arquivos/43.303.798 bytes, tree manifest SHA-256
  `C7D6B483141E6CDA9B6AEC883E68BF5F9C6948B9EF355B0DE68BC4199B0322CD`;
- `main.dart.js`: 3.592.748 bytes, SHA-256
  `951B3E50A11620B19A655571D6491C20CC781A77AE44E09D6457A56FA9D856CE`;
- APK debug do mesmo perfil: 195.252.860 bytes, SHA-256
  `0D1F104AB2D22605F901E7588B8DF16CF159D1149CE9F2F1880DDAA1F482B9F6`;
- APK release assinado: não existe; keystore privado ainda é necessário.

O pacote `maplibre_gl` 0.27.0 foi publicado em 19 de agosto, mas não foi adotado nesta rodada: ele
muda o runtime Web para GL JS 6/WebGL2 e o ciclo de vida Android, e não havia navegador integrado
nem dispositivo Android para a validação necessária. A versão 0.26.2 aprovada ainda emite avisos
de Kotlin Gradle Plugin legado, Java 8 source/target e APIs de plugins. Atualizações major
adicionais não foram aplicadas sem migração dedicada.

## Segurança e preservação de dados

O `.env` local mantém:

```env
REAL_HARDWARE_ACKNOWLEDGED=false
ALLOW_MISSION_UPLOAD=false
ALLOW_FLIGHT_COMMANDS=false
ALLOW_MISSION_START=false
ALLOW_VEHICLE_ARM=false
```

O container foi inspecionado separadamente com `GATEWAY_RUNTIME=container`, modo `simulation` e
`udp:0.0.0.0:14550`; configurações reais são recusadas nesse runtime.

Nenhuma chave, senha ou token é reproduzido aqui. As três variáveis MapTiler estão presentes, mas
compartilham hoje o mesmo valor exposto; crie três chaves separadas/restritas, substitua-as no
`.env` ignorado, refaça builds/testes e só então revogue a antiga.

Os dois pedidos `PENDING_ADMIN_APPROVAL` são evidência de teste. **Não aprovar, não preparar,
não autorizar, não reivindicar e não despachar.** O backup pré-integração do banco foi mantido fora
do repositório; nenhum volume/container de dados foi apagado.

## Próximas ações manuais

1. Para novo ensaio `direct`, confirmar `COM7` no Gerenciador de Dispositivos, fechar/desconectar
   completamente o Mission Planner e executar somente
   `scripts\start_gateway.ps1 -DiagnoseOnly`.
2. Para forwarding, manter o Mission Planner como dono da COM7/57600, desabilitar o AutoConnect
   UDP 14551 **Inbound**, configurar `Mavlink Mirror` como UDP Client para `127.0.0.1:14551`, deixar
   **Write access** desligado e repetir o diagnóstico passivo.
3. Instalar Ubuntu/ArduPilot no WSL 2 e executar SITL antes de qualquer upload físico.
4. Obter a senha administrativa persistida ou autorização explícita para rotacioná-la; só então
   repetir o smoke autenticado somente leitura.
5. Rotacionar a credencial MapTiler exposta e repetir Web/admin/Android separadamente.
6. Encerrar e reautenticar, ou revogar, a sessão externa aeronáutica cujo token em cache foi
   identificado durante a inspeção; nenhum valor da credencial foi registrado aqui.

Nenhum próximo passo deve habilitar upload, comandos ou início antes de heartbeat/telemetria
atuais, SITL, revisão de missão, checklist e autorização operacional específicos.
