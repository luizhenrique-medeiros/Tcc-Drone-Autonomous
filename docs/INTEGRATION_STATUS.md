# Estado das integrações

Atualizado em 21 de agosto de 2026, branch `final-1`, commit-base
`b61913995c31933477b2e73910e6d275205d14d2`. **Implementado** significa código e contrato presentes;
**testado** significa comando executado e resultado observado. Teste automatizado, build, HTTP
200, renderização Web, SITL, heartbeat físico, upload e voo são evidências diferentes.

## Resumo atual

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
