# Estado das integrações

Atualizado em 17 de agosto de 2026. **Implementado** significa código e contrato presentes;
**testado** significa comando executado e resultado observado. Teste automatizado, build, HTTP
200, renderização Web, SITL, heartbeat físico, upload e voo são evidências diferentes.

## Resumo atual

| Integração | Implementação | Evidência executada | Estado honesto |
|---|---|---|---|
| PostgreSQL/PostGIS + Alembic | sim | PostgreSQL 17/PostGIS 3.5.2 healthy; `0006_mission_start_health` no head; head único e roundtrip SQLite aprovados | banco atual preservado; dois pedidos de teste continuam `PENDING_ADMIN_APPROVAL` e não podem ser mutados |
| FastAPI | sim | Ruff/format e 53 testes aprovados; 1 opt-in ignorado | `/health` e `/ready` respondem; warning conhecido Starlette/httpx |
| admin React | sim | ESLint, 16 arquivos/67 testes, build Vite e imagem Docker aprovados | bundle gera aviso de chunk acima de 500 kB; novo smoke visual não foi possível |
| Flutter Android/Web | uma base `mobile/` | SDK global estável 3.47.0: format 90 arquivos/0 mudanças, analyze sem issues, 98 testes; Web release, dry run Wasm e APK debug aprovados | build não prova tiles, GPS, aparelho nem UI visual desta rodada |
| MapTiler/MapLibre | estilo híbrido, busca/reverse e mapas Flutter/admin | smoke Chrome real aprovado em 7 de agosto; nesta rodada apenas HTTP/assets/headers | chave exposta precisa ser rotacionada; Android e novo smoke com chaves restritas pendentes |
| CORS/CSP/worker admin | configuração explícita | CSP, nosniff, DENY, Referrer-Policy e worker 200 `application/javascript` conferidos | headers/MIME não provam renderização do mapa |
| gateway `simulation`/Pymavlink | sim | Ruff/format, 57 testes com doubles e imagens Docker aprovados | doubles não provam SITL nem hardware |
| protocolo de missão | ACK, releitura, journal e estados `UPLOADED`/`VERIFIED` | testes automatizados | nenhum upload/releitura foi enviado à Pixhawk |
| comandos operacionais | `START`, `PAUSE`, `CONTINUE`, RTL e ABORT persistidos/ACK-aware | backend, gateway e admin testados | nenhum comando real foi enviado; gates locais estão falsos |
| conexão serial direta | sim | heartbeat real recebido duas vezes em `COM7`/57600, `sysid=1`, `compid=1`, `STABILIZE`, `armed=false` | confirmou somente comunicação/heartbeat daquele momento; GPS, bateria, EKF e home não foram obtidos no diagnóstico passivo |
| gateway real → backend | sim | ciclo limitado de 15 s publicou sete heartbeats `HARDWARE_REAL` com HTTP 200 | não havia comando pendente nem missão elegível; nenhuma escrita MAVLink foi habilitada |
| estado físico atual | sim, com erro explícito | nova execução registrou `HARDWARE_REAL`, `ERROR`, `direct`, COM7/57600, `connected=false`, `heartbeat=false` e três gates falsos | a COM7 não está enumerada agora; o gateway permanece parado |
| forwarding Mission Planner | sim em código/documentação | tentativa passiva em UDP 14551 sem heartbeat; conflito de listener Inbound identificado | Mavlink Mirror ainda precisa ser configurado e validado manualmente |
| SITL | preparado | WSL possui somente `docker-desktop`; ArduPilot/MAVProxy ausentes | não executado |
| armamento, motores, voo e entrega | não automatizados | nenhuma execução | não validados |

`UPLOADED` registra o ACK do protocolo de missão. Só a releitura e comparação integral publicam
`VERIFIED`. Esse estado aguarda armamento físico pelo operador e um `START` separado. O início
exige `ALLOW_FLIGHT_COMMANDS=true` e `ALLOW_MISSION_START=true`; o gateway nunca arma o veículo.
`PAUSE` e `CONTINUE` exigem o gate geral de comandos e ACK do autopiloto.

## Ambiente local executado

| Superfície | Endereço/estado |
|---|---|
| admin | `http://localhost:5173`, container healthy |
| API | `http://localhost:8000`, container healthy |
| OpenAPI | `http://localhost:8000/docs` |
| Flutter Web | `http://localhost:5174`, build release servido por HTTP |
| PostgreSQL | `127.0.0.1:5432`, container healthy |
| gateway físico | parado intencionalmente enquanto a topologia física não está pronta |

O controlador visual do navegador não estava disponível. Foram verificados listeners, respostas
HTTP e assets, mas não houve novo smoke visual, inspeção de console ou validação de tiles nesta
rodada. A validação MapLibre/MapTiler no Chrome de 7 de agosto continua evidência histórica; não
deve ser apresentada como repetida agora.

