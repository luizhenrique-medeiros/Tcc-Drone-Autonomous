# Estado das integrações

Atualizado em 7 de agosto de 2026. **Implementado** significa código inspecionado; **testado** significa comando realmente executado e resultado observado. Evidência de uma camada não comprova a camada seguinte.

## Matriz atual

| Integração | Implementação | Evidência executada | Estado honesto |
|---|---|---|---|
| PostgreSQL/PostGIS + Alembic | sim | migration `0003_schema_names` no head e ciclo em banco temporário na bateria anterior | validado localmente; concorrência crítica ainda requer prova específica em PostgreSQL |
| autenticação/papéis | sim | cadastro/login de cliente, `/auth/me` e login ADMIN ao vivo aprovados | credenciais locais foram rotacionadas; produção ainda exige gestão externa de segredos |
| Flutter Android/Web | mesma base `mobile/`, MapLibre via `maplibre_gl` | 32 testes, analyze, build Web configurado, smoke visual completo no Chrome e APK debug configurado | Web validado localmente com a chave temporária; Android compilado, mas não instalado/executado |
| admin React | MapLibre GL JS, estilo híbrido, rota/pontos e fallback | ESLint, 33 testes, build Vite e smoke visual autenticado aprovados | mapa real validado localmente; restrição da futura chave Web ainda deve ser conferida |
| FastAPI | proxy autenticado para MapTiler Geocoding API | serviço/testes, busca, resolução e reverse geocoding exercitados pelo Flutter Web | fluxo local completo aprovado; chave de servidor exposta ainda deve ser substituída |
| CORS/CSP Web | origens exatas 5173/5174; admin permite MapTiler e worker `blob:` | requests reais e headers CSP/XFO/nosniff confirmados em `/` e no bundle | novos hosts exigem CORS, CSP e origem da chave Web consistentes |
| estilo MapTiler | `hybrid-v4/style.json` em MapLibre, sem `iframe`/Static Maps | HTTP 200 direto e no browser; estilo GL v8, tiles, sprites e fontes carregados | renderização Web comprovada; Android runtime ainda pendente |
| busca MapTiler | backend usa `/geocoding/{texto}.json`, `autocomplete=true`, `language=pt`, limite 5 | consulta “Atibaia” pela UI retornou cinco sugestões reais | aprovado localmente no Web; quotas e chave substituta ainda pendentes |
| reverse geocoding MapTiler | backend envia `longitude,latitude` e adapta GeoJSON | arraste real do mapa atualizou coordenadas e endereço pela UI | aprovado localmente no Web; Android runtime ainda pendente |
| busca mundial | `MAPS_SEARCH_COUNTRY=` vazio omite `country`; valor opcional usa ISO de duas letras | configuração/código inspecionados | cobertura do negócio continua independente do filtro de busca |
| seleção de ponto | mapa híbrido, navegação livre, pino central e `onCameraIdle` | câmera inicial em Atibaia/zoom 18, arraste, confirmação de segurança e persistência pela UI | fluxo Web completo aprovado; não substitui validação técnica do local |
| diagnóstico de runtime | rota/tela somente em debug; endpoint WS em `development`/`test` | teste automatizado anterior | não deve expor chave nem JWT; probes precisam refletir falha real |
| WebSocket cliente/admin | sim | testes automatizados | fluxo autenticado completo no navegador precisa ser revalidado |
| gateway `simulation` | sim | heartbeat e testes anteriores | pedido controlado permanece pendente e **não deve ser despachado** |
| gateway Pymavlink | sim | doubles em memória | não comprova SITL ou porta real |
| QGC WPL 110 | sim | geração/hash/versionamento em testes anteriores | Mission Planner não foi aberto nesta rodada |
| SITL/Mission Planner/Pixhawk/voo | documentação/preparação parcial | nenhuma execução nesta rodada | não validado |

## Ensaio HTTP direto do MapTiler

A credencial não é reproduzida neste relatório. Em 2026-08-07:

| Chamada | Resultado observado | Conclusão permitida |
|---|---|---|
| estilo `hybrid-v4/style.json` | HTTP 200, documento GL v8, 40 layers | estilo acessível naquele request direto |
| pesquisa | HTTP 200, 3 features naquele ensaio | Search API respondeu àquela consulta |
| reverse geocoding | HTTP 200, 1 feature naquele ensaio | Search API respondeu àquela coordenada |

