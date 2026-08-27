# Plano de testes e evidências

## Camadas

1. **Unitário:** domínio, schemas, widgets/componentes e gateway fake; sem hardware.
2. **Integração local:** FastAPI + PostGIS, contratos frontend, WebSocket e exportador.
3. **Sistema `simulation`:** fluxo cliente → admin → gateway determinístico.
4. **SITL:** MAVLink real contra ArduPilot virtual.
5. **Bancada Pixhawk:** manual, inicialmente sem hélices.
6. **Voo controlado:** progressão manual com critérios e evidência.

Teste em camada inferior não comprova camada superior.

## Backend

Cobrir cadastro/login/RBAC, propriedade, pontos válidos/inválidos inclusive coordenada mundial distante que chega a `PENDING_ADMIN_APPROVAL`, PostGIS, dinheiro, submit/cancel, exclusão de `DRAFT` da listagem, listagem própria paginada, grupos active/history, ordenação, detalhe estrangeiro `404`, itens/valores/ponto/imagem opcional, milestones sanitizados, approve/reject/motivo, missão/versionamento/exportação/revisão, autorização separada/TTL/uso único/idempotência, persistência do registro de autorização após reload/claim, ARM dedicado/payload estrito/gates/ACK + heartbeat, snapshot vencido/incompleto, telemetria antiga/provenance, WebSocket próprio/estrangeiro e erros. Para localizações salvas, cobrir lista vazia, primeira/segunda/terceira criação, quarta recusada, CRUD próprio, recurso alheio não enumerável, nome 1–40, endereço ausente, coordenadas inválidas, `user_id` sem autoridade, provider/tipo e quatro flags persistidos, rejeição de confirmação falsa ou tipo inválido, confirmação atual no pedido e cópia fiel para `DeliveryPoint`.

Em PostgreSQL isolado, executar `upgrade`, `alembic check`, `downgrade` e novo `upgrade`. O limite de três exige ainda teste paralelo com sessões/conexões independentes: ambas as requisições devem passar pelo `FOR NO KEY UPDATE` da linha do usuário e o estado final nunca pode exceder três. SQLite em memória não comprova esse lock. Nunca testar downgrade destrutivo no banco do usuário sem backup.

## Mobile

Cobrir formulários, restauração/expiração da sessão, catálogo/carrinho, responsividade, busca/sem resultado, abertura direta sem endereço/GPS, MapLibre/pino central/coordenadas mundiais, confirmação de área, pagamento sem dado bancário, submit, lista/histórico/filtros/paginação, card/título/ID curto/status, detalhe completo, timeline simplificada, estado vazio/erro/offline, atualização WebSocket, reconexão, polling e refresh manual. Para localizações salvas, cobrir item `Minhas localizações` na Conta, listas com 0/1/2/3 registros reais, contador, adicionar/limite, criar/editar/excluir, loading/success/empty/limit/error/offline, picker no checkout, somente itens existentes, revisão no mesmo mapa, captura real de provider/tipo/flags, reinício das duas confirmações atuais, payload condicional do pedido, ajuste sem atualizar o atalho e ausência de cards fictícios. MapTiler real requer testes separados com chave restrita e aparelho/navegador.

## Admin

Cobrir proteção de rota, fila/vazio/erro, detalhe/mapa, configuração MapTiler, loading/timeout/erro/retry/fallback, rota/marcadores/fit bounds, atribuição/logo, approve/reject, export/revisão, health stale/UNKNOWN/null, os quatro gates independentes, checks automáticos `PASS/WARNING/BLOCKING`, exatamente três confirmações humanas da autorização, ausência da frase, modal final, warning não bloqueante, blocker impeditivo, idempotência/duplo clique, WebSocket/ACK/reconexão/coalescência, alertas/dedupe/cooldown, ARM dedicado, `START`/`PAUSE`/`CONTINUE`, RTL e abortamento.

## MapTiler e MapLibre

