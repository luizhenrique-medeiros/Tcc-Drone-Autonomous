# Ações manuais necessárias

Esta lista contém apenas etapas que dependem de conta, credencial, rede, software externo ou hardware. Uma implementação ou build aprovado não conclui essas etapas.

## Estado das credenciais locais

Banco, JWT e gateway possuem valores locais no `.env` ignorado. `/health`, `/ready` e `/docs`
respondem 200, porém a senha `ADMIN_INITIAL_PASSWORD` atual não corresponde ao hash da conta
persistida: o login retorna `401`. Isso não indica banco vazio. Obtenha a senha vigente ou peça
autorização explícita antes de rotacionar; não copie qualquer valor para Git, documentação,
screenshots ou histórico.

Para uma rotação futura, use:

```powershell
docker compose exec backend python scripts/rotate_admin_password.py `
  --email admin@example.local
```

O comando solicita a senha sem expô-la na linha de comando. Execute qualquer smoke mutante somente em ambiente local de simulação:

```powershell
$env:ADMIN_INITIAL_PASSWORD='SENHA_LOCAL_ROTACIONADA'
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\integration_smoke.ps1 `
  -ConfirmSimulationMutation
```

Não use `change_me` nem enfraqueça a proteção do script.

Os pedidos controlados `27207fa7-df70-45b5-bb2f-d9279a0347f8` e `92198217-c06b-41f5-b91e-61b985b86803` permanecem `PENDING_ADMIN_APPROVAL`. **Não os aprove, não prepare missão, não autorize voo e não os despache.** Eles existem apenas como evidência de integração/persistência.

## Prioridade 1 — rotacionar e restringir MapTiler

A credencial recebida foi exposta em conversa. Requests diretos e o smoke Web real responderam corretamente em 2026-08-07, mas isso não torna a chave segura nem valida Android.

Crie chaves substitutas antes de revogar a exposta:

| Variável | Superfície | Proteção necessária |
|---|---|---|
| `MAPTILER_WEB_API_KEY` | Flutter Web e admin | origens exatas de `localhost`/`127.0.0.1` nas portas 5173/5174 e depois somente domínios publicados |
| `MAPTILER_ANDROID_API_KEY` | APK Flutter | chave separada; observar e validar o `User-Agent` real do aparelho antes de aplicar a restrição |
| `MAPTILER_SERVER_API_KEY` | FastAPI/Search API | nunca enviar ao cliente; em hospedagem, considerar credencial de serviço assinada |

Mantenha também:

```env
MAP_PROVIDER=maptiler
MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json
```

`MAPTILER_STYLE_URL` não recebe `?key=`. Não use uma URL completa como valor de `*_API_KEY`. O projeto usa o style JSON no MapLibre; não use o visualizador em `iframe` e não habilite Static Maps. No plano Free, atribuição MapTiler/OpenStreetMap e logo MapTiler linkado são obrigatórios.

Depois:

1. grave cada valor somente no `.env` local/secret store;
2. configure quotas/alertas e as restrições correspondentes;
3. reconstrua backend/admin e reinicie o Flutter com `-MapTilerConfigured`;
4. valide separadamente Flutter Web, admin e Android;
5. confira requests/erros no painel MapTiler;
6. revogue a chave exposta;
7. confirme que nenhum valor apareceu em logs, relatórios, screenshots, histórico ou commit.

Dados externos ainda necessários: origens/domínios finais, `User-Agent` Android realmente observado, ambiente de hospedagem do backend e quotas escolhidas.

## Prioridade 2 — revalidar Flutter Web após trocar a chave

Com API/admin ativos:

```powershell
docker compose up -d --build db backend admin
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1
```

Acesse:

- cliente Flutter Web: `http://localhost:5174`;
- admin React: `http://localhost:5173`;
- FastAPI/OpenAPI: `http://localhost:8000/docs`.

O ensaio visual de 7 de agosto confirmou cadastro/login, produtos, carrinho, pesquisa por Atibaia, mapa híbrido, câmera inicial, pan, reverse geocoding, confirmação segura, PIX simulado, criação do pedido e visualização no admin. Na rodada atual, admin/Flutter Web e assets responderam 200, os headers do admin e o MIME do worker foram conferidos, mas o controlador visual do navegador estava indisponível. Depois de instalar as chaves substitutas restritas e resolver o login admin, repita a validação e complete os cenários não cobertos:

1. login em larguras de celular e desktop, sem overflow horizontal;
2. mapa MapLibre real com estilo híbrido MapTiler, atribuição e logo visíveis;
3. pan/zoom livre e navegação entre continentes;
4. busca mundial e debounce;
5. pino fixo no centro e coordenada atualizada ao parar a câmera;
6. localização concedida, negada, desativada, timeout e navegador sem suporte;
7. tela `/debug` ou atalho de perfil em build debug, sem chave/JWT expostos;
8. hot reload pressionando `r` no terminal do Flutter.

Não marque mapas como aprovados com chave ausente, 403/429, timeout, CORS/CSP, falha de estilo/tiles ou fallback. Não confirme ponto nem pedido pela UI usando `-WithoutMapTiler`; esse modo serve somente aos estados locais de desenvolvimento.

## Prioridade 3 — rede local e Android físico

1. Descubra o IPv4 do computador que executa Docker.
2. Confirme que computador e celular estão na mesma rede privada sem isolamento de clientes.
3. Use `API_BIND_ADDRESS=0.0.0.0` somente durante o ensaio em LAN.
4. Passe `http://IP_DO_PC:8000` ao perfil `android_physical_device`.
5. Adicione origens Web LAN exatas ao CORS e à lista de origens permitidas da chave Web MapTiler apenas se o navegador for aberto em outro dispositivo.
6. Se necessário, libere TCP 8000 no Firewall do Windows somente para perfil/sub-rede privados.
7. Teste `http://IP_DO_PC:8000/health` no celular antes de abrir o app.
8. Recolha o bind para `127.0.0.1` quando o teste terminar.

