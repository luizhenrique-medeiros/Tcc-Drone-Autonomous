# Desenvolvimento

## Ambiente

Windows 10/11, PowerShell, Python 3.13, Node, Docker Desktop e Flutter/Android SDK. WSL 2 é usado para SITL. O SDK Flutter pode existir em `./flutter` local, mas fica ignorado e não deve ser commitado.

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

### Flutter

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_all.ps1 -SkipBuilds
```

No Windows, o servidor de análise e o Gradle podem falhar quando o caminho absoluto contém acentos. Os scripts `bootstrap.ps1`, `start_mobile.ps1` e `test_all.ps1` detectam esse caso e reutilizam uma junção ASCII validada dentro do diretório temporário. Projeto, SDK e cache Pub continuam no mesmo disco, evitando a limitação de raízes diferentes do compilador Kotlin; não mova o repositório nem versione aliases locais.

Configuração Google/Android fica em arquivo local ignorado. O fallback de mapa é apenas desenvolvimento.

O script inicia com demonstração local por padrão. Para integração, configure a chave Android e execute:

```powershell
$env:GOOGLE_MAPS_ANDROID_API_KEY='chave-restrita-local'
.\scripts\start_mobile.ps1 -Integrated -GoogleMapsConfigured -ApiBaseUrl http://10.0.2.2:8000
```

Fora do debug local, a URL integrada deve usar HTTPS e uma distribuição exige keystore privado externo.

## Banco e seed

Compose habilita PostGIS pelo init. `alembic upgrade head` deve funcionar em banco vazio. Seed é idempotente; admin inicial só é criado com variáveis explícitas. Nunca use seed de demo em banco com evidência de voo sem revisão.

## Qualidade

Python: Ruff e Pytest. React: ESLint, testes e build TypeScript. Flutter: formatter, analyze, tests e APK debug quando SDK Android estiver disponível. Mudança de schema ganha migração; bug ganha regressão.

Com a stack simulada healthy, o smoke vertical reproduzível é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1
```

Ele persiste um cliente, pedido, missão, eventos e telemetria fake no banco local. Não o execute contra produção e não trate `COMPLETED` simulado como prova de entrega física.

## Fluxo Git

Branches `feature/...`/`fix/...`, commits Conventional Commits. Não versionar SDKs, APK, firmware, `.env`, banco, logs ou exportações locais. Antes de commit, revisar `git status` porque o repositório pode conter trabalho do usuário.

## Troubleshooting

- API `ready` falha: verificar Postgres, URL e migração.
- mapa vazio: verificar restrições da chave/manifest; não colocar a chave no Dart.
- admin CORS: incluir origem exata em `CORS_ORIGINS`.
- gateway sem heartbeat: validar modo/conexão e SITL antes do real.
- pre-arm: ler mensagem no Mission Planner; não desabilitar check.
- comando crítico timeout: preservar erro/evento e investigar link, sem retry infinito.
