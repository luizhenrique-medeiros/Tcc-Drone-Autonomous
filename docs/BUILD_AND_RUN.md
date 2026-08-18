# Build e execução

Comandos para Windows/PowerShell. O projeto usa uma única base Flutter em `mobile/` para Android e Web; `admin_web/` é o painel operacional separado.

Como a política do PowerShell pode bloquear scripts locais, os exemplos invocam scripts do repositório com:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script.ps1>
```

Isso altera apenas o processo iniciado; não muda a policy global da máquina.

## Pré-requisitos

- Docker Desktop 4.86.0 e Docker Engine/Compose 29.7.2;
- Node.js 24.19.0 e npm 11.17.0 (`npm.cmd` evita o wrapper `npm.ps1` quando a policy bloqueia scripts);
- Python 3.13.15 nos ambientes virtuais ou containers;
- Flutter 3.47/Dart 3.13 compatíveis com `mobile/pubspec.yaml`;
- Chrome ou Edge para Flutter Web;
- Android SDK API 37, JDK 17+, AGP 9.1.1 e Gradle 9.3.1 para APK;
- `.env` local criado a partir de `.env.example`, sem segredos versionados.

O caminho do projeto possui caracteres acentuados. Os scripts Flutter usam a junção ASCII temporária fornecida pelo repositório.

O computador possui o SDK oficial global estável Flutter 3.47.0/Dart 3.13.0. Os scripts resolvem
o SDK na ordem `-FlutterSdkRoot`, `FLUTTER_ROOT` e `PATH`; `./flutter` só entra na seleção com
`-AllowBundledFlutterSdk` explícito. Antes de executar, eles validam o canal `stable`, Flutter
3.47.x, Dart 3.13.x e que `flutter`/`dart` pertencem ao mesmo SDK. O fork local pré-release desta
máquina é rejeitado por essas regras. A atualização do Android Studio permanece manual pelo
próprio editor; não aceite licenças automaticamente em nome do usuário.

## URLs locais

| Aplicação | URL |
|---|---|
| API | `http://localhost:8000` |
| OpenAPI | `http://localhost:8000/docs` |
| admin React | `http://localhost:5173` |
| cliente Flutter Web | `http://localhost:5174` |

## 1. Backend e admin

Na raiz:

```powershell
docker compose config --quiet
docker compose up -d --build db backend admin
docker compose ps
docker compose logs --tail=200 backend admin
```

Antes de qualquer fluxo administrativo completo, confirme que o `.env` local não contém placeholders. No estado atual, a senha inicial do `.env` não corresponde ao hash do administrador persistido e o login retorna `401`. Não redefina a conta sem autorização e não copie credenciais para documentação ou terminal.

O gateway não sobe no perfil padrão. Para `simulation`:

```powershell
docker compose --profile gateway up -d --build
```

Não use o container do gateway para abrir `COM7` no Windows. Em `direct` ou `mission_planner_forward`, mantenha banco/backend/admin no Docker e execute o gateway no host com o script da seção 9.

## 2. Flutter Web — modo recomendado

Com API/admin ativos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1
```

O launcher:

- usa o perfil `local_web` e `API_BASE_URL=http://localhost:8000`;
- abre Chrome por padrão na porta 5174;
- carrega seletivamente `MAPTILER_WEB_API_KEY`, `MAPTILER_STYLE_URL` e `FLUTTER_WEB_PORT` do `.env` quando o processo ainda não os definiu;
- não mostra a chave no resumo;
- executa `flutter pub get` se `package_config.json` estiver ausente ou se `pubspec.yaml`/`pubspec.lock` forem mais novos;
- preserva hot reload: pressione `r` no terminal do Flutter;
- detecta porta ocupada antes de iniciar.

Parâmetros opcionais:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1 `
  -Device edge `
  -Port 5174
```

Para validar deliberadamente o fallback local:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1 `
  -WithoutMapTiler
```

O fallback não é mapa real e não libera checkout integrado.

### Diagnóstico debug

Em build debug e ambiente não hospedado, use a rota `/debug` ou o atalho no perfil para conferir plataforma, URL, API, WebSocket, estilo/tiles MapTiler, busca pelo backend, geolocalização, presença de sessão, versão e modo. Nenhuma chave ou JWT é exibida.

## 3. Flutter Web — comandos diretos

Para desenvolvimento sem o wrapper:

```powershell
cd mobile
flutter.bat pub get
flutter.bat run -d chrome `
  --web-port 5174 `
  --dart-define=APP_ENVIRONMENT=local_web `
  --dart-define=DEMO_MODE=false `
  --dart-define=API_BASE_URL=http://localhost:8000 `
  --dart-define=MAP_PROVIDER=maptiler `
  --dart-define=MAPTILER_CONFIGURED=true `
  --dart-define=MAPTILER_STYLE_URL=$env:MAPTILER_STYLE_URL `
  --dart-define=MAPTILER_WEB_API_KEY=$env:MAPTILER_WEB_API_KEY
```