- backend: contrato interno, URL externa codificada, ordem longitude/latitude, `language`, `limit`, `autocomplete`, país opcional e parser GeoJSON;
- segurança: chave de servidor ausente dos DTOs/erros/logs; chaves Web/Android separadas; estilo sem `?key=` no arquivo;
- erros: chave ausente, 403, 429, timeout, falha de rede, JSON/GeoJSON inválido, zero features e retry sem sucesso falso;
- Flutter Web: estilo/tiles, eventos de câmera, pino central, CORS, origem autorizada, atribuição/logo e fallback com `-WithoutMapTiler`;
- Android: mapa no emulador/aparelho, geolocalização, `User-Agent` observado e chave Android restrita;
- admin: MapLibre GL JS, estilo híbrido, rota/pontos, zoom/fit bounds, CSP/worker e fallback.
- localização salva: abrir o mesmo mapa com centro inicial e provider/tipo salvos, revisar sem conclusão instantânea, registrar as quatro flags reais ao criar/editar, renovar revisão/área segura no pedido, ajustar somente o snapshot e reutilizar o fluxo nos modos criar/editar;

HTTP 200 do estilo ou da Geocoding API não prova renderização em browser/Android. Um build aprovado também não prova acesso a tiles, atribuição visível ou restrição correta da chave.

## Localizações salvas e snapshot — cenários planejados

Backend/API:

- usuário sem localizações; criar primeira, segunda e terceira; impedir quarta com `409/SAVED_LOCATION_LIMIT_REACHED`; repetir `Idempotency-Key` sem duplicar nem consumir outra vaga;
- listar somente próprias; ler/editar/excluir própria; impedir leitura, edição, exclusão e uso de outra;
- aceitar local sem endereço; persistir e devolver `map_provider`, `map_type` e as quatro flags; rejeitar nome vazio/maior que 40, coordenadas fora da faixa, `map_type` fora de `hybrid|satellite` e qualquer confirmação ausente ou falsa na criação;
- ignorar/rejeitar `user_id` externo sem mudar o proprietário derivado do JWT;
- `OrderCreate` rejeitar ambos/nenhum identificador; no caminho salvo, rejeitar revisão ou área segura ausente/falsa e aceitar somente os dois booleanos atuais verdadeiros;
- criar uma `SavedLocation` com provider/tipo identificáveis — incluindo caso `satellite` — e comprovar que o `DeliveryPoint` com `SAVED_POINT` copia esses valores e registra as confirmações atuais, sem substituí-los por defaults;
- editar e excluir `SavedLocation` depois do pedido e comprovar que o detalhe, a missão e o destino histórico continuam iguais;
- executar criações concorrentes contra PostgreSQL isolado e comprovar o lock por usuário e o total final máximo de três.

Flutter/widget/repository:

- Conta abre a tela correta; 0/1/2/3 cards e contador são dinâmicos; adicionar desabilita no limite;
- criar, editar e excluir atualizam a lista canônica; modal de exclusão permite cancelar; erro/offline oferece retry e não inventa dados;
- picker mostra somente localizações existentes, abre MapLibre/MapTiler com provider/tipo coerentes, limpa as confirmações atuais, exige nova revisão/área segura e permite ajustar sem alterar a salva;
- pedido funciona sem salvar; salvamento posterior funciona quando escolhido; recusa, offline, falha e limite três preservam o pedido criado;
- executar a mesma base em Flutter Web e Android, separando widget/build de smoke real de browser/emulador/aparelho.

Esses cenários são requisitos de validação e não integram a evidência acumulada nem suas contagens até que os comandos correspondentes terminem com sucesso e o resultado seja registrado.

## Gateway

Cobrir configuração segura, fake, heartbeat, normalização, preflight, rejeição de missão acima de `MAX_MISSION_DISTANCE_M`, timeout, claim concorrente, autorização expirada, hash/versão, upload ACK/erro, releitura e `VERIFIED`, mensagens de outro `sysid/compid`, versão do autopiloto, taxas de stream, telemetria ausente, reconexão, journal, idade de comando, gates independentes, ARM, `START`, `PAUSE`, `CONTINUE`, abortamento e RTL. Confirmar que `START` não arma, exige identidade/frescor/link, veículo já armado e os gates locais; `CONTINUE` só é aceito após `PAUSED`; e falha HTTP depois de `PAUSE`/`CONTINUE` confirmado é reconciliada sem reenviar o comando físico.

