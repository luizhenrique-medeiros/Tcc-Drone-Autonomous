# Desenvolvimento

## Ambiente

Windows 10/11, PowerShell, Python 3.13, Node, Docker Desktop, Flutter, Chrome e Android SDK. WSL 2 é o ambiente previsto para SITL, mas ainda não possui uma distribuição ArduPilot/MAVProxy nesta máquina. O SDK Flutter pode existir em `./flutter` local, mas fica ignorado e não deve ser commitado.

Fotografia de 20 de agosto de 2026: Python 3.13.15, Node 24.19.0, npm 11.17.0,
Docker Desktop 4.86.0/Engine 29.7.2, Git 2.55.0.windows.3, Android Studio 2026.1.3,
Android API 37, AGP 9.1.1 e Gradle 9.3.1. O SDK oficial global é Flutter 3.47.0/Dart 3.13.0.
Os scripts resolvem `-FlutterSdkRoot` → `FLUTTER_ROOT` → `PATH` e validam canal `stable`,
Flutter 3.47.x e Dart 3.13.x. `./flutter` requer `-AllowBundledFlutterSdk` explícito e o fork
pré-release presente nesta máquina é rejeitado. Sempre registre caminho e `--version` do binário.
Se a ExecutionPolicy impedir a chamada direta, execute-os com
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script.ps1>`; o bypass vale apenas para
o processo iniciado.

Docker Desktop 4.87, WSL 2.7.12, VS Code e Java apareceram como atualizações disponíveis, mas
não foram instalados automaticamente. Docker Scout exigiu login e não foi usado como evidência.

## Primeira execução

```powershell
Copy-Item .env.example .env
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_development.ps1 `
  -FlutterSdkRoot 'C:\Users\Luiz\Documents\flutter'
```

Esse comando sobe DB/backend/admin e inicia Flutter Web em primeiro plano. Valide sem iniciar nada
com `-ValidateOnly`. Inclua o gateway simulado somente com os dois switches
`-IncludeSimulationGateway -ConfirmSimulationGateway`; a ausência da confirmação é recusada.
O Compose usa `GATEWAY_CONTAINER_*`, define `GATEWAY_RUNTIME=container` e recusa modos de
hardware. `direct` e `mission_planner_forward` executam somente no host pelo
`scripts/start_gateway.ps1`, que define o runtime correspondente.

Troque segredos `change_me`. Se o Docker não puder ler `~/.docker/config.json`, corrija permissão local; não copie credencial para o repositório.

### Python

Use `python` 3.13 quando o `py` launcher não registrar a instalação:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\ruff check .
.\.venv\Scripts\pytest
```

Repita em `drone_gateway`. Não misture os ambientes virtuais.

### Node no PowerShell

Se a política bloquear `npm.ps1`, use `npm.cmd`:

```powershell
cd admin_web
npm.cmd install
npm.cmd run dev
```

O admin carrega MapLibre GL JS com `MAPTILER_WEB_API_KEY` e `MAPTILER_STYLE_URL` no `.env.local`/ambiente de build. A chave Web aparece no bundle e deve ser restrita por origem; a URL de estilo permanece sem `?key=`.

### Flutter

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 `
  -SkipBuilds `
  -FlutterSdkRoot '<CAMINHO_SDK_FLUTTER_OFICIAL>'
```

No Windows, o servidor de análise e o Gradle podem falhar quando o caminho absoluto contém acentos. Os scripts `bootstrap.ps1`, `start_mobile.ps1` e `test_all.ps1` detectam esse caso e reutilizam uma junção ASCII validada dentro do diretório temporário. Projeto, SDK e cache Pub continuam no mesmo disco, evitando a limitação de raízes diferentes do compilador Kotlin; não mova o repositório nem versione aliases locais.

O Android atual compila com API 37, AGP 9.1.1 e Gradle 9.3.1. O Android Studio deve ser
atualizado pelo próprio editor quando o `winget` assim indicar. Command-line tools/licenças ainda
precisam de confirmação humana; não execute aceitação de licença automaticamente. O aviso futuro
do Kotlin Gradle Plugin, Java 8 source/target e APIs de plugins vem do pacote `maplibre_gl` 0.26.2
e dependências, não de falha do APK atual. A 0.27 foi adiada porque exige migração Web/Android e
validação visual/em dispositivo.

A configuração de mapas usa `MAP_PROVIDER=maptiler`, `MAPTILER_STYLE_URL` e chaves MapTiler
separadas para Web, Android e servidor. Todos os valores ficam no ambiente ou em arquivo local
ignorado. Na inspeção de 20/08, as três variáveis estavam presentes, mas continham o mesmo valor;
isso mantém o risco de exposição cruzada. Crie três chaves novas e restritas, substitua-as no
`.env` ignorado, refaça os builds/testes por plataforma e somente então revogue a chave exposta.
Não copie valores para comandos, logs ou Git. O fallback de mapa é apenas desenvolvimento.

Para abrir Flutter Web integrado à API local:

```powershell
.\scripts\start_mobile_web.ps1
```

Para abrir deliberadamente sem MapTiler e conferir somente os estados locais:

```powershell
.\scripts\start_mobile_web.ps1 -WithoutMapTiler
```

