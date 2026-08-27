# Relatório de auditoria técnica

- Auditoria original: 6 de agosto de 2026
- Atualização de arquitetura e segurança: 7 de agosto de 2026
- Integração final e hardware passivo: 17 de agosto de 2026
- Verificação final integrada: 20 de agosto de 2026
- ARM administrativo e regressão fail-closed: 21 de agosto de 2026
- Branch inspecionada: `final-1`
- Commit-base inspecionado: `b61913995c31933477b2e73910e6d275205d14d2`

> **Status histórico:** as conclusões originais sobre o provedor de mapas foram superadas pela migração MapTiler/MapLibre. Este documento separa requests HTTP diretos do smoke visual Web realizado depois deles. O resumo legado do provedor anterior permanece apenas em [GOOGLE_MAPS_SETUP.md](GOOGLE_MAPS_SETUP.md).

## Escopo e critério de evidência

A auditoria cobriu código, testes, configurações, migrações, scripts e documentação de `backend`, `drone_gateway`, `mobile`, `admin_web`, raiz e infraestrutura. Artefatos gerados, dependências instaladas e ambientes virtuais não foram tratados como fonte.

O cliente continua sendo **uma única aplicação Flutter em `mobile/` para Android e Web**. `admin_web/` permanece uma aplicação React separada. Nenhum cliente Web paralelo foi criado.

As conclusões distinguem:

1. implementação presente;
2. teste automatizado com doubles;
3. request HTTP direto a serviço externo;
4. execução visual/integrada em browser ou Android;
5. ArduPilot SITL/Mission Planner;
6. Pixhawk ou drone físico.

Um nível não comprova o seguinte. Em particular, HTTP 200 de estilo/geocoding não comprova tiles completos, MapLibre no cliente, origem/`User-Agent`, CORS/CSP, geolocalização ou seleção final.

## Atualização executiva — 21 de agosto de 2026

### 1. Estado do repositório e arquitetura

A aplicação mantém Flutter Android/Web em `mobile/`, admin React separado, FastAPI/PostGIS e
gateway Python isolado. No profile Docker, modo/conexão agora vêm de `GATEWAY_CONTAINER_*`; ele
identifica `GATEWAY_RUNTIME=container` e recusa `real`, `direct` e `mission_planner_forward`;
serial e forwarding executam somente no host Windows. O `docker compose config` foi validado.
O novo `scripts/start_development.ps1` inicia DB/backend/admin e Flutter Web, sem gateway por
padrão; a simulação exige os dois switches de inclusão/confirmação. Parser PowerShell 5.1,
`-ValidateOnly` e recusa sem confirmação passaram sem iniciar serviços.

### 2. Qualidade e dependências

- backend: Uvicorn 0.52.4, Ruff/format, 56 testes aprovados e 1 PostgreSQL opt-in ignorado;
- gateway: Ruff/format e 85 testes aprovados;
- admin: `@testing-library/user-event` 14.6.5, plugin React 6.1.0, MapLibre GL JS 6.4.1,
  Vite 8.2.2 e Vitest 4.1.11; lint, 20 arquivos/112 testes e build aprovados;
- Flutter: SDK oficial stable 3.47.0/Dart 3.13.0, format 90, analyze e 98 testes aprovados;
- Flutter lock: MapLibre direto 0.26.2 e oito transitivas compatíveis atualizadas; 0.27 adiada
  porque exige migração Web/Android com runtime visual/dispositivo;
- total unificado: **351 testes aprovados**, 1 opt-in ignorado, exit 0;
- `pip check`/`pip-audit` nos venvs e nas imagens Python: zero incompatibilidades ou
  vulnerabilidades conhecidas; `npm audit` completo/produção: zero; `npm ci --dry-run` e
  `npm ls`: aprovados.

### 3. Builds e imagens

Builds Docker com `--pull`, Vite, Flutter Web release integrado, dry run automático Wasm e APK
debug integrado passaram. Os artefatos Flutter usam `DEMO_MODE=false`, API local e MapTiler
configurado sem registrar credencial. O APK tem 195.252.860 bytes e SHA-256
`0D1F104AB2D22605F901E7588B8DF16CF159D1149CE9F2F1880DDAA1F482B9F6`; `main.dart.js` tem
3.592.748 bytes e SHA-256 `951B3E50A11620B19A655571D6491C20CC781A77AE44E09D6457A56FA9D856CE`.
O tree manifest Web cobre 40 arquivos/43.303.798 bytes e tem SHA-256
`C7D6B483141E6CDA9B6AEC883E68BF5F9C6948B9EF355B0DE68BC4199B0322CD`; o lock tem SHA-256
`A11E35E0E411D5B7BD81E81B6F66E222134C504230D187847AB086C6FB5C3EC5`.