Os testes Pymavlink usam conexão controlada em memória. Eles não abrem serial/UDP, não executam SITL e não se conectam a hardware.

## ARM normal — cenários planejados

Backend/API:

- recusar não `ADMIN`, rota genérica `/commands/ARM`, missão diferente de `VERIFIED`, missão sem claim/veículo ou gateway divergente;
- exigir `Idempotency-Key`, `reason` válido e exatamente `area_clear_confirmed=true`, `operator_present_confirmed=true` e `safety_switch_ready_confirmed=true`; rejeitar campo extra, falso e qualquer forma de force/bypass;
- recusar `SIMULATION`, `UNKNOWN`, snapshot stale/incompleto, `armed=true`, modo diferente de `STABILIZE`, cada falha de GPS/EKF/bateria/home/geofence/RTL/preflight e cada gate falso ou nulo;
- repetir chave/corpo sem duplicar, conflitar chave/corpo diferente e serializar concorrência para manter no máximo um comando crítico aberto;
- rejeitar primeiro ACK de gateway diferente, conclusão sem `ACKNOWLEDGED` e `COMPLETED` sem heartbeat posterior fresco do mesmo veículo, origem permitida e `armed=true`;
- validar migração a partir do head anterior, coluna `vehicle_arm_enabled`, largura do enum de comando e roundtrip isolado de upgrade/downgrade/upgrade.

Admin:

- esconder/desabilitar a ação e explicar cada blocker de missão, claim, identidade, origem, staleness, health/preflight, modo, estado armado e gates;
- mostrar resumo operacional, motivo e confirmações presenciais; exigir hold de dois segundos e não oferecer force/bypass;
- conservar a mesma idempotency key após resposta ambígua, tratar `202` como pendente e só indicar armamento quando o snapshot canônico novo/fresco trouxer `armed=true`;
- após timeout/erro, não apresentar sucesso nem reenviar automaticamente; manter `START` bloqueado até a confirmação física.

Gateway/adaptador:

- provar defaults falsos e exigir simultaneamente `ALLOW_VEHICLE_ARM`, `ALLOW_FLIGHT_COMMANDS` e `ALLOW_MISSION_START`, além do reconhecimento explícito em hardware real;
- recusar comando vencido, missão/veículo/gateway/fase divergente, origem inválida, heartbeat/health/preflight incompleto e modo diferente de `STABILIZE` sem transmitir; se o veículo armou depois do request, reconciliar o `PENDING` sem nova escrita;
- verificar uma única transação normal `MAV_CMD_COMPONENT_ARM_DISARM` com `param1=1`, `param2=0`, demais parâmetros zero e ACK estritamente correlacionado; cobrir `IN_PROGRESS`, aceite final, rejeição e timeout;
- exigir heartbeat posterior com `armed=true`, publicar o health antes de `COMPLETED` e comprovar que ARM não chama `START` nem muda a missão para execução;
- reconciliar `PENDING` já armado sem escrita; após restart, concluir `ACKNOWLEDGED` apenas com heartbeat armado e falhar resultado falso/nulo como incerto, sem reenvio; desarmamento nunca aciona rearmamento.

Esses cenários são requisitos de validação. Não entram nas evidências ou contagens datadas abaixo até que cada comando correspondente termine com sucesso no ambiente declarado.

## SITL

Registrar versão ArduPilot, comando, parâmetros não sensíveis e logs. Cenários: heartbeat, upload curto, ARM normal deliberado, confirmação por ACK + heartbeat, `START` separado, chegada, retorno, perda de link, bateria/falha simulada, upload incorreto, abort/RTL e reconciliação sem rearmamento. Rodar antes de Pixhawk.

## Hardware e voo

Registrar data, local controlado, operador, hardware/firmware, checklist, missão/hash, logs Mission Planner/TLOG/dataflash e resultado real. Progressão: comunicação → sensores → upload desarmado → ARM normal e motores sem hélices → desarmamento/intervenção → voo manual → missão curta sem carga → RTL → carga leve/mecanismo → entrega e retorno. Nunca pular SITL nem tratar teste automatizado como autorização para hardware.

## Evidência atual — 21 de agosto de 2026

