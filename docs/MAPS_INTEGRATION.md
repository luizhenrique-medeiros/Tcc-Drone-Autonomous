# Integração de mapas

## Arquitetura vigente

MapTiler é o provedor externo e MapLibre faz a renderização. Android e Web usam a mesma base Flutter em `mobile/`; `admin_web/` permanece uma aplicação React separada.

```text
Flutter Android/Web
  ├─ SatelliteMapView → maplibre_gl → estilo GL híbrido MapTiler
  ├─ LocationService → geolocator
  └─ MapProvider → FastAPI autenticado → MapTiler Geocoding API

Admin React → MapLibre GL JS → mesmo estilo GL híbrido MapTiler
```

O cliente consulta busca, geocodificação e reverse geocoding somente pelos contratos internos da API. A credencial de servidor nunca chega ao Flutter nem ao painel administrativo. SDKs e serviços externos ficam atrás de abstrações para permitir doubles determinísticos.

## Estilo JSON, não `iframe`

O projeto usa a URL de estilo vetorial:

```text
https://api.maptiler.com/maps/hybrid-v4/style.json
```

Esse documento GL permite ao MapLibre controlar pan, zoom, câmera, eventos, rota e marcadores. A aplicação acrescenta a chave em runtime; `MAPTILER_STYLE_URL` deve permanecer sem query, fragmento ou credencial.

O visualizador terminado em `/maps/hybrid-v4/` é uma página HTML independente. Um `iframe` isolaria estado e eventos e, portanto, não é usado. Static Maps também não é usado: o admin renderiza o estilo interativo e não depende do endpoint pago que fica fora do plano Free.

## Variáveis e credenciais

```env
MAP_PROVIDER=maptiler
MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json
MAPTILER_WEB_API_KEY=
MAPTILER_ANDROID_API_KEY=
MAPTILER_SERVER_API_KEY=
```

Use credenciais separadas:

1. `MAPTILER_WEB_API_KEY` é incorporada aos bundles do Flutter Web e do admin. É pública por natureza e deve aceitar somente as origens Web exatas autorizadas;
2. `MAPTILER_ANDROID_API_KEY` é incorporada ao APK e também pode ser extraída. Antes de restringi-la, observe e valide o `User-Agent` realmente enviado pelo aplicativo/dispositivo;
3. `MAPTILER_SERVER_API_KEY` fica somente no FastAPI. Não a reutilize em navegador ou APK; em hospedagem, avalie credencial de serviço com assinatura HMAC.

A chave recebida para esta migração foi exposta em conversa. Ela deve ser rotacionada antes de apresentação ou publicação. Nenhum valor real pode entrar em Dart, documentação, screenshot, log, histórico de terminal ou Git. O `.env` evita versionamento, mas não torna uma chave cliente secreta.

Procedimento detalhado: [MAPTILER_SETUP.md](MAPTILER_SETUP.md).

## Flutter Web e Android

O launcher Web recomendado é:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1
```

Ele usa `http://localhost:5174`, importa do `.env` somente a chave Web e a URL de estilo, não imprime a credencial e passa a configuração por `--dart-define`.

Em emulador Android:

```powershell
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -MapTilerConfigured
```

Para executar deliberadamente sem o provedor externo e verificar estados locais:

```powershell
.\scripts\start_mobile_web.ps1 -WithoutMapTiler
```

O fallback é identificado como desenvolvimento, não mostra cartografia real, não se apresenta como mapa híbrido e não libera checkout integrado.

## Busca e geocodificação

O FastAPI adapta a Geocoding API do MapTiler aos DTOs estáveis do aplicativo:

```http
GET https://api.maptiler.com/geocoding/{texto}.json
  ?key=<segredo-do-servidor>
  &language=pt
  &limit=5
  &autocomplete=true
```

- pesquisa: texto codificado, `autocomplete=true` e até cinco resultados;
- detalhe/geocode: endereço ou `feature_id`, `autocomplete=false` e limite um;
- reverse geocoding: `{longitude},{latitude}.json`, sempre nessa ordem externa;
- `MAPS_SEARCH_COUNTRY=` vazio omite o filtro `country`; um código ISO de duas letras restringe somente resultados da busca e não limita o checkout mundial.

O Flutter aplica debounce de 400 ms, consulta a partir de três caracteres e descarta respostas antigas. O backend valida GeoJSON, coordenadas, campos ausentes e respostas vazias. `403`, `429`, timeout, rede ou JSON inválido viram erros explícitos; nenhum deles autoriza fabricar endereço ou coordenada.

Geocode fornece somente uma aproximação inicial. Reverse geocoding fornece um rótulo auxiliar. Latitude e longitude confirmadas manualmente continuam autoritativas.

## Mapa e seleção manual