As imagens do snapshot de 20/08 começam por `0f8c4855` (admin), `220aaddad0` (backend) e `85340a31ab`
(gateway). Os digests-base preservados são `ffb752e1` (Python), `d32cdf61` (Node), `a8b39bd9`
(Nginx) e `83e9999d` (PostGIS). DB/backend/admin ficaram healthy; o gateway novo ficou
`Created`/parado, em simulação, com todos os gates de escrita falsos. Elas não foram reconstruídas
depois da inclusão do ARM administrativo e não são evidência do código de 21/08.

### 4. Banco e fluxo de negócio

O head versionado é `0007_vehicle_arm_command` e passou em banco temporário. O último snapshot do
PostgreSQL vivo permanece em `0006_mission_start_health`; nenhum upgrade foi aplicado nesta rodada.
Esse banco preserva 1 pedido `COMPLETED`, 2 pedidos
`PENDING_ADMIN_APPROVAL`, 0 comandos de gateway e 34.179 snapshots de saúde. Os dois pedidos
pendentes não foram aprovados, preparados, autorizados, reivindicados ou despachados.

### 5. HTTP, WebSocket, mapa e autenticação

`/health`, `/ready`, `/docs`, admin 5173 e Flutter Web 5174 responderam 200. CSP, nosniff, DENY e
Referrer-Policy estavam presentes; o worker MapLibre respondeu 200 como JavaScript. O WebSocket
admin recebeu `operations.connected`. O preflight Flutter retornou 200 com origem exata e métodos
`GET`, `POST`, `PATCH`, `DELETE` e `OPTIONS`; request sem token retornou 401 e um JWT efêmero de
cliente listou quatro produtos.

O estilo MapTiler respondeu 200 como JSON GL v8 `Satellite Hybrid` com 40 camadas, e reverse
geocoding respondeu 200 com 10 resultados. O controlador visual integrado não encontrou navegador,
logo não houve nova evidência de login visual, mapa renderizado, tiles, console ou interação UI.
O login admin com a senha atual do `.env` continuou em 401; nenhuma senha foi rotacionada.

### 6. Pixhawk direta e telemetria real

Um diagnóstico e o gateway host executaram somente leitura entre 11:14:04Z e 11:19:05Z sobre
COM7/57600. A Pixhawk 6C/ArduCopter 4.6.3 respondeu como system/component 1/1, `STABILIZE` e
`armed=false`. Foram persistidos 129 snapshots `HARDWARE_REAL`; bateria ficou em 74–75%, GPS
chegou a fix 3/5 satélites e terminou fix 1/0, EKF/preflight ficaram falsos e home/origin ausentes.
REST e WebSocket exibiram a origem real; depois da parada, o snapshot ficou `is_stale=true`.

### 7. Limites operacionais

Todos os gates permaneceram falsos. Não houve comando, ACK operacional, upload, releitura, start,
armamento, ensaio de motor ou voo. Observar `armed=false` não é um ensaio de motor. O veículo não
atingiu preflight-ready e o resultado final é `NO-GO`.

### 8. Mission Planner e SITL

O forwarding E2E não funcionou: UDP 14551 estava configurada como entrada e o diagnóstico expirou
sem heartbeat. É necessário desabilitar esse listener e configurar Mavlink Mirror como UDP Client
`127.0.0.1:14551`, com **Write access OFF**. SITL não pôde ser executado: o WSL contém apenas
`docker-desktop`, sem distribuição ArduPilot/MAVProxy.

### 9. Ações externas e segurança

As três variáveis MapTiler estavam presentes, mas compartilhavam o mesmo valor exposto. Criar três
chaves separadas/restritas, substituir no `.env` ignorado, rebuildar/validar cada superfície e só
então revogar a chave antiga. Durante a inspeção da configuração externa do Mission Planner foi
identificado, em cache, um token de sessão de um
serviço aeronáutico. O valor e o serviço não são registrados; por precaução, encerrar/reautenticar
ou revogar essa sessão após o trabalho. Atualizações disponíveis de Docker Desktop 4.87, WSL
2.7.12, VS Code e Java não foram aplicadas; Docker Scout exigiu login.

### 10. Conclusão

Software, mocks, builds e telemetria real passiva foram comprovados. SITL, forwarding Mission
Planner E2E, upload, ensaio de motor e voo permanecem não comprovados. A matriz literal está em
[INTEGRATION_STATUS.md](INTEGRATION_STATUS.md); ações exatas estão em
[MANUAL_ACTIONS_REQUIRED.md](MANUAL_ACTIONS_REQUIRED.md).

## Atualização executiva histórica — 17 de agosto de 2026