Para o emulador Android, configure a chave restrita e execute:

```powershell
$env:MAPTILER_ANDROID_API_KEY='chave-android-restrita-local'
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -MapTilerConfigured
```

Dispositivo físico usa `-Profile android_physical_device -ApiBaseUrl http://<IP-LAN>:8000 -AllowInsecureLanHttp -MapTilerConfigured` e requer exposição consciente da API. A chave Android é incorporada ao APK; observe e valide o `User-Agent` real antes de configurar sua restrição. Fora do debug local, a URL integrada deve usar HTTPS e uma distribuição exige keystore privado externo.

## Banco e seed

Compose habilita PostGIS pelo init. `alembic upgrade head` deve funcionar em banco vazio. Seed é idempotente; admin inicial só é criado com variáveis explícitas. Nunca use seed de demo em banco com evidência de voo sem revisão.

## Qualidade

Python: Ruff e Pytest. React: ESLint, testes e build TypeScript. Flutter: formatter, analyze, testes, build Web release e APK debug quando os SDKs estiverem disponíveis. Mudança de schema ganha migração; bug ganha regressão.

Para auditar Python no caminho acentuado do projeto, force a saída do subprocesso em UTF-8:

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
.\.venv\Scripts\python.exe -m pip_audit
```

Na rodada de 20/08, `pip check` e `pip-audit` nos ambientes virtuais e nas imagens finais de
backend/gateway retornaram zero incompatibilidades/vulnerabilidades conhecidas. `npm.cmd audit`
completo e de produção também retornou zero; `npm ci --dry-run` e `npm ls` passaram. As versões
diretas ficaram em Uvicorn 0.52.4 e, no admin, user-event 14.6.5, plugin React 6.1.0, MapLibre
6.4.1, Vite 8.2.2 e Vitest 4.1.11.

No Flutter, somente `mobile/pubspec.lock` mudou: MapLibre direto 0.26.2 e oito transitivas
compatíveis (archive 4.1.0, code_assets 2.0.0, dbus 0.7.15, hooks 2.2.0, image 4.9.2,
objective_c 9.6.0, record_use 1.1.1 e vm_service 15.3.0). Format/analyze/98 testes e os builds
Web/Wasm/APK foram repetidos depois da mudança.

As imagens atuais são `postgis/postgis:17-3.5`, `python:3.13-slim`, `node:24-alpine` e
`nginx:1.28.3-alpine`. Tags são mutáveis: registre o digest observado em cada auditoria e não
confunda um pull/build aprovado com validação funcional da aplicação.

Com a stack simulada healthy, o smoke vertical reproduzível é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1 -ConfirmSimulationMutation
```

Ele persiste um cliente, pedido, missão, eventos e telemetria fake no banco local. Não o execute contra produção e não trate `COMPLETED` simulado como prova de entrega física.

Em 21/08, após o ARM administrativo e o hardening de locks/correlação, o mesmo comando com
`-SkipBuilds` terminou com exit 0: backend 56, gateway 85, admin 112 e Flutter 98, total de
**351 aprovados + 1 opt-in ignorado**. A revisão `0007_vehicle_arm_command` passou apenas em banco
temporário; o PostgreSQL vivo e o hardware não foram modificados.

O resultado unificado de 20/08 foi exit 0, com 54 testes backend, 63 gateway, 67 admin e 98
Flutter: **282 aprovados + 1 opt-in ignorado**. O ensaio COM7 posterior foi receive-only e não faz
parte dessas contagens: produziu 129 snapshots reais, sem comando, upload, armamento ou voo.

## Fluxo Git

Branches `feature/...`/`fix/...`, commits Conventional Commits. Não versionar SDKs, APK, firmware, `.env`, banco, logs ou exportações locais. Antes de commit, revisar `git status` porque o repositório pode conter trabalho do usuário.

## Troubleshooting

- API `ready` falha: verificar Postgres, URL e migração.
- mapa vazio: verificar `MAPTILER_CONFIGURED`, estilo sem query, chave da plataforma, restrição de origem/`User-Agent`, CSP/CORS e quota; não declarar sucesso pelo simples HTTP 200 do estilo.
- busca falha: verificar `MAPTILER_SERVER_API_KEY` somente no backend e respostas 403/429 sem registrar a query com credencial.
- admin CORS: incluir origem exata em `CORS_ORIGINS`.
- gateway sem heartbeat: validar modo/conexão e SITL antes do real.
- login admin 401 após mudar `.env`: a variável inicial não regrava o hash de uma conta já
  persistida; obtenha a senha vigente ou peça autorização para usar o script de rotação.
- `COM7`/telemetria inadequada: confirmar a enumeração, usar apenas um dono da serial e repetir
  primeiro o diagnóstico receive-only; em 20/08 o link direto funcionou, mas GPS terminou fix 1/0,
  EKF/preflight ficaram falsos e home/origin ausentes.
- forwarding sem heartbeat: desabilitar o listener UDP 14551 Inbound do Mission Planner e criar
  Mavlink Mirror UDP Client para `127.0.0.1:14551`, com Write access desligado.
- pre-arm: ler mensagem no Mission Planner; não desabilitar check.
- comando crítico timeout: preservar erro/evento e investigar link, sem retry infinito.
