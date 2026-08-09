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

Cobrir cadastro/login/RBAC, propriedade, pontos válidos/inválidos inclusive coordenada mundial distante que chega a `PENDING_ADMIN_APPROVAL`, PostGIS, dinheiro, submit/cancel, exclusão de `DRAFT` da listagem, listagem própria paginada, grupos active/history, ordenação, detalhe estrangeiro `404`, itens/valores/ponto/imagem opcional, milestones sanitizados, approve/reject/motivo, missão/versionamento/exportação/revisão, autorização separada/TTL/uso único/idempotência, persistência do registro de autorização após reload/claim, snapshot vencido/incompleto, telemetria antiga/provenance, WebSocket próprio/estrangeiro e erros. Para localizações salvas, cobrir lista vazia, primeira/segunda/terceira criação, quarta recusada, CRUD próprio, recurso alheio não enumerável, nome 1–40, endereço ausente, coordenadas inválidas, `user_id` sem autoridade, provider/tipo e quatro flags persistidos, rejeição de confirmação falsa ou tipo inválido, confirmação atual no pedido e cópia fiel para `DeliveryPoint`.

Em PostgreSQL isolado, executar `upgrade`, `alembic check`, `downgrade` e novo `upgrade`. O limite de três exige ainda teste paralelo com sessões/conexões independentes: ambas as requisições devem passar pelo `FOR NO KEY UPDATE` da linha do usuário e o estado final nunca pode exceder três. SQLite em memória não comprova esse lock. Nunca testar downgrade destrutivo no banco do usuário sem backup.

## Mobile

Cobrir formulários, restauração/expiração da sessão, catálogo/carrinho, responsividade, busca/sem resultado, abertura direta sem endereço/GPS, MapLibre/pino central/coordenadas mundiais, confirmação de área, pagamento sem dado bancário, submit, lista/histórico/filtros/paginação, card/título/ID curto/status, detalhe completo, timeline simplificada, estado vazio/erro/offline, atualização WebSocket, reconexão, polling e refresh manual. Para localizações salvas, cobrir item `Minhas localizações` na Conta, listas com 0/1/2/3 registros reais, contador, adicionar/limite, criar/editar/excluir, loading/success/empty/limit/error/offline, picker no checkout, somente itens existentes, revisão no mesmo mapa, captura real de provider/tipo/flags, reinício das duas confirmações atuais, payload condicional do pedido, ajuste sem atualizar o atalho e ausência de cards fictícios. MapTiler real requer testes separados com chave restrita e aparelho/navegador.

## Admin

Cobrir proteção de rota, fila/vazio/erro, detalhe/mapa, configuração MapTiler, loading/timeout/erro/retry/fallback, rota/marcadores/fit bounds, atribuição/logo, approve/reject, export/revisão, health stale/UNKNOWN/null, checks automáticos `PASS/WARNING/BLOCKING`, exatamente três confirmações humanas, ausência da frase, modal final, warning não bloqueante, blocker impeditivo, idempotência/duplo clique, WebSocket/ACK/reconexão/coalescência, alertas/dedupe/cooldown, RTL e abortamento.

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

Cobrir configuração segura, fake, heartbeat, normalização, preflight, rejeição de missão acima de `MAX_MISSION_DISTANCE_M`, timeout, claim concorrente, autorização expirada, hash/versão, upload ACK/erro, releitura, mensagens de outro `sysid/compid`, versão do autopiloto, taxas de stream, telemetria ausente, reconexão, journal, abortamento e RTL.

Os testes Pymavlink usam conexão controlada em memória. Eles não abrem serial/UDP, não executam SITL e não se conectam a hardware.

## SITL

Registrar versão ArduPilot, comando, parâmetros não sensíveis e logs. Cenários: heartbeat, upload curto, início deliberado, chegada, retorno, perda de link, bateria/falha simulada, upload incorreto, abort/RTL e reconciliação. Rodar antes de Pixhawk.

## Hardware e voo

Registrar data, local controlado, operador, hardware/firmware, checklist, missão/hash, logs Mission Planner/TLOG/dataflash e resultado real. Progressão: comunicação → sensores → upload desarmado → motores sem hélices → voo manual → missão curta sem carga → RTL → carga leve/mecanismo → entrega e retorno.

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

## Evidência acumulada — atualizada em 2026-08-08

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

Total comprovado: **173 testes automatizados aprovados**. Artefato Android atual: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 214.406.475 bytes, SHA-256 `ACB33B014CF3407B13B86295E7F6E3BF7AE0006F3CED47520A15D25F9B81287C`. A instalação em emulador/aparelho e a assinatura não foram revalidadas nesta rodada.

## Comandos

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 -SkipBuilds
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