| Evidência executada | Resultado | Limite honesto |
|---|---|---|
| suíte unificada | exit 0; backend 56, gateway 85, admin 112 e Flutter 98: **351 aprovados + 1 opt-in ignorado** | o skip PostgreSQL depende de ambiente opt-in; warning Starlette/httpx permanece |
| qualidade | Ruff/format backend/gateway, ESLint, Flutter format 90/analyze e Compose config aprovados | análise estática não comprova runtime externo |
| dependências | `pip check`/`pip-audit` em venvs e imagens: zero; `npm audit` full/prod: zero; `npm ci --dry-run`/`npm ls` OK | fotografia datada de 20/08 |
| builds | Docker `--pull`, Vite, Flutter Web release, Wasm dry run e APK debug integrado aprovados | build não prova renderização visual, dispositivo ou voo |
| HTTP/WebSocket | backend/admin/Flutter Web 200; CORS exato; catálogo retornou 4 produtos; WS `operations.connected` | JWTs efêmeros apenas; login admin atual seguiu 401 |
| MapTiler | style 200 GL v8/40 camadas; reverse geocode 200/10 resultados | HTTP não prova mapa renderizado nem tiles completos |
| serial direta passiva | cinco minutos COM7/57600, 129 snapshots reais, sys/component 1/1, `STABILIZE`, `armed=false` | receive-only; nenhum comando ou ACK operacional |
| telemetria real | bateria 74–75%; GPS chegou fix 3/5 sats e terminou fix 1/0; REST/WS e staleness comprovados | EKF/preflight falsos; home/origin ausentes; `NO-GO` |
| Mission Planner forwarding | UDP 14551 Inbound; diagnóstico expirou sem heartbeat | E2E não comprovado; requer Mavlink Mirror UDP Client/write off |
| SITL | ambiente inspecionado | impossível nesta máquina: apenas `docker-desktop`, sem ArduPilot/MAVProxy |
| upload, motor e voo | não executados; gates falsos | observar `armed=false` não é ensaio de motor |

O source head passou a `0007_vehicle_arm_command` e o roundtrip foi executado apenas em banco
temporário. O PostgreSQL vivo permaneceu no último snapshot em Alembic `0006`, com 1 pedido `COMPLETED`, 2
`PENDING_ADMIN_APPROVAL`, nenhum comando de gateway e 34.179 snapshots. **Não aprovar, preparar,
autorizar, reivindicar ou despachar** os dois pedidos pendentes.

O controlador visual integrado não encontrou navegador, portanto nenhum HTTP 200, bundle, worker
ou resposta MapTiler foi convertido em alegação de smoke visual. O login admin foi tentado e
retornou 401; a conta não foi redefinida.

Após a atualização compatível do lock, o rerun Flutter preservou os 98 testes. O Web release tem
40 arquivos/43.303.798 bytes, tree manifest SHA-256
`C7D6B483141E6CDA9B6AEC883E68BF5F9C6948B9EF355B0DE68BC4199B0322CD`; o APK debug tem
195.252.860 bytes, SHA-256
`0D1F104AB2D22605F901E7588B8DF16CF159D1149CE9F2F1880DDAA1F482B9F6`.

## Evidência histórica — 17 de agosto de 2026

| Evidência executada | Resultado | Limite honesto |
|---|---|---|
| backend | Ruff/format e 53 testes aprovados; 1 opt-in ignorado; `pip-audit` limpo | warning Starlette/httpx; audit precisou de UTF-8 explícito por causa do caminho com acento |
| gateway | Ruff/format e 57 testes aprovados | doubles não provam socket, SITL ou hardware |
| admin | ESLint, 16 arquivos/67 testes e build Vite aprovados | aviso de chunk acima de 500 kB; controlador visual do navegador indisponível |
| Flutter | SDK oficial global stable 3.47.0: format 90 arquivos/0 mudanças, analyze sem issues e 98/98 testes; Web release, dry run Wasm e APK debug aprovados | HTTP/build não comprovam UI, tiles, GPS ou aparelho nesta rodada |
| Docker | imagens backend/admin/gateway construídas; DB/API/admin healthy | gateway físico parado intencionalmente |
| migração | `0006_mission_start_health` aplicada ao PostgreSQL real; head único e roundtrip SQLite aprovados | downgrade não executado no banco do usuário |
| serial direta passiva, evidência anterior da mesma sessão | heartbeat real recebido duas vezes em COM7/57600: system/component 1/1, `STABILIZE`, desarmado | GPS, bateria, EKF, home, upload e comandos não foram obtidos/enviados |
| gateway real limitado → backend | sete heartbeats normalizados aceitos com HTTP 200 em 15 s | não havia missão elegível nem comandos; nenhuma escrita MAVLink foi habilitada |
| estado físico final | COM7 deixou de ser enumerada; snapshot persistido ficou offline/`ERROR`, com três gates falsos | era o estado daquela fotografia; foi superado pela sessão direta de 20/08 |
| Mission Planner forwarding | listener Inbound conflitante identificado; diagnóstico UDP sem heartbeat | Mavlink Mirror ainda não foi validado |
| SITL, upload, armamento, motor, voo | não executados | permanecem pendentes e separados |

