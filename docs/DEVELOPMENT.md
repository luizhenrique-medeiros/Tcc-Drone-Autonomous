# Desenvolvimento

## Ambiente

Windows 10/11, PowerShell, Python 3.13, Node, Docker Desktop, Flutter, Chrome e Android SDK. WSL 2 é usado para SITL. O SDK Flutter pode existir em `./flutter` local, mas fica ignorado e não deve ser commitado.

Fotografia de 17 de agosto de 2026: Python 3.13.15, Node 24.19.0, npm 11.17.0,
Docker Desktop 4.86.0/Engine 29.7.2, Git 2.55.0.windows.3, Android Studio 2026.1.3,
Android API 37, AGP 9.1.1 e Gradle 9.3.1. O SDK oficial global é Flutter 3.47.0/Dart 3.13.0.
Os scripts resolvem `-FlutterSdkRoot` → `FLUTTER_ROOT` → `PATH` e validam canal `stable`,
Flutter 3.47.x e Dart 3.13.x. `./flutter` requer `-AllowBundledFlutterSdk` explícito e o fork
pré-release presente nesta máquina é rejeitado. Sempre registre caminho e `--version` do binário.
Se a ExecutionPolicy impedir a chamada direta, execute-os com
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script.ps1>`; o bypass vale apenas para
o processo iniciado.

## Primeira execução

```powershell
Copy-Item .env.example .env
docker compose config
docker compose up --build
```

Inclua o gateway simulado no fluxo vertical com `docker compose --profile gateway up --build`.

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
do Kotlin Gradle Plugin vem do pacote `maplibre_gl`, não de falha do APK atual.

A configuração de mapas usa `MAP_PROVIDER=maptiler`, `MAPTILER_STYLE_URL` e chaves MapTiler separadas para Web, Android e servidor. Todos os valores ficam no ambiente ou em arquivo local ignorado. A chave recebida na migração foi exposta e precisa ser rotacionada; não a copie para comandos, logs ou Git. O fallback de mapa é apenas desenvolvimento.

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

Na rodada atual, backend e gateway retornaram zero vulnerabilidades conhecidas; os pacotes locais
do próprio projeto foram ignorados pelo auditor. `npm.cmd audit` completo e de produção também
retornou zero.

As imagens atuais são `postgis/postgis:17-3.5`, `python:3.13-slim`, `node:24-alpine` e
`nginx:1.28.3-alpine`. Tags são mutáveis: registre o digest observado em cada auditoria e não
confunda um pull/build aprovado com validação funcional da aplicação.

Com a stack simulada healthy, o smoke vertical reproduzível é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1 -ConfirmSimulationMutation
```

Ele persiste um cliente, pedido, missão, eventos e telemetria fake no banco local. Não o execute contra produção e não trate `COMPLETED` simulado como prova de entrega física.

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
- `COM7` ausente: reconectar cabo/link e confirmar a enumeração antes de executar o diagnóstico;
  no estado final de 17 de agosto não havia porta serial nem listeners UDP 14550/14551.
- pre-arm: ler mensagem no Mission Planner; não desabilitar check.
- comando crítico timeout: preservar erro/evento e investigar link, sem retry infinito.