Esses requests diretos, isoladamente, não comprovam a camada de interface. A validação adicional no Chrome confirmou estilo, tiles, sprites, fontes, busca, reverse geocoding, atribuição/logo e fluxo autenticado. Android, restrição de origem/`User-Agent`, quotas e geolocalização concedida continuam sem prova. A chave usada foi exposta em conversa e deve ser substituída/revogada.

## Qualidade e auditoria de dependências

- backend: Ruff, formatação e 28 testes aprovados;
- gateway: Ruff, formatação e 31 testes aprovados;
- admin: ESLint, 33 testes e build Vite aprovados;
- Flutter: formatação, analyze e 32 testes aprovados;
- Python: `pip-audit` detectou `PYSEC-2026-1845` no pytest 8.4.2, risco médio relacionado a `tmpdir` em UNIX;
- backend/gateway: constraints de desenvolvimento elevadas para `pytest>=9.0.3,<10`; ambas as suítes passaram depois da atualização;
- `pip-audit` final: zero vulnerabilidades conhecidas;
- `npm audit` das dependências de produção do admin: zero vulnerabilidades conhecidas.

Total executado: **124 testes automatizados aprovados**. Os audits são fotografias datadas e devem ser repetidos depois de mudar constraints/locks.

## Builds e artefatos

O release Flutter Web atual, configurado com MapTiler e backend local, foi recompilado com sucesso: 40 arquivos e 43.776.910 bytes em `mobile/build/web`.

O APK debug atual foi recompilado com MapTiler para o perfil `android_emulator`: 190.538.195 bytes, SHA-256 `AF1328CB60E74CFF0D3A5CDE5A8527618F79FB2D55A9E1778061BE221285BE25` e assinatura debug v2 verificada. Ele serve para desenvolvimento, mas não foi instalado por ausência de emulador/aparelho. Não existe keystore privada configurada para produzir um release distribuível.

## Pedido controlado e painel administrativo

O smoke Flutter Web criou pela interface o pedido:

- ID: `92198217-c06b-41f5-b91e-61b985b86803`;
- estado: `PENDING_ADMIN_APPROVAL`;
- coordenadas finais: `-23.117843,-46.554947`;
- pagamento: preferência PIX simulada, sem transação bancária;
- mapa: ponto selecionado e revisado visualmente no admin autenticado.

Uma chamada controlada anterior à API também criou o pedido:

- ID: `27207fa7-df70-45b5-bb2f-d9279a0347f8`;
- estado: `PENDING_ADMIN_APPROVAL`;
- coordenadas finais: `-23.1178450,-46.5507630`;
- persistência: valores confirmados diretamente no PostgreSQL.

O pedido novo valida criação pela UI e persistência; o anterior continua sendo evidência direta da API. **Não aprovar, preparar missão, autorizar voo, reivindicar no gateway ou despachar nenhum deles.**

A senha administrativa local e o papel ADMIN foram reconciliados; login, dashboard e detalhe do pedido responderam com sucesso. A inspeção foi somente leitura.

## Configuração e riscos atuais

- portas: API `8000`, admin `5173`, Flutter Web `5174`;
- `MAP_PROVIDER=maptiler` e `MAPS_SEARCH_COUNTRY=` vazio;
- `MAPTILER_STYLE_URL` deve ser a URL HTTPS de `style.json` sem query;
- chave Web pública restrita por origem; Android separada após observar/validar `User-Agent`; servidor somente no FastAPI;
- atribuição MapTiler/OpenStreetMap e logo MapTiler do plano Free não podem ser removidos;
- segredos locais foram regenerados e permanecem somente no `.env` ignorado;
- a chave MapTiler recebida foi exposta e deve ser rotacionada.

## Bloqueios atuais

- criar/testar chaves MapTiler separadas e revogar a credencial exposta;
- confirmar origens Web finais, `User-Agent` Android e quotas;
- instalar e executar o APK em emulador/aparelho com mapa, busca, geolocalização, atribuição e logo;
- validar geolocalização Web nos estados concedida, timeout e indisponível; o estado bloqueado já foi observado;
- gerar release Android atual com keystore/assinatura e instalá-lo;
- manter o pedido controlado sem despacho;
- testar fluxo admin de missão, SITL, Mission Planner e hardware.

Resultado `COMPLETED` em `simulation` continua sendo estado lógico, nunca prova de entrega física.