Detalhes: [LOCAL_NETWORK_SETUP.md](LOCAL_NETWORK_SETUP.md).

## Prioridade 4 — SITL

Neste computador, `wsl --list --verbose` mostrou apenas a distribuição interna `docker-desktop`; não há uma distribuição Linux de desenvolvimento nem ArduPilot/MAVProxy instalados. Portanto, SITL ainda não pode ser executado.

1. Instale uma distribuição Ubuntu no WSL 2 e o ArduPilot conforme a documentação oficial.
2. Inicie SITL pelo procedimento documentado.
3. Configure `MAVLINK_MODE=sitl`, URL UDP e IDs realmente observados.
4. Mantenha `ALLOW_MISSION_START=false` no primeiro teste de conexão e telemetria.
5. Registre heartbeat, versão, GPS, EKF, bateria simulada, home e taxas de mensagens.
6. Teste upload, releitura e hash da missão sem declarar voo físico.
7. Habilite início somente em sessão deliberada e valide RTL, perda de link e reconciliação.

## Prioridade 5 — Mission Planner e Pixhawk em bancada

Antes de iniciar, confirme hardware, firmware, frame, topologia do link, porta/baud, `sysid`/`compid`, alimentação e parâmetros já existentes. Não altere parâmetros automaticamente.

Evidência anterior da rodada: após liberar a COM7/57600, dois diagnósticos passivos receberam
heartbeat real `sysid=1`, `compid=1`, modo `STABILIZE` e `armed=false`; um ciclo limitado publicou
sete heartbeats no backend sem escrita MAVLink. O forwarding não foi validado.

Estado atual: a COM7 não está enumerada; o dispositivo PnP aparece somente como histórico/estado
desconhecido, o Mission Planner está fechado e não há listeners UDP 14550/14551. O diagnóstico
passivo retorna exit 2/`VEHICLE_PORT_NOT_FOUND`, e o backend preserva snapshot `HARDWARE_REAL`,
`ERROR`, `direct`, COM7/57600 com upload/comandos/início falsos.

1. execute [PREFLIGHT_CHECKLIST.md](PREFLIGHT_CHECKLIST.md);
2. remova as hélices;
3. reconecte o cabo/link e confirme no Gerenciador de Dispositivos que a porta COM7 voltou;
4. para serial direta, mantenha Mission Planner fechado e execute somente `scripts\start_gateway.ps1 -DiagnoseOnly`;
5. para forwarding, abra o Mission Planner, desabilite o AutoConnect **Mavlink alt port** UDP 14551 `Inbound` e conecte em `COM7`, `57600`;
6. abra `SETUP` → `Advanced` → `Mavlink Mirror`, escolha **UDP Client**, `127.0.0.1`, porta `14551`, com **Write access** desmarcado;
7. execute `scripts\start_gateway.ps1 -DiagnoseOnly` e confirme heartbeat no gateway;
8. valide GPS, EKF, bateria, home e pre-arm no Inspector e no admin;
9. confira no admin origem `HARDWARE_REAL`, timestamps e campos ausentes honestos;
10. somente em outra sessão, depois de SITL/checklist, habilite Write access + ACK/upload, mantendo comandos/start falsos;
11. exporte, revise, envie, aguarde ACK e releia/compare a missão sem iniciar voo;
12. preserve TLOG/dataflash, eventos e logs.

## Prioridade 6 — APK físico

O APK debug integrado atual está em `mobile/build/app/outputs/flutter-apk/app-debug.apk`:
195.236.488 bytes e SHA-256
`202C72EE6397D6F5EE19012C08C2DE7E67FAD5FE18D60583CAB9B9D7C3EE9B6F`.
Foi compilado com API 37, AGP 9.1.1 e Gradle 9.3.1, mas não foi instalado nesta rodada. Não há
release atual nem keystore privada configurada.

1. Crie/forneça um keystore release fora do repositório e configure aliases/senhas por mecanismo secreto local.
2. Observe o `User-Agent` realmente enviado pelo APK assinado ao MapTiler e valide a regra antes de restringir a chave Android.
3. Configure URL LAN e `MAPTILER_ANDROID_API_KEY` separada/restrita.
4. Gere e verifique um novo APK assinado; registre tamanho, SHA-256 e resultado da verificação de assinatura.
5. Instale em aparelho compatível.
6. Valide login, catálogo, mapa real, ponto sem endereço, pedido e acompanhamento.
7. Teste perda/retorno da rede.
8. Registre aparelho, Android, build e resultado antes de afirmar que foi testado.

## Bloqueios externos atuais

- a chave MapTiler recebida foi exposta e ainda precisa ser substituída/revogada;
- Flutter Web deve ser revalidado depois da chave substituta restrita; Android ainda não teve runtime manual;
- origens Web finais e `User-Agent` Android ainda precisam ser confirmados no painel MapTiler;
- falta keystore para produzir APK release assinado/implantável;
- os pedidos controlados `27207fa7-df70-45b5-bb2f-d9279a0347f8` e `92198217-c06b-41f5-b91e-61b985b86803` devem permanecer sem despacho;
- a COM7 foi validada anteriormente por heartbeat real, mas está ausente agora; o forwarding 14551 ainda depende da configuração manual acima;
- SITL depende da instalação de uma distribuição WSL 2 e do ArduPilot;
- novo heartbeat no estado atual, GPS/bateria/EKF/home pelo gateway, upload na Pixhawk, motores, armamento e voo permanecem não executados.