Total daquela fotografia: **275 testes automatizados aprovados**, mais 1 opt-in ignorado. O rerun
orquestrado terminou com exit 0 em 107,5 s, usando seleção explícita do SDK oficial stable. O APK
debug integrado daquela rodada, regenerado com `DEMO_MODE=false` e a configuração MapTiler do `.env`
ignorado, possui 195.236.488 bytes e SHA-256
`202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`.

O banco preserva dois pedidos de teste em `PENDING_ADMIN_APPROVAL`; **não aprovar, preparar,
autorizar, reivindicar ou despachar**. O login administrativo não foi usado no smoke final porque
a senha do `.env` diverge do hash persistido. Isso não torna o banco vazio. O navegador visual
estava indisponível, então listener e HTTP 200 não foram registrados como smoke de UI.

## Evidência da entrega de localizações salvas — 2026-08-09

| Evidência executada | Resultado | Limite honesto |
|---|---|---|
| backend completo | Ruff e format aprovados; 51 testes aprovados e 1 opt-in ignorado no comando comum | aviso conhecido de depreciação Starlette/httpx |
| PostgreSQL/PostGIS isolado | `upgrade`, `alembic check`, teste concorrente opt-in, `downgrade` para `0003` e novo `upgrade` aprovados em banco temporário descartado | avisos informativos de reflexão `geography`; não usou banco do usuário |
| Flutter | `dart format`, `flutter analyze` sem issues e 87 testes aprovados | testes host/widget não substituem tiles reais nem aparelho físico |
| Flutter Web | build release aprovado, inclusive dry run Wasm; servidor local respondeu 200 e Chrome 151 renderizou visualmente a tela de login em 1440×1000 | controlador interativo do navegador estava indisponível; CRUD Web e MapTiler real não foram exercitados |
| Android | o smoke da funcionalidade, antes do endurecimento final da corrida de sessão, percorreu login demo, Conta, vazio `0 de 3`, fluxo manual, ajuste acessível, confirmação segura e CRUD criar/renomear/excluir em Android 15/API 35 x86_64, sem erro fatal/Unhandled do app. O APK final foi recompilado, instalado e renderizou o login no mesmo AVD | ao tentar repetir a transição para Home com o APK final, o processo do host `qemu-system-x86_64-headless.exe` caiu duas vezes com `APPCRASH c0000005`, inclusive com GPU desligada; portanto o CRUD final não foi reexecutado. O smoke usou mapa local honesto, não tiles/GPS reais nem aparelho físico |

O smoke Android inicial confirmou que o ajuste por `Norte` muda a coordenada e libera a continuação, que a confirmação de área segura habilita o CTA e que criar `Casa`, renomear para `Casa2` e excluir retorna de `1 de 3` a `0 de 3`. O APK instalado nessa rodada tinha 214.464.266 bytes e SHA-256 `3634403478A01AB9E90C8846D3BFCBC243C0A036F03AFB67FCD4786890BF83C9`. Após a regressão final da fila da câmera, `mobile/build/app/outputs/flutter-apk/app-debug.apk` foi regenerado com 214.465.272 bytes e SHA-256 `41A6BA275CF91B67FB246275089613C4F2E9D562CAD6DD731E517B49EE3F5055`; essa última variante não foi reinstalada porque os reruns passaram a encerrar o processo hospedeiro do emulador. A falha foi registrada pelo Windows Error Reporting em `qemu-system-x86_64-headless.exe`, não pelo log do Flutter.