- estilo híbrido MapTiler carregado por MapLibre;
- navegação mundial sem bounds artificiais na UI;
- pan e zoom livres, com rotação/inclinação conforme suporte da plataforma;
- pino visual fixo no centro no fluxo do cliente;
- alvo acompanhado durante o movimento e consolidado em `onCameraIdle`, somente depois de interação manual;
- rota e pontos desenhados no admin, com enquadramento por bounds ou zoom de ponto único;
- confirmação de área segura e segunda etapa obrigatórias;
- faixa geográfica e confirmações recalculadas pelo servidor; distância preservada para auditoria e limite operacional aplicado pelo gateway.

A localização do dispositivo é opcional e aproximada. Permissão negada, serviço desativado, timeout ou navegador sem suporte mantêm busca e navegação direta disponíveis.

## Atribuição, logo e consumo

Os créditos fornecidos pelas fontes do estilo devem permanecer visíveis no controle de atribuição do MapLibre, incluindo MapTiler e OpenStreetMap. No plano Free, o logo oficial do MapTiler também deve permanecer visível e linkado. Não cubra, remova ou substitua esses elementos.

Com MapLibre, o consumo é contabilizado pelas requisições aos recursos do mapa. Busca/autocomplete também consome chamadas. Debounce, limite de resultados e monitoramento de quota evitam consumo desnecessário, mas não devem esconder `429` do usuário.

## CORS, CSP e URLs

| Consumidor | URL local |
|---|---|
| Flutter Web | `http://localhost:5174` |
| admin | `http://localhost:5173` |
| API | `http://localhost:8000` |

O backend permite somente origens Web exatas, incluindo variantes `127.0.0.1` quando necessárias. CORS não se aplica ao APK nativo. As origens autorizadas da chave Web MapTiler devem acompanhar as URLs reais do Flutter Web e admin.

O Nginx do admin permite os recursos `https://api.maptiler.com` e workers `blob:` exigidos pelo MapLibre. Hospedagem em outro domínio exige revisar CORS, CSP e a restrição de origem da chave; não use `*` fora de teste isolado.

## Diagnóstico e falhas

Loading, timeout, erro do estilo/tiles e fallback são estados distintos. Criar controller, receber parte do estilo ou obter um HTTP 200 isolado não comprova que o mapa ficou utilizável no navegador ou Android. A UI deve bloquear confirmação integrada quando o provedor não estiver operacional.

Em build debug e ambiente não hospedado, `/debug` informa plataforma, URL/saúde da API, WebSocket, inicialização do mapa, busca e geolocalização. A tela mostra apenas presença de sessão; nunca exibe chave ou JWT.

## Evidência confirmada em 2026-08-07

Um ensaio HTTP direto, usando a credencial temporária, confirmou:

- estilo híbrido: HTTP 200, documento GL versão 8 e 40 layers;
- pesquisa: HTTP 200 e 3 features nesse ensaio;
- reverse geocoding: HTTP 200 e 1 feature nesse ensaio.

Esses resultados diretos foram complementados por smoke real no Chrome. O Flutter Web confirmou estilo/tiles/fontes/sprites, câmera inicial, pan, busca, reverse geocoding, atribuição/logo e checkout; o admin autenticado confirmou o ponto no mapa e headers CSP reais. Android, geolocalização concedida/timeout e origem/`User-Agent` restritos ainda não foram comprovados. A credencial usada continua exposta e precisa ser rotacionada.

No admin, lint, 33 testes, build e smoke visual passaram. Durante o smoke, a prontidão foi corrigida para `style.load` e o worker do MapLibre passou a ser empacotado pelo Vite com `?worker&url`; o reteste obteve worker/tiles 200, exibiu o mapa e o marcador sem timeout ou erro novo no console. A futura chave restrita ainda exige novo smoke.

## Testes esperados

- backend: URL, ordem longitude/latitude, query, parser GeoJSON, país opcional, 403/429/timeout e filtragem da chave em erros/logs;
- Flutter: debounce, descarte de resposta antiga, geolocalização, pino central, eventos de câmera e layout compacto;
- Web: estilo, tiles, CORS/CSP, origem autorizada, atribuição/logo e fluxo autenticado;
- Android: build e execução em emulador/aparelho, `User-Agent`, mapa visual e permissão;
- admin: rota/pontos, fit bounds, loading, erro, retry e fallback honesto;
- manual: pan/zoom mundial, endereço distante, coordenada sem rótulo e consumo/quota.

## Referências oficiais

- [MapTiler Maps API](https://docs.maptiler.com/cloud/api/maps/)
- [MapTiler Geocoding API](https://docs.maptiler.com/cloud/api/geocoding/)
- [Proteção de chaves MapTiler](https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/)
- [Atribuição MapTiler](https://docs.maptiler.com/guides/map-design/attribution/add-attribution/)
- [MapLibre GL JS](https://maplibre.org/maplibre-gl-js/docs/)
- [Pacote Flutter `maplibre_gl`](https://pub.dev/packages/maplibre_gl)
