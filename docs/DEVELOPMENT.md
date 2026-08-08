# Desenvolvimento

## Ambiente

Windows 10/11, PowerShell, Python 3.13, Node, Docker Desktop, Flutter, Chrome e Android SDK. WSL 2 é usado para SITL. O SDK Flutter pode existir em `./flutter` local, mas fica ignorado e não deve ser commitado.

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
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_all.ps1 -SkipBuilds
```

No Windows, o servidor de análise e o Gradle podem falhar quando o caminho absoluto contém acentos. Os scripts `bootstrap.ps1`, `start_mobile.ps1` e `test_all.ps1` detectam esse caso e reutilizam uma junção ASCII validada dentro do diretório temporário. Projeto, SDK e cache Pub continuam no mesmo disco, evitando a limitação de raízes diferentes do compilador Kotlin; não mova o repositório nem versione aliases locais.

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
- pre-arm: ler mensagem no Mission Planner; não desabilitar check.
- comando crítico timeout: preservar erro/evento e investigar link, sem retry infinito.
