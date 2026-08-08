# Execução em localhost e rede local

Por padrão, Docker publica banco, API e admin somente em `127.0.0.1`. Isso reduz exposição acidental. Abra a API na LAN somente quando um Android físico ou outro navegador precisar alcançá-la.

## Portas padronizadas

| Serviço | Porta | Consumidores |
|---|---:|---|
| FastAPI | 8000 | Flutter Android/Web, admin e gateway |
| admin React | 5173 | navegador do operador |
| Flutter Web | 5174 | navegador do cliente |
| PostgreSQL | 5432 | backend; não exponha ao celular |
| MAVLink UDP | 14550/UDP | gateway em SITL/forwarding |

Android e Web compartilham o mesmo código Flutter em `mobile/`. Somente a URL da API muda por plataforma:

| Perfil | URL da API |
|---|---|
| `local_web` | `http://localhost:8000` |
| `android_emulator` | `http://10.0.2.2:8000` |
| `android_physical_device` | `http://IP_DO_PC:8000` |
| `hosted` | URL HTTPS publicada |

`10.0.2.2` é um alias do host no emulador Android; ele não serve para Chrome local nem para celular físico.

## Localhost recomendado

```powershell
docker compose up -d --build db backend admin
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1
```

URLs:

- API/OpenAPI: `http://localhost:8000/docs`;
- admin: `http://localhost:5173`;
- cliente Flutter Web: `http://localhost:5174`;
- diagnóstico Flutter debug: `http://localhost:5174/#/debug` ou rota `/debug`, conforme a estratégia de URL do navegador.

O launcher Web carrega somente `MAPTILER_WEB_API_KEY`, `MAPTILER_STYLE_URL` e a porta necessárias do `.env`, usa `local_web`, passa a API local correta e mantém hot reload. Se a porta estiver ocupada, ele interrompe com PID/porta em vez de iniciar em uma URL inesperada.

Em 2026-08-07, o Flutter Web local em `localhost` concluiu cadastro/login, produtos, carrinho, busca, mapa híbrido MapTiler, seleção do ponto, checkout e criação do pedido. Estilo, tiles, fontes, sprites, reverse geocoding, logo e atribuição foram observados no Chrome. Isso valida o loopback local, não acesso a partir de outro dispositivo na LAN nem Android.

O fluxo Web criou o pedido `92198217-c06b-41f5-b91e-61b985b86803`, `PENDING_ADMIN_APPROVAL`, nas coordenadas `-23.117843,-46.554947`; o admin autenticado exibiu o ponto no mapa real. O pedido controlado anterior `27207fa7-df70-45b5-bb2f-d9279a0347f8` também permanece pendente. **Não aprovar, autorizar ou despachar nenhum deles.**

O CORS local deve conter as origens exatas:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174
```

## Descobrir o IPv4 do computador

```powershell
Get-NetIPConfiguration |
  Where-Object { $_.IPv4DefaultGateway } |
  Select-Object InterfaceAlias,IPv4Address,IPv4DefaultGateway
```

Escolha o IPv4 da interface Wi-Fi/Ethernet na mesma rede do celular. Não use IP de VPN, Docker, WSL, APIPA (`169.254.*`) ou endereço público.

## Abrir somente a API na LAN

No `.env` local:

```env
API_BIND_ADDRESS=0.0.0.0
ADMIN_BIND_ADDRESS=127.0.0.1
DATABASE_BIND_ADDRESS=127.0.0.1
MOBILE_API_BASE_URL=http://192.168.X.Y:8000
MOBILE_ALLOW_INSECURE_LAN_HTTP=true
```

Substitua `192.168.X.Y` pelo IP observado. Depois:

```powershell
docker compose up -d --build backend admin
docker compose ps
```

Teste no computador e no celular:

```text
http://192.168.X.Y:8000/health
```

`/health` deve retornar HTTP 200 se o processo está ativo. `/ready` também deve retornar 200 quando o banco estiver pronto.

## Executar Flutter no Android físico

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile.ps1 `
  -Integrated `
  -TargetProfile android_physical_device `
  -ApiBaseUrl http://192.168.X.Y:8000 `
  -AllowInsecureLanHttp `
  -MapTilerConfigured
```

