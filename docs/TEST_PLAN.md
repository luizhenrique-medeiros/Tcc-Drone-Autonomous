# Plano de testes e evidências

## Camadas

1. **Unitário:** domínio, schemas, widgets/componentes, fake gateway; sem rede/banco real.
2. **Integração:** FastAPI + banco PostGIS isolado, contratos frontend e exportador.
3. **Sistema fake:** fluxo cliente→admin→gateway determinístico.
4. **SITL:** MAVLink real contra ArduPilot virtual.
5. **Bancada Pixhawk:** manual, inicialmente sem hélices.
6. **Voo controlado:** progressão manual com critérios e evidência.

## Backend

Cadastro/login/RBAC; propriedade; pontos válidos/inválidos/segunda etapa/cobertura/PostGIS; dinheiro; submit/cancel; approve/reject/motivo; missão/versionamento/exportação/revisão; autorização separada/TTL/uso único/saúde vencida; transições concorrentes; auditoria/idempotência; telemetria antiga; WebSocket e erros.

## Mobile

Formulários, catálogo/carrinho, responsividade, permissão, busca/sem resultado, duas etapas, satélite, marcador/coordenadas, confirmação/erro/restauração, pagamento sem dado bancário, submit e todos os estados. Golden tests somente para componentes/telas estáveis e revisados manualmente.

## Admin

Proteção de rota, fila/vazio/erro, detalhe/mapa, diferença aproximado/final, approve/reject, bloqueio de edição, export/revisão, health stale, checklist, confirmação reforçada, duplo clique, autorização, WebSocket/reconexão, RTL/abort e catálogo dev protegido.

## Gateway

Config segura, fake, heartbeat, parsing/normalização, preflight, timeout, claim concorrente, autorização expirada, hash/versão, upload ACK/erro, releitura, duplicidade, telemetria, reconexão, missão consumida, abortamento e RTL. Parte dos testes instancia o adaptador Pymavlink com conexão controlada em memória para verificar o protocolo; eles não abrem socket, não executam SITL e não se conectam a hardware.

## SITL

Registrar versão ArduPilot, comando, parâmetros não sensíveis e logs. Cenários: conexão/heartbeat, upload curto, início deliberado, chegada, retorno, perda de link simulada, bateria/falha simulada, upload incorreto, abort/RTL e reconciliação. Rodar tudo antes de Pixhawk.

## Hardware e voo

Evidência manual deve identificar data, local controlado, operador, hardware/firmware, checklist, missão/hash, log Mission Planner, vídeo/foto quando permitido e resultado real. Progressão: comunicação → sensores → upload desarmado → motores sem hélices → voo manual → missão curta sem carga → RTL → carga leve/mecanismo → entrega e retorno.

## Matriz de estado atual — 2026-08-06

| Evidência | Estado comprovado | Limite |
|---|---|---|
| código do protótipo | **implementado e revisado localmente** | não equivale a homologação operacional |
| backend | **Ruff, format, `pip check` e 11 testes aprovados** | 1 aviso de depreciação Starlette/httpx no ambiente de teste |
| gateway | **Ruff, format, `pip check` e 28 testes aprovados** | Pymavlink controlado em memória; sem socket/SITL/hardware |
| painel admin | **ESLint, 11 testes e build Vite aprovados** | sem automação em navegador real |
| aplicativo Android | **format, analyze e 12 testes aprovados; APK debug gerado** | APK não instalado em aparelho/emulador nesta rodada |
| migrações/PostGIS | **upgrade, ausência de drift, downgrade e novo upgrade aprovados em banco limpo** | reflexão de `geography` gera aviso informativo do SQLAlchemy |
| imagens Docker | **backend, admin e gateway construídos; quatro serviços healthy** | validação local, não implantação de produção |
| fluxo integrado fake | **`COMPLETED`, 13 eventos e 5 amostras de telemetria** | determinístico; não comprova deslocamento nem entrega física |
| Google Maps/GPS | **integração implementada** | não validada com chave real, rede móvel ou GPS de aparelho |
| SITL | **não validado** | exige suíte separada com versão e log ArduPilot |
| Pixhawk 6C | **não validada** | exige checklist e log de bancada, inicialmente sem hélices |
| voo real | **não validado** | exige evidência de missão controlada completa |

O build Android comprovado é de demonstração/debug em `mobile/build/app/outputs/flutter-apk/app-debug.apk`: 154.917.450 bytes, SHA-256 `612652F2D24272F3693CF6615BCAC26A128F5730A50DB1E26C7657365764530D`. A transição `DELIVERY_CONFIRMED` no fake significa apenas que a etapa lógica do mecanismo foi alcançada; não confirma que um pacote foi fisicamente entregue.

O `npm audit` registrou duas ocorrências altas do mesmo aviso `GHSA-qwww-vcr4-c8h2` em `react-router`/`react-router-dom`. O cenário descrito exige RSC Actions, recurso ausente neste painel Vite puramente client-side; ainda assim, o alerta permanece risco residual acompanhado, e não foi ocultado nem “corrigido” com downgrade que reintroduziria vulnerabilidades antigas.

## Comandos

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\test_all.ps1 -SkipBuilds
docker compose --profile gateway config
docker compose --profile gateway up -d --build
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\integration_smoke.ps1
```

O script `scripts/test_all.ps1` executa os grupos locais disponíveis e falha se um grupo executado falhar. Em caminhos Windows com acento, ele usa uma junção ASCII validada no diretório temporário para manter projeto, SDK e cache Pub no mesmo disco. O smoke integrado cria registros identificados por e-mail único no banco local; execute-o somente em ambiente de desenvolvimento/simulação.