- backend: Ruff/format e 53 testes aprovados, com 1 opt-in ignorado;
- gateway: Ruff/format e 57 testes aprovados;
- admin: ESLint, 16 arquivos/67 testes, build Vite e imagem Docker aprovados;
- Flutter: no SDK oficial global stable Flutter 3.47.0/Dart 3.13.0, format verificou 90 arquivos
  sem mudanças, analyze terminou sem issues e 98/98 testes passaram no rerun final; Web release,
  dry run Wasm e APK debug aprovados;
- migração `0006_mission_start_health` aplicada ao PostgreSQL real; head único e roundtrip SQLite
  aprovados;
- `pip-audit` do backend/gateway e `npm audit` do admin retornaram zero vulnerabilidades
  conhecidas; os pacotes Python locais foram ignorados pela ferramenta;
- DB/API/admin healthy e Flutter Web servido; `/health`, `/ready`, `/docs`, 5173 e 5174
  responderam 200;
- headers CSP, nosniff, DENY e Referrer-Policy do admin conferidos; worker MapLibre respondeu 200
  como `application/javascript`;
- controlador visual do navegador indisponível; nenhum novo smoke visual/console/tiles foi inferido;
- login admin com a credencial atual do `.env` retornou 401 porque ela diverge do hash persistido;
  a conta não foi redefinida;
- dois diagnósticos passivos diretos receberam heartbeat real da Pixhawk em COM7/57600,
  system/component 1/1, `STABILIZE`, `armed=false`; um ciclo limitado publicou sete heartbeats no
  backend sem escrita MAVLink;
- no estado final daquela rodada a COM7 estava ausente, Mission Planner estava fechado e não havia listeners 14550/14551
  e o snapshot é `HARDWARE_REAL`/`ERROR`/`direct`, com os três gates falsos;
- forwarding, SITL, GPS/bateria/EKF/home ao vivo pelo gateway, upload, armamento, motores e voo não
  foram validados.

Total daquela fotografia: **275 testes aprovados**, mais 1 opt-in ignorado; a bateria orquestrada terminou com
exit 0 em 107,5 s. O APK debug integrado atual,
regenerado com `DEMO_MODE=false` e a configuração MapTiler do `.env` ignorado, tem 195.236.488
bytes e SHA-256 `202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`.
As evidências de 6–17 de agosto abaixo são históricas e não substituem a fotografia de 20/08.

## Resultado executivo histórico — 7 de agosto de 2026

A base funcional preserva autenticação e papéis, PostGIS, pedidos persistidos, separação entre aprovação comercial e autorização de voo, missão versionada, WebSocket autenticado e gateway isolado. O modo `simulation` continua sendo evidência lógica, não evidência de voo.

A integração de mapas vigente é:

| Superfície | Implementação | Limite atual |
|---|---|---|
| Flutter Android/Web | `maplibre_gl` com estilo híbrido MapTiler, pino central e eventos de câmera | Web validado no Chrome; Android runtime pendente |
| admin React | MapLibre GL JS, rota/pontos, fit bounds/zoom, loading/erro/retry/fallback | 33 testes/lint/build e smoke visual autenticado aprovados |
| FastAPI | proxy autenticado para MapTiler Geocoding API | fluxo Flutter Web completo aprovado; chave substituta de servidor pendente |

O projeto usa `hybrid-v4/style.json`, não o visualizador em `iframe`. O admin não usa Static Maps. Atribuição MapTiler/OpenStreetMap e logo MapTiler do plano Free permanecem obrigatórios.

## Credenciais e exposição

A chave recebida para a migração foi exposta em conversa. Ela deve ser substituída antes de apresentação pública:

- `MAPTILER_WEB_API_KEY`: chave cliente observável, restrita pelas origens Web exatas;
- `MAPTILER_ANDROID_API_KEY`: chave cliente extraível do APK, separada e restringida somente depois de observar/validar o `User-Agent` real;
- `MAPTILER_SERVER_API_KEY`: somente FastAPI, nunca enviada ao cliente; em hospedagem, considerar credencial de serviço assinada;
- `MAPTILER_STYLE_URL`: URL HTTPS de `style.json` sem query ou credencial.

Nenhuma chave deve entrar em documentação, screenshot, log, histórico de terminal ou Git. A chave exposta deve ser revogada depois de testar as substitutas.

## Evidência confirmada em 2026-08-07

### MapTiler HTTP direto

| Chamada | Resultado observado | Conclusão permitida |
|---|---|---|
| estilo híbrido | HTTP 200, documento GL v8, 40 layers | o estilo respondeu naquele request |
| pesquisa | HTTP 200, 3 features naquele ensaio | a Search API respondeu àquela consulta |
| reverse geocoding | HTTP 200, 1 feature naquele ensaio | a Search API respondeu àquela coordenada |

