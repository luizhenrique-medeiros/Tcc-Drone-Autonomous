# Build e execução

Comandos para Windows/PowerShell. O projeto usa uma única base Flutter em `mobile/` para Android e Web; `admin_web/` é o painel operacional separado.

Como a política do PowerShell pode bloquear scripts locais, os exemplos invocam scripts do repositório com:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script.ps1>
```

Isso altera apenas o processo iniciado; não muda a policy global da máquina.

## Pré-requisitos

- Docker Desktop e Docker Compose;
- Node.js 22+ (`npm.cmd` evita o wrapper `npm.ps1` quando a policy bloqueia scripts);
- Python 3.13 nos ambientes virtuais ou containers;
- Flutter/Dart compatíveis com `mobile/pubspec.yaml`;
- Chrome ou Edge para Flutter Web;
- Android SDK e JDK 17 para APK;
- `.env` local criado a partir de `.env.example`, sem segredos versionados.

O caminho do projeto possui caracteres acentuados. Os scripts Flutter usam a junção ASCII temporária fornecida pelo repositório.

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

Antes de qualquer fluxo administrativo completo, confirme que o `.env` local não contém placeholders. A rodada de 2026-08-07 regenerou os segredos e reconciliou a senha administrativa; não copie os valores para documentação ou terminal.

O gateway não sobe no perfil padrão. Para `simulation`:

```powershell
docker compose --profile gateway up -d --build
```

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
..\flutter\bin\flutter.bat pub get
..\flutter\bin\flutter.bat run -d chrome `
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
..\flutter\bin\flutter.bat build web --release
..\flutter\bin\flutter.bat build web --wasm --dry-run
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
..\flutter\bin\flutter.bat pub get
..\flutter\bin\dart.bat format --output=none --set-exit-if-changed lib test
..\flutter\bin\flutter.bat analyze
..\flutter\bin\flutter.bat test
..\flutter\bin\flutter.bat build apk --debug --dart-define=DEMO_MODE=true
```

Artefato debug esperado:

```text
mobile/build/app/outputs/flutter-apk/app-debug.apk
```

O build release pode verificar compilação, mas distribuição/instalação exige keystore externo e credenciais do ambiente:

```powershell
..\flutter\bin\flutter.bat build apk --release
```

O APK debug atual foi recompilado depois da migração, com MapTiler e perfil `android_emulator`: 190.538.195 bytes, SHA-256 `AF1328CB60E74CFF0D3A5CDE5A8527618F79FB2D55A9E1778061BE221285BE25` e assinatura Android Debug v2 verificada. Ele ainda precisa ser instalado e executado em emulador/aparelho. Não há um APK release atual nem keystore privada configurada para distribuição.

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
  -File .\scripts\start_gateway.ps1
```

O padrão é `MAVLINK_MODE=simulation`. Para SITL/hardware, siga [MISSION_PLANNER_SETUP.md](MISSION_PLANNER_SETUP.md); mudar apenas a variável de modo não configura topologia, IDs ou checklist.

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
  -File .\scripts\test_all.ps1
```

Use `-SkipBuilds` para ciclo rápido. Registre exit code, contagens, artefatos e hashes em [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md). Não reutilize contagens/hashes de uma bateria anterior depois de alterar código.

## Evidência confirmada após a migração de mapas

Em 2026-08-07:

- backend aprovou Ruff/formatação e 28 testes; gateway aprovou Ruff/formatação e 31 testes;
- o admin aprovou lint, 33 testes, build Vite e smoke visual autenticado com MapLibre GL JS;
- o Flutter aprovou formatação/analyze, 32 testes, build Web configurado, smoke Chrome completo e build APK debug configurado;
- requests HTTP diretos retornaram estilo MapTiler 200 (GL v8/40 layers), pesquisa 200 (3 features naquele ensaio) e reverse geocoding 200 (1 feature naquele ensaio);
- `pip-audit` encontrou `PYSEC-2026-1845` no pytest 8.4.2; depois de elevar as constraints de desenvolvimento do backend/gateway para `pytest>=9.0.3,<10`, ambas as suítes passaram e o audit final retornou zero vulnerabilidades conhecidas;
- `npm audit` das dependências de produção do admin retornou zero vulnerabilidades conhecidas.

O smoke Flutter Web confirmou estilo/tiles/fontes/sprites, câmera inicial, arraste, busca, reverse geocoding, CORS/CSP, atribuição/logo e checkout. O admin confirmou o mesmo ponto no mapa híbrido. Android, origem/`User-Agent`, geolocalização concedida/timeout e chave substituta restrita ainda não foram validados. A chave usada foi exposta e deve ser rotacionada.

O smoke Web criou o pedido `92198217-c06b-41f5-b91e-61b985b86803`, `PENDING_ADMIN_APPROVAL`, nas coordenadas `-23.117843,-46.554947`, e o painel autenticado o exibiu sem alterar o ponto. O pedido controlado anterior `27207fa7-df70-45b5-bb2f-d9279a0347f8` também permanece pendente. **Não aprovar, autorizar nem despachar nenhum deles.**