No admin, a resposta da raiz inclui CSP, `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY` e `Referrer-Policy`; o worker MapLibre respondeu 200 como
`application/javascript`. Esses checks validam entrega/headers, não renderização.

O login administrativo integrado também não foi repetido: `ADMIN_INITIAL_PASSWORD` no `.env`
não corresponde mais ao hash da conta persistida. Não redefina a senha sem autorização do usuário.
Uma falha de login não significa banco vazio; a inspeção direta preservou três pedidos, sendo dois
pendentes e um `COMPLETED` histórico de simulação.

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

Backend, admin e gateway foram reconstruídos com essas tags. Os IDs locais finais das imagens
da aplicação começam por `4b7ade21` (backend), `8dd1f487` (admin) e `29c26f2a` (gateway). O
container do gateway foi recriado e permanece em `Created`/parado, com o volume persistente
preservado. Os digests e IDs são a fotografia local da rodada e podem mudar após novo build ou
quando uma tag mutável for publicada novamente.

## Qualidade, auditorias e artefatos

- backend: 53 testes aprovados e 1 opt-in ignorado; Ruff e format aprovados;
- gateway: 57 testes aprovados; Ruff e format aprovados;
- admin: 16 arquivos/67 testes aprovados, ESLint e build Vite aprovados;
- Flutter: 98/98 testes aprovados com SDK oficial global stable Flutter 3.47.0/Dart 3.13.0;
  format verificou 90 arquivos/0 mudanças, analyze terminou sem issues, Web release e dry run
  Wasm foram aprovados;
- total: **275 testes automatizados aprovados**, mais 1 opt-in ignorado; a bateria orquestrada
  final terminou com exit 0 em 107,5 s e selecionou o SDK por parâmetro, revisão `4cf24164269a`;
- `npm audit`, completo e de produção: zero vulnerabilidades conhecidas;
- `pip-audit` do backend e do gateway: zero vulnerabilidades conhecidas; os pacotes locais do
  próprio projeto foram apenas ignorados pela ferramenta. No caminho com acento, a repetição usou
  `PYTHONUTF8`/`PYTHONIOENCODING` para evitar o erro de decodificação do subprocesso;

Artefatos atuais:

- Flutter Web integrado (`DEMO_MODE=false`, MapTiler configurado pelo `.env` ignorado):
  `main.dart.js` com 3.592.450 bytes; servidor local em 5174 respondeu 200;
- APK debug do mesmo perfil: 195.236.488 bytes, SHA-256
  `202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`;
- APK release assinado: não existe; keystore privado ainda é necessário.

O pacote `maplibre_gl` ainda aplica o Kotlin Gradle Plugin de forma que o Flutter sinaliza como
incompatível com uma versão futura. A dependência direta já está na versão compatível mais recente
resolvida; a correção definitiva depende de atualização do pacote. Atualizações major do admin
(React 19, ESLint 10, TypeScript 7 e outras) não foram aplicadas sem uma migração dedicada.

## Segurança e preservação de dados

O `.env` local mantém:

```env
REAL_HARDWARE_ACKNOWLEDGED=false
ALLOW_MISSION_UPLOAD=false
ALLOW_FLIGHT_COMMANDS=false
ALLOW_MISSION_START=false
```

Nenhuma chave, senha ou token é reproduzido aqui. A chave MapTiler recebida em conversa deve ser
rotacionada e substituída por chaves Web, Android e servidor separadas/restritas.

Os dois pedidos `PENDING_ADMIN_APPROVAL` são evidência de teste. **Não aprovar, não preparar,
não autorizar, não reivindicar e não despachar.** O backup pré-integração do banco foi mantido fora
do repositório; nenhum volume/container de dados foi apagado.

## Próximas ações manuais

1. Reconectar o link USB/telemetria e confirmar que `COM7` reaparece no Gerenciador de
   Dispositivos.
2. Para `direct`, fechar/desconectar completamente o Mission Planner e executar somente
   `scripts\start_gateway.ps1 -DiagnoseOnly`.
3. Para forwarding, manter o Mission Planner como dono da COM7/57600, desabilitar o AutoConnect
   UDP 14551 **Inbound**, configurar `Mavlink Mirror` como UDP Client para `127.0.0.1:14551`, deixar
   **Write access** desligado e repetir o diagnóstico passivo.
4. Instalar Ubuntu/ArduPilot no WSL 2 e executar SITL antes de qualquer upload físico.
5. Obter a senha administrativa persistida ou autorização explícita para rotacioná-la; só então
   repetir o smoke autenticado somente leitura.
6. Rotacionar a credencial MapTiler exposta e repetir Web/admin/Android separadamente.

Nenhum próximo passo deve habilitar upload, comandos ou início antes de heartbeat/telemetria
atuais, SITL, revisão de missão, checklist e autorização operacional específicos.