A credencial não é reproduzida. Esses resultados diretos não validam, por si sós, browser, Android ou fluxo completo; a camada Web foi testada separadamente abaixo.

### Flutter Web

O release integrado foi aberto no Chrome em `http://localhost:5174`. Cadastro/login, catálogo, carrinho, pesquisa por Atibaia, resolução, estilo híbrido, tiles, fontes, sprites, câmera inicial em zoom 18, arraste, reverse geocoding, confirmação de área segura, PIX simulado e criação do pedido foram observados sem erro de runtime. Atribuição MapTiler/OpenStreetMap e logo estavam visíveis. O estado de geolocalização bloqueada teve fallback manual funcional; permissão concedida e timeout não foram exercitados.

### Admin

O painel aprovou ESLint, 33 testes e build Vite. Um smoke autenticado exibiu o pedido novo e seu ponto real no mapa híbrido. Durante o ensaio, o evento de prontidão foi corrigido de `load` para `style.load`, evitando timeout depois de o estilo já ter sido baixado. O Web Worker ESM também passou a usar o pipeline oficial `?worker&url` do Vite; o asset autocontido respondeu 200 e eliminou 404/MIME incorreto. O reteste confirmou estado pronto, tiles 200, logo/atribuição e ausência de erro novo no console. Headers CSP, X-Frame-Options e nosniff também foram confirmados na resposta real de `/` e do bundle.

### Auditoria de dependências

`pip-audit` detectou `PYSEC-2026-1845` no pytest 8.4.2, risco médio relacionado ao tratamento de `tmpdir` em UNIX. A constraint de desenvolvimento foi elevada para `pytest>=9.0.3,<10` no backend e gateway. Ambas as suítes passaram depois da atualização e o `pip-audit` final retornou zero vulnerabilidades conhecidas.

`npm audit` das dependências de produção do admin também retornou zero vulnerabilidades conhecidas. Os dois resultados são fotografias datadas e devem ser repetidos depois de mudar constraints/locks.

O total executado nesta atualização foi **124 testes**: backend 28, gateway 31, admin 33 e Flutter 32.

## Evidência anterior preservada

Uma chamada controlada diretamente à API criou o pedido `27207fa7-df70-45b5-bb2f-d9279a0347f8`, em `PENDING_ADMIN_APPROVAL`, com coordenadas finais `-23.1178450,-46.5507630` confirmadas no PostgreSQL. Isso comprova contrato/persistência, não mapa funcional nem despacho. **Não aprovar, preparar missão, autorizar voo ou despachar esse pedido.**

Depois de rotacionar e reconciliar a credencial local, o login administrativo, dashboard e detalhe do pedido responderam com sucesso. A inspeção foi somente leitura.

O smoke Web criou também o pedido `92198217-c06b-41f5-b91e-61b985b86803`, em `PENDING_ADMIN_APPROVAL`, com coordenadas `-23.117843,-46.554947` e preferência PIX simulada. **Não aprovar, preparar, autorizar ou despachar nenhum pedido de teste.**

Naquela rodada, o release Web foi recompilado e o APK debug tinha 190.538.195 bytes e o hash então
registrado. Esse artefato foi superado pelo APK da atualização executiva acima. Ainda não há
keystore privada nem release distribuível atual.

## Pendências críticas

- criar e testar chaves MapTiler separadas, configurar quotas/restrições e revogar a exposta;
- executar em emulador/aparelho Android e observar/validar o `User-Agent` antes da restrição;
- testar geolocalização Web concedida, timeout e indisponível;
- testar preparação, revisão e autorização administrativas somente em um ensaio controlado separado;
- comprovar atomicidade/concorrência de decisões, preparação, autorização e claim em PostgreSQL;
- revisar o vínculo verificável entre credencial, gateway e veículo/missão;
- testar SITL antes de Mission Planner/Pixhawk/bancada/voo;
- gerar e instalar novo APK release assinado com a configuração atual.

## Ações deliberadamente não realizadas

- nenhuma chave ou senha foi copiada para documentação, log ou Git;
- nenhum sucesso de browser/Android foi inferido dos requests HTTP diretos;
- porta, firmware e IDs só foram registrados quando observados; nenhum parâmetro da Pixhawk foi
  alterado ou presumido;
- nenhum comando de armamento real foi executado;
- nenhum resultado de SITL, hardware ou voo foi inferido de doubles;
- nenhum pagamento real foi implementado.

Consulte [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md), [MAPTILER_SETUP.md](MAPTILER_SETUP.md) e [MANUAL_ACTIONS_REQUIRED.md](MANUAL_ACTIONS_REQUIRED.md).