A fila dos movimentos programáticos da câmera ganhou regressões para três sequências rápidas: retorno ao alvo ainda ativo, retorno ao alvo já aplicado e substituição de múltiplos alvos pendentes. Assim, o último ponto selecionado continua sendo o ponto mostrado pelo mapa após os movimentos assíncronos terminarem.

Essa evidência é adicional e específica desta entrega; não reescreve as contagens históricas abaixo nem comprova MapTiler com chave restrita, geolocalização real, SITL, Pixhawk ou voo.

## Evidência histórica preservada — 2026-08-08

| Evidência | Estado comprovado | Limite |
|---|---|---|
| backend | Ruff/format e 33 testes | aviso de depreciação Starlette/httpx; concorrência real de `Idempotency-Key` no PostgreSQL não foi ensaiada em paralelo |
| gateway | Ruff/format e 31 testes | doubles; sem socket/SITL/hardware |
| admin | ESLint, 57 testes e build Vite | smoke visual do novo modal não executado: navegador/controlador visual indisponíveis nesta sessão |
| Flutter | format/analyze, 52 testes, build Web e APK debug | smoke visual de Meus Pedidos não executado; APK não instalado; geolocalização concedida/timeout não exercitados |
| migrations/PostGIS | head, sem drift, ciclo upgrade/downgrade aprovado em banco temporário | avisos informativos de reflexão `geography` |
| Docker | imagens atualizadas; API/admin/DB healthy; gateway ativo; HTTP 200 nas portas 5173, 5174 e 8000 | ambiente local, não produção |
| integração gateway/backend | cadastro, checkout, aprovação, missão, revisão, autorização com três confirmações, execução simulada e pedido/missão `COMPLETED`; 13 eventos e 5 telemetrias | simulação não comprova entrega física |
| MapTiler HTTP direto | estilo 200 (GL v8/40 layers), pesquisa 200 (3 features neste ensaio) e reverse 200 (1 feature) | a chave usada foi exposta e deve ser rotacionada |
| MapLibre Web | estilo/tiles/fontes/sprites 200, câmera inicial/zoom, arraste, busca/reverse, logo/atribuição e checkout confirmados no Chrome | chave temporária exposta; restrição de origem ainda não provada |
| MapLibre Android e GPS | APK debug compilado; no Web, estado de permissão bloqueada tratado sem impedir o mapa manual | exigem emulador/aparelho e matriz concedida/negada/timeout |
| auditoria Python | `PYSEC-2026-1845` encontrado no pytest 8.4.2; constraints de desenvolvimento atualizadas para `pytest>=9.0.3,<10`; suítes backend/gateway passaram e `pip-audit` final retornou zero vulnerabilidades conhecidas | risco era médio, ligado a `tmpdir` UNIX; repetir após alterar constraints/lock |
| auditoria npm de produção | zero vulnerabilidades conhecidas | fotografia de 2026-08-07; repetir antes de publicar |
| SITL/Mission Planner/Pixhawk/voo | não validado | exige evidência separada |

Total histórico daquela bateria: **173 testes automatizados aprovados**. O hash e o tamanho do APK registrados nessa seção foram superados pelo artefato atual descrito acima. A instalação em emulador/aparelho e a assinatura release continuam sem revalidação nesta rodada.

## Comandos

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 `
  -SkipBuilds `
  -FlutterSdkRoot '<CAMINHO_SDK_FLUTTER_OFICIAL>'
docker compose --profile gateway config --quiet
docker compose --profile gateway up -d --build
docker compose exec -T backend alembic check
```

Depois de trocar todos os placeholders locais e rotacionar a conta existente:

```powershell
$env:ADMIN_INITIAL_PASSWORD='SENHA_LOCAL_ROTACIONADA'
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\integration_smoke.ps1 `
  -ConfirmSimulationMutation
```

O smoke cria registros identificados no banco local. Execute somente em loopback/simulação. Não registre um comando como aprovado se ele não terminou com exit code zero.