Não cole o valor da chave na linha de comando. Defina-a no ambiente ou use o wrapper.

O build estático não possui hot reload e precisa ser servido por HTTP; abrir `index.html` diretamente não é suportado:

```powershell
flutter.bat build web --release
flutter.bat build web --wasm --dry-run
```

Build integrado não-debug exige perfil hospedado e API HTTPS; use `flutter run` para desenvolvimento local HTTP.

## 4. Android emulador

O emulador alcança o host por `10.0.2.2`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile.ps1 `
  -Integrated `
  -TargetProfile android_emulator `
  -ApiBaseUrl http://10.0.2.2:8000 `
  -MapTilerConfigured
```

Sem chave Android, remova `-MapTilerConfigured`; o app informa o fallback. A chave Android é incorporada ao APK e deve ser separada da Web/servidor; observe o `User-Agent` real antes de restringi-la.

## 5. Android físico na LAN

Siga [LOCAL_NETWORK_SETUP.md](LOCAL_NETWORK_SETUP.md):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile.ps1 `
  -Integrated `
  -TargetProfile android_physical_device `
  -ApiBaseUrl http://IP_DO_PC:8000 `
  -AllowInsecureLanHttp `
  -MapTilerConfigured
```

`localhost` e `10.0.2.2` não servem para aparelho físico. Para qualquer rede além de uma LAN debug controlada, use HTTPS.

## 6. Qualidade e builds Flutter

```powershell
cd mobile
flutter.bat pub get
dart.bat format --output=none --set-exit-if-changed lib test
flutter.bat analyze
flutter.bat test
flutter.bat build apk --debug --dart-define=DEMO_MODE=true
```

Artefato debug esperado:

```text
mobile/build/app/outputs/flutter-apk/app-debug.apk
```

O build release pode verificar compilação, mas distribuição/instalação exige keystore externo e credenciais do ambiente:

```powershell
flutter.bat build apk --release
```

O APK debug atual foi recompilado no perfil integrado (`DEMO_MODE=false`, configuração
MapTiler obtida do `.env` ignorado) com `compileSdk=37`, AGP 9.1.1 e Gradle 9.3.1:
195.236.488 bytes, SHA-256
`202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`. Ele ainda precisa ser
instalado e executado em emulador/aparelho. Não há APK release atual nem keystore privada
configurada para distribuição. O pacote `maplibre_gl` ainda produz aviso de compatibilidade futura
com o Kotlin Gradle Plugin; o build atual termina com sucesso, mas a dependência precisa ser
reavaliada quando publicar uma correção.

Não use a chave debug como assinatura de distribuição e não versione APK ou keystore.

## 7. Admin React sem Docker

```powershell
cd admin_web
npm.cmd install
npm.cmd run lint
npm.cmd run test
npm.cmd run build
npm.cmd run dev -- --host 0.0.0.0 --port 5173
```

`VITE_DEMO_MODE=false` é o modo integrado. Demo deve ser ativada explicitamente e identificada visualmente.

Configure `MAPTILER_WEB_API_KEY` e `MAPTILER_STYLE_URL` antes do build. A URL de estilo permanece sem `?key=`; a chave Web fica no bundle e deve ser restrita por origem. O admin usa MapLibre GL JS, não `iframe` nem Static Maps.

## 8. Backend sem Docker

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

O backend usa apenas `MAPTILER_SERVER_API_KEY` para pesquisa/geocodificação. Não reutilize a chave Web/Android nem registre a query externa com credencial.

Fora do Compose, ajuste `DATABASE_URL`; o hostname `db` só existe na rede Docker.

## 9. Gateway

```powershell
cd drone_gateway
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest
cd ..
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_gateway.ps1 `
  -DiagnoseOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_gateway.ps1
```

O primeiro comando é diagnóstico passivo e termina; o segundo mantém o processo integrado ao backend. O padrão versionado é `simulation`, enquanto o `.env` local pode escolher `direct` ou `mission_planner_forward`. Em hardware, mantenha `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false` até concluir cada gate. Siga [MISSION_PLANNER_SETUP.md](MISSION_PLANNER_SETUP.md); mudar apenas o modo não configura a topologia nem substitui checklist.

## 10. Smoke integrado mutante

Se o administrador já existe com senha inicial insegura, rotacione primeiro:

```powershell
docker compose exec backend python scripts/rotate_admin_password.py `
  --email admin@example.local
```

Depois, somente em loopback/ambiente descartável de simulação:

```powershell
$env:ADMIN_INITIAL_PASSWORD='SENHA_LOCAL_ROTACIONADA'
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\integration_smoke.ps1 `
  -ConfirmSimulationMutation
```

O smoke cria dados e altera estados. `COMPLETED` em `simulation` não prova entrega física.

## 11. Bateria completa

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 `
  -FlutterSdkRoot '<CAMINHO_SDK_FLUTTER_OFICIAL>'
```

Acrescente `-SkipBuilds` para ciclo rápido. Não invoque `./scripts/test_all.ps1` diretamente se a
ExecutionPolicy bloquear scripts locais: essa tentativa termina antes da bateria. Registre exit code,
contagens, artefatos e hashes em [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md). Não reutilize
contagens/hashes de uma bateria anterior depois de alterar código.

## Evidência atual — 17 de agosto de 2026

- backend: Ruff/format e 53 testes aprovados, com 1 opt-in ignorado;
- gateway: Ruff/format e 57 testes aprovados;
- admin: ESLint, 16 arquivos/67 testes, build Vite e imagem Docker aprovados;
- Flutter: no SDK oficial global estável 3.47.0/Dart 3.13.0, format verificou 90 arquivos sem
  mudanças, analyze terminou sem issues e 98/98 testes passaram; Web release, dry run
  Wasm e APK debug integrado (`DEMO_MODE=false`) também foram aprovados; `main.dart.js` tem
  3.592.450 bytes e o servidor em 5174 respondeu 200;
- orquestração: `test_all.ps1 -SkipBuilds` terminou com exit 0 em 107,5 s usando a seleção por
  parâmetro do SDK oficial stable, revisão `4cf24164269a`; a chamada direta bloqueada pela
  ExecutionPolicy não executou a bateria e não entra como resultado;
- Docker: banco, API e admin healthy; gateway físico parado deliberadamente;
- HTTP: `/health`, `/ready`, `/docs`, admin 5173 e Flutter Web 5174 responderam 200;
- admin: CSP, `nosniff`, `DENY` e `Referrer-Policy` presentes; worker MapLibre respondeu 200 com
  `application/javascript`;
- migração: `0006_mission_start_health` aplicada; head único e roundtrip SQLite aprovados;
- navegador: controlador visual indisponível; não houve novo smoke visual, console ou tiles;
- login admin: credenciais atuais do `.env` retornaram 401; não resetar sem autorização.
- auditorias: `pip-audit` de backend/gateway e `npm audit` completo/produção retornaram zero
  vulnerabilidades conhecidas; use UTF-8 explícito no subprocesso Python se o caminho acentuado
  causar erro de decodificação.

Imagens usadas: `postgis/postgis:17-3.5`, `python:3.13-slim`, `node:24-alpine` e
`nginx:1.28.3-alpine`. Digests e matriz completa estão em
[INTEGRATION_STATUS.md](INTEGRATION_STATUS.md).

## Evidência histórica após a migração de mapas

Em 2026-08-07, antes da bateria atual:

- backend aprovou Ruff/formatação e 28 testes; gateway aprovou Ruff/formatação e 31 testes;
- o admin aprovou lint, 33 testes, build Vite e smoke visual autenticado com MapLibre GL JS;
- o Flutter aprovou formatação/analyze, 32 testes, build Web configurado, smoke Chrome completo e build APK debug configurado;
- requests HTTP diretos retornaram estilo MapTiler 200 (GL v8/40 layers), pesquisa 200 (3 features naquele ensaio) e reverse geocoding 200 (1 feature naquele ensaio);
- `pip-audit` encontrou `PYSEC-2026-1845` no pytest 8.4.2; depois de elevar as constraints de desenvolvimento do backend/gateway para `pytest>=9.0.3,<10`, ambas as suítes passaram e o audit final retornou zero vulnerabilidades conhecidas;
- `npm audit` das dependências de produção do admin retornou zero vulnerabilidades conhecidas.

O smoke Flutter Web confirmou estilo/tiles/fontes/sprites, câmera inicial, arraste, busca, reverse geocoding, CORS/CSP, atribuição/logo e checkout. O admin confirmou o mesmo ponto no mapa híbrido. Android, origem/`User-Agent`, geolocalização concedida/timeout e chave substituta restrita ainda não foram validados. A chave usada foi exposta e deve ser rotacionada.

O smoke Web criou um pedido `PENDING_ADMIN_APPROVAL` e o painel autenticado o exibiu sem alterar
o ponto. Outro pedido controlado anterior também permanece pendente. **Não aprovar, preparar,
autorizar, reivindicar nem despachar nenhum deles.** IDs, coordenadas e credenciais de evidência
não precisam ser reproduzidos para executar o ambiente.