HTTP sem TLS é aceito apenas em build debug e com consentimento explícito para LAN. Para rede externa ou build publicado, use HTTPS.

CORS não se aplica ao APK nativo. Ele se aplica ao Flutter Web e ao admin.

## Flutter Web acessado por outro dispositivo

Acrescente a origem exata do navegador ao `.env`:

```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://192.168.X.Y:5174
```

Adicione também a origem `http://192.168.X.Y:5174` à lista de origens permitidas da chave Web MapTiler. O servidor de desenvolvimento precisa escutar na LAN; para esse caso deliberado, prefira o launcher do projeto. Se for necessário executar manualmente o mesmo Flutter como `web-server`:

```powershell
cd mobile
..\flutter\bin\flutter.bat run -d web-server `
  --web-hostname 0.0.0.0 `
  --web-port 5174 `
  --dart-define=APP_ENVIRONMENT=demo_network `
  --dart-define=API_BASE_URL=http://192.168.X.Y:8000 `
  --dart-define=ALLOW_INSECURE_LAN_HTTP=true `
  --dart-define=DEMO_MODE=false `
  --dart-define=MAP_PROVIDER=maptiler `
  --dart-define=MAPTILER_CONFIGURED=true `
  --dart-define=MAPTILER_STYLE_URL=$env:MAPTILER_STYLE_URL `
  --dart-define=MAPTILER_WEB_API_KEY=$env:MAPTILER_WEB_API_KEY
```

Não substitua a referência de ambiente por uma chave literal. `MAPTILER_STYLE_URL` deve ser a URL HTTPS de `style.json` sem query. Expor o Web server em `0.0.0.0` deve ser temporário e limitado à rede privada.

## Firewall do Windows

Primeiro teste a conexão. Se bloqueada, crie manualmente uma regra de entrada TCP 8000, perfil **Privado**, limitada à sub-rede local. Para compartilhar o servidor Web, a porta 5174 também pode precisar de regra igualmente restrita.

Não abra PostgreSQL 5432, MAVLink ou portas de desenvolvimento no perfil Público. O repositório não altera o firewall automaticamente.

## Diagnóstico

```powershell
Test-NetConnection 127.0.0.1 -Port 8000
Test-NetConnection 127.0.0.1 -Port 5173
Test-NetConnection 127.0.0.1 -Port 5174
Get-NetTCPConnection -LocalPort 8000,5173,5174 -State Listen
docker compose logs --tail=100 backend admin
```

Na tela debug do Flutter, confira:

- `API URL` correspondente ao perfil;
- `Backend reachable`;
- `WebSocket reachable`;
- estilo/tiles MapTiler e busca pelo backend separadamente;
- modo de build e plataforma;
- apenas presença de sessão, nunca o token.

Checklist:

- celular e PC na mesma rede;
- sem isolamento de cliente/AP no Wi-Fi;
- IP não mudou por DHCP;
- `API_BIND_ADDRESS=0.0.0.0` aplicado após recriar o container;
- firewall no perfil correto;
- URL do Android físico usa IP do PC, não `localhost` ou `10.0.2.2`;
- WebSocket deriva `ws://IP:8000/api/v1` da URL HTTP;
- cada origem Web está no CORS do backend e na lista de origens permitidas da chave Web MapTiler;
- o APK usa a chave Android separada e seu `User-Agent` real foi observado antes da restrição;
- o backend usa somente `MAPTILER_SERVER_API_KEY`, sem enviá-la ao cliente.

## Ao terminar

Quando acesso LAN não for mais necessário:

1. restaure `API_BIND_ADDRESS=127.0.0.1`;
2. remova origens MapTiler/CORS temporárias;
3. encerre o servidor Web exposto;
4. remova regras temporárias do firewall, se criadas.

Não publique banco ou MAVLink diretamente na internet. Túnel/VPN não substitui autenticação, CORS, TLS e restrições de chave.
