# Plano de testes e evidências

## Camadas

1. **Unitário:** domínio, schemas, widgets/componentes e gateway fake; sem hardware.
2. **Integração local:** FastAPI + PostGIS, contratos frontend, WebSocket e exportador.
3. **Sistema `simulation`:** fluxo cliente → admin → gateway determinístico.
4. **SITL:** MAVLink real contra ArduPilot virtual.
5. **Bancada Pixhawk:** manual, inicialmente sem hélices.
6. **Voo controlado:** progressão manual com critérios e evidência.

Teste em camada inferior não comprova camada superior.

## Backend

Cobrir cadastro/login/RBAC, propriedade, pontos válidos/inválidos, PostGIS, dinheiro, submit/cancel, approve/reject/motivo, missão/versionamento/exportação/revisão, autorização separada/TTL/uso único, snapshot vencido/incompleto, idempotência, telemetria antiga/provenance, WebSocket e erros.

Em PostgreSQL isolado, executar `upgrade`, `alembic check`, `downgrade` e novo `upgrade`. Nunca testar downgrade destrutivo no banco do usuário sem backup.

## Mobile

Cobrir formulários, restauração/expiração da sessão, catálogo/carrinho, responsividade, busca/sem resultado, abertura direta sem endereço/GPS, MapLibre/pino central/coordenadas, confirmação de área, pagamento sem dado bancário, submit e estados de acompanhamento. MapTiler real requer testes separados com chave restrita e aparelho/navegador.

## Admin

Cobrir proteção de rota, fila/vazio/erro, detalhe/mapa, configuração MapTiler, loading/timeout/erro/retry/fallback, rota/marcadores/fit bounds, atribuição/logo, approve/reject, export/revisão, health stale/UNKNOWN/null, checklist, confirmação reforçada, idempotência, WebSocket/ACK/reconexão/coalescência, alertas/dedupe/cooldown, RTL e abortamento.

## MapTiler e MapLibre

- backend: contrato interno, URL externa codificada, ordem longitude/latitude, `language`, `limit`, `autocomplete`, país opcional e parser GeoJSON;
- segurança: chave de servidor ausente dos DTOs/erros/logs; chaves Web/Android separadas; estilo sem `?key=` no arquivo;
- erros: chave ausente, 403, 429, timeout, falha de rede, JSON/GeoJSON inválido, zero features e retry sem sucesso falso;
- Flutter Web: estilo/tiles, eventos de câmera, pino central, CORS, origem autorizada, atribuição/logo e fallback com `-WithoutMapTiler`;
- Android: mapa no emulador/aparelho, geolocalização, `User-Agent` observado e chave Android restrita;
- admin: MapLibre GL JS, estilo híbrido, rota/pontos, zoom/fit bounds, CSP/worker e fallback.

HTTP 200 do estilo ou da Geocoding API não prova renderização em browser/Android. Um build aprovado também não prova acesso a tiles, atribuição visível ou restrição correta da chave.

## Gateway

Cobrir configuração segura, fake, heartbeat, normalização, preflight, timeout, claim concorrente, autorização expirada, hash/versão, upload ACK/erro, releitura, mensagens de outro `sysid/compid`, versão do autopiloto, taxas de stream, telemetria ausente, reconexão, journal, abortamento e RTL.

Os testes Pymavlink usam conexão controlada em memória. Eles não abrem serial/UDP, não executam SITL e não se conectam a hardware.

## SITL

Registrar versão ArduPilot, comando, parâmetros não sensíveis e logs. Cenários: heartbeat, upload curto, início deliberado, chegada, retorno, perda de link, bateria/falha simulada, upload incorreto, abort/RTL e reconciliação. Rodar antes de Pixhawk.

## Hardware e voo

Registrar data, local controlado, operador, hardware/firmware, checklist, missão/hash, logs Mission Planner/TLOG/dataflash e resultado real. Progressão: comunicação → sensores → upload desarmado → motores sem hélices → voo manual → missão curta sem carga → RTL → carga leve/mecanismo → entrega e retorno.

## Evidência acumulada — atualizada em 2026-08-07

| Evidência | Estado comprovado | Limite |
|---|---|---|
| backend | Ruff/format e 28 testes | aviso de depreciação Starlette/httpx |
| gateway | Ruff/format e 31 testes | doubles; sem socket/SITL/hardware |
| admin | ESLint, 33 testes, build Vite e smoke visual autenticado com MapTiler real | Android e chave Web substituta/restrita continuam fora desta evidência |
| Flutter | format/analyze, 32 testes, build Web, smoke Chrome completo e APK debug configurado | APK não instalado; geolocalização concedida/timeout não exercitados |
| migrations/PostGIS | head, sem drift, ciclo upgrade/downgrade aprovado em banco temporário | avisos informativos de reflexão `geography` |
| Docker | imagens construídas; API/admin/DB healthy; gateway ativo | ambiente local, não produção |
| integração gateway/backend | heartbeat e polling `simulation` observados | nenhum pedido foi aprovado, autorizado ou despachado |
| MapTiler HTTP direto | estilo 200 (GL v8/40 layers), pesquisa 200 (3 features neste ensaio) e reverse 200 (1 feature) | a chave usada foi exposta e deve ser rotacionada |
| MapLibre Web | estilo/tiles/fontes/sprites 200, câmera inicial/zoom, arraste, busca/reverse, logo/atribuição e checkout confirmados no Chrome | chave temporária exposta; restrição de origem ainda não provada |
| MapLibre Android e GPS | APK debug compilado; no Web, estado de permissão bloqueada tratado sem impedir o mapa manual | exigem emulador/aparelho e matriz concedida/negada/timeout |
| auditoria Python | `PYSEC-2026-1845` encontrado no pytest 8.4.2; constraints de desenvolvimento atualizadas para `pytest>=9.0.3,<10`; suítes backend/gateway passaram e `pip-audit` final retornou zero vulnerabilidades conhecidas | risco era médio, ligado a `tmpdir` UNIX; repetir após alterar constraints/lock |
| auditoria npm de produção | zero vulnerabilidades conhecidas | fotografia de 2026-08-07; repetir antes de publicar |
| SITL/Mission Planner/Pixhawk/voo | não validado | exige evidência separada |

Total comprovado: **124 testes automatizados aprovados**. Artefato Android atual: `mobile/build/app/outputs/flutter-apk/app-debug.apk`, 190.538.195 bytes, SHA-256 `AF1328CB60E74CFF0D3A5CDE5A8527618F79FB2D55A9E1778061BE221285BE25`, assinatura Android Debug v2 verificada.

## Comandos

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\test_all.ps1 -SkipBuilds
docker compose --profile gateway config --quiet
docker compose --profile gateway up -d --build
docker compose exec -T backend alembic check
```

Depois de trocar todos os placeholders locais e rotacionar a conta existente:

```powershell
$env:ADMIN_INITIAL_PASSWORD='SENHA_LOCAL_ROTACIONADA'
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\integration_smoke.ps1 `
  -ConfirmSimulationMutation
```

O smoke cria registros identificados no banco local. Execute somente em loopback/simulação. Não registre um comando como aprovado se ele não terminou com exit code zero.
