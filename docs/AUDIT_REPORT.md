# Relatório de auditoria técnica

- Auditoria original: 6 de agosto de 2026
- Atualização de arquitetura e segurança: 7 de agosto de 2026
- Branch inspecionada: `review-and-upgrade`

> **Status histórico:** as conclusões originais sobre o provedor de mapas foram superadas pela migração MapTiler/MapLibre. Este documento separa requests HTTP diretos do smoke visual Web realizado depois deles. O resumo legado do provedor anterior permanece apenas em [GOOGLE_MAPS_SETUP.md](GOOGLE_MAPS_SETUP.md).

## Escopo e critério de evidência

A auditoria cobriu código, testes, configurações, migrações, scripts e documentação de `backend`, `drone_gateway`, `mobile`, `admin_web`, raiz e infraestrutura. Artefatos gerados, dependências instaladas e ambientes virtuais não foram tratados como fonte.

O cliente continua sendo **uma única aplicação Flutter em `mobile/` para Android e Web**. `admin_web/` permanece uma aplicação React separada. Nenhum cliente Web paralelo foi criado.

As conclusões distinguem:

1. implementação presente;
2. teste automatizado com doubles;
3. request HTTP direto a serviço externo;
4. execução visual/integrada em browser ou Android;
5. ArduPilot SITL/Mission Planner;
6. Pixhawk ou drone físico.

Um nível não comprova o seguinte. Em particular, HTTP 200 de estilo/geocoding não comprova tiles completos, MapLibre no cliente, origem/`User-Agent`, CORS/CSP, geolocalização ou seleção final.

## Resultado executivo atualizado

A base funcional preserva autenticação e papéis, PostGIS, pedidos persistidos, separação entre aprovação comercial e autorização de voo, missão versionada, WebSocket autenticado e gateway isolado. O modo `simulation` continua sendo evidência lógica, não evidência de voo.

A integração de mapas vigente é:

| Superfície | Implementação | Limite atual |
|---|---|---|
| Flutter Android/Web | `maplibre_gl` com estilo híbrido MapTiler, pino central e eventos de câmera | Web validado no Chrome; Android runtime pendente |
| admin React | MapLibre GL JS, rota/pontos, fit bounds/zoom, loading/erro/retry/fallback | 33 testes/lint/build e smoke visual autenticado aprovados |
| FastAPI | proxy autenticado para MapTiler Geocoding API | fluxo Flutter Web completo aprovado; chave substituta de servidor pendente |

O projeto usa `hybrid-v4/style.json`, não o visualizador em `iframe`. O admin não usa Static Maps. Atribuição MapTiler/OpenStreetMap e logo MapTiler do plano Free permanecem obrigatórios.

## Credenciais e exposição

A chave recebida para a migração foi exposta em conversa. Ela deve ser substituída antes de apresentação pública:

- `MAPTILER_WEB_API_KEY`: chave cliente observável, restrita pelas origens Web exatas;
- `MAPTILER_ANDROID_API_KEY`: chave cliente extraível do APK, separada e restringida somente depois de observar/validar o `User-Agent` real;
- `MAPTILER_SERVER_API_KEY`: somente FastAPI, nunca enviada ao cliente; em hospedagem, considerar credencial de serviço assinada;
- `MAPTILER_STYLE_URL`: URL HTTPS de `style.json` sem query ou credencial.

Nenhuma chave deve entrar em documentação, screenshot, log, histórico de terminal ou Git. A chave exposta deve ser revogada depois de testar as substitutas.

## Evidência confirmada em 2026-08-07

### MapTiler HTTP direto

| Chamada | Resultado observado | Conclusão permitida |
|---|---|---|
| estilo híbrido | HTTP 200, documento GL v8, 40 layers | o estilo respondeu naquele request |
| pesquisa | HTTP 200, 3 features naquele ensaio | a Search API respondeu àquela consulta |
| reverse geocoding | HTTP 200, 1 feature naquele ensaio | a Search API respondeu àquela coordenada |

A credencial não é reproduzida. Esses resultados diretos não validam, por si sós, browser, Android ou fluxo completo; a camada Web foi testada separadamente abaixo.

### Flutter Web

O release integrado foi aberto no Chrome em `http://localhost:5174`. Cadastro/login, catálogo, carrinho, pesquisa por Atibaia, resolução, estilo híbrido, tiles, fontes, sprites, câmera inicial em zoom 18, arraste, reverse geocoding, confirmação de área segura, PIX simulado e criação do pedido foram observados sem erro de runtime. Atribuição MapTiler/OpenStreetMap e logo estavam visíveis. O estado de geolocalização bloqueada teve fallback manual funcional; permissão concedida e timeout não foram exercitados.

### Admin

O painel aprovou ESLint, 33 testes e build Vite. Um smoke autenticado exibiu o pedido novo e seu ponto real no mapa híbrido. Durante o ensaio, o evento de prontidão foi corrigido de `load` para `style.load`, evitando timeout depois de o estilo já ter sido baixado. O Web Worker ESM também passou a usar o pipeline oficial `?worker&url` do Vite; o asset autocontido respondeu 200 e eliminou 404/MIME incorreto. O reteste confirmou estado pronto, tiles 200, logo/atribuição e ausência de erro novo no console. Headers CSP, X-Frame-Options e nosniff também foram confirmados na resposta real de `/` e do bundle.

### Auditoria de dependências

`pip-audit` detectou `PYSEC-2026-1845` no pytest 8.4.2, risco médio relacionado ao tratamento de `tmpdir` em UNIX. A constraint de desenvolvimento foi elevada para `pytest>=9.0.3,<10` no backend e gateway. Ambas as suítes passaram depois da atualização e o `pip-audit` final retornou zero vulnerabilidades conhecidas.

`npm audit` das dependências de produção do admin também retornou zero vulnerabilidades conhecidas. Os dois resultados são fotografias datadas e devem ser repetidos depois de mudar constraints/locks.

O total executado nesta atualização foi **124 testes**: backend 28, gateway 31, admin 33 e Flutter 32.

## Evidência anterior preservada

Uma chamada controlada diretamente à API criou o pedido `27207fa7-df70-45b5-bb2f-d9279a0347f8`, em `PENDING_ADMIN_APPROVAL`, com coordenadas finais `-23.1178450,-46.5507630` confirmadas no PostgreSQL. Isso comprova contrato/persistência, não mapa funcional nem despacho. **Não aprovar, preparar missão, autorizar voo ou despachar esse pedido.**

Depois de rotacionar e reconciliar a credencial local, o login administrativo, dashboard e detalhe do pedido responderam com sucesso. A inspeção foi somente leitura.

O smoke Web criou também o pedido `92198217-c06b-41f5-b91e-61b985b86803`, em `PENDING_ADMIN_APPROVAL`, com coordenadas `-23.117843,-46.554947` e preferência PIX simulada. **Não aprovar, preparar, autorizar ou despachar nenhum pedido de teste.**

O release Web foi recompilado no estado final. O APK debug configurado possui 190.538.195 bytes, SHA-256 `AF1328CB60E74CFF0D3A5CDE5A8527618F79FB2D55A9E1778061BE221285BE25` e assinatura debug v2 verificada. Ele não foi instalado; não há keystore privada nem release distribuível atual.

## Pendências críticas

- criar e testar chaves MapTiler separadas, configurar quotas/restrições e revogar a exposta;
- executar em emulador/aparelho Android e observar/validar o `User-Agent` antes da restrição;
- testar geolocalização Web concedida, timeout e indisponível;
- testar preparação, revisão e autorização administrativas somente em um ensaio controlado separado;
- comprovar atomicidade/concorrência de decisões, preparação, autorização e claim em PostgreSQL;
- revisar o vínculo verificável entre credencial, gateway e veículo/missão;
- testar SITL antes de Mission Planner/Pixhawk/bancada/voo;
- gerar e instalar novo APK release assinado com a configuração atual.

## Ações deliberadamente não realizadas

- nenhuma chave ou senha foi copiada para documentação, log ou Git;
- nenhum sucesso de browser/Android foi inferido dos requests HTTP diretos;
- nenhuma porta COM, firmware ou parâmetro da Pixhawk foi presumido;
- nenhum comando de armamento real foi executado;
- nenhum resultado de SITL, hardware ou voo foi inferido de doubles;
- nenhum pagamento real foi implementado.

Consulte [INTEGRATION_STATUS.md](INTEGRATION_STATUS.md), [MAPTILER_SETUP.md](MAPTILER_SETUP.md) e [MANUAL_ACTIONS_REQUIRED.md](MANUAL_ACTIONS_REQUIRED.md).
