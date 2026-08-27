# Configuração do MapTiler

O projeto usa o estilo híbrido do MapTiler e renderização MapLibre nas duas interfaces. O Flutter Android/Web usa `maplibre_gl`; o painel React usa MapLibre GL JS. Busca, geocodificação e reverse geocoding passam pelo backend FastAPI para que a credencial de servidor não seja enviada ao cliente.

## Escolha da integração

O link terminado em `/style.json` é um documento de estilo GL e é a opção usada pelo projeto. Ele permite movimentar a câmera, manter o pino no centro, observar `onCameraMove`/`onCameraIdle`, desenhar rota e pontos e compartilhar a mesma implementação Flutter entre Android e Web.

O link terminado em `/maps/hybrid-v4/` entrega um visualizador HTML independente. O trecho `#zoom/latitude/longitude` define somente a vista inicial. Incorporá-lo em `iframe` isolaria o estado e os eventos do mapa e não atende ao fluxo de seleção precisa; por isso ele não é usado.

Mantenha a URL de estilo sem a chave:

```text
https://api.maptiler.com/maps/hybrid-v4/style.json
```

A aplicação adiciona `?key=...` em runtime. Não copie o HTML do `iframe` para o aplicativo.

Referências oficiais: [Maps API](https://docs.maptiler.com/cloud/api/maps/), [visualizador em iframe](https://docs.maptiler.com/guides/getting-started/use-map/iframe/) e [MapLibre no Flutter](https://docs.maptiler.com/flutter/maplibre-gl-js/get-started/).

## Variáveis

Crie um `.env` local a partir de `.env.example` e preencha:

```env
MAP_PROVIDER=maptiler
MAPTILER_STYLE_URL=https://api.maptiler.com/maps/hybrid-v4/style.json
MAPTILER_WEB_API_KEY=
MAPTILER_ANDROID_API_KEY=
MAPTILER_SERVER_API_KEY=
```

- `MAPTILER_WEB_API_KEY`: incorporada aos bundles do Flutter Web e do admin; trate-a como chave pública de navegador.
- `MAPTILER_ANDROID_API_KEY`: incorporada ao APK por `--dart-define`; ela pode ser extraída do aplicativo e não é um segredo de servidor.
- `MAPTILER_SERVER_API_KEY`: lida somente pelo FastAPI para a Search API.
- `MAPTILER_STYLE_URL`: deve apontar para `api.maptiler.com/maps/.../style.json`, sem query, fragmento ou credencial.

Não use uma URL completa como valor de uma variável `*_API_KEY`. Nunca versione `.env`, copie chaves para exemplos, logs, documentação ou screenshots.

## Proteção e rotação

A chave recebida nesta sessão foi publicada em uma conversa. Ela serve apenas para a validação local atual e deve ser rotacionada no painel do MapTiler antes de qualquer apresentação pública.

Na inspeção de 20/08, Web, Android e Server estavam preenchidas, porém com o mesmo valor. Isso é
um risco atual: não existe isolamento entre superfícies enquanto compartilharem a credencial.

1. crie uma chave Web e limite as origens HTTP usadas, por exemplo `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:5174` e `http://127.0.0.1:5174`;
2. crie uma chave Android separada e valide o `User-Agent` real das requisições no aparelho antes de aplicar uma regra compatível;
3. crie uma chave somente de servidor para a Search API; em hospedagem, considere credencial de serviço com assinatura HMAC;
4. substitua as três variáveis no `.env` ignorado e reconstrua/teste cada superfície;
5. configure quotas/alertas e revogue a chave exposta somente depois que as substitutas forem testadas.

Uma chave Web sempre pode ser observada no navegador. O `.env` evita que ela entre no Git, mas a proteção efetiva é a restrição de origem e a rotação. Consulte [autenticação por chave](https://docs.maptiler.com/cloud/api/authentication-key/), [proteção de chaves](https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-protect-your-map-key/) e [credenciais assinadas](https://docs.maptiler.com/guides/maps-apis/maps-platform/how-to-use-credentials-to-securely-sign-requests-to-maptiler-cloud-api/).

## Flutter Web

Com backend e Docker ativos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\start_mobile_web.ps1
```

O aplicativo abre em `http://localhost:5174`. O launcher importa somente a chave Web e a URL de estilo do `.env`, não imprime o valor e passa as configurações por `--dart-define`.

Para iniciar sem o provedor externo e verificar apenas os estados de desenvolvimento:

```powershell
.\scripts\start_mobile_web.ps1 -WithoutMapTiler
```

## Flutter Android

Em um emulador Android:

```powershell
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -MapTilerConfigured
```

Para aparelho físico, informe uma URL da API alcançável pela LAN ou HTTPS e siga [Rede local](LOCAL_NETWORK_SETUP.md). A chave é passada ao código Dart, não ao manifest Android.

## Backend

O backend usa a Search API do MapTiler nos contratos internos já expostos ao aplicativo:

- pesquisa: `GET /geocoding/{texto}.json`;
- detalhe de uma sugestão: `GET /geocoding/{feature_id}.json`;
- reverse geocoding: `GET /geocoding/{longitude},{latitude}.json`.

A ordem externa é longitude/latitude; o backend converte explicitamente para os DTOs do domínio, que usam latitude e longitude nomeadas. A chave de servidor fica na query somente na chamada direta ao MapTiler e deve ser removida de mensagens de erro e logs. Consulte a [Geocoding API](https://docs.maptiler.com/cloud/api/geocoding/).

Depois de mudar a credencial:

```powershell
docker compose up -d --build backend admin
```

## Painel administrativo

O admin usa um mapa MapLibre interativo, e não Static Maps nem `iframe`. Isso permite ajustar a câmera à rota e aos pontos sem depender do endpoint Static Maps, que não está incluído no plano Free.

```powershell
docker compose up -d --build admin
Start-Process 'http://localhost:5173'
```

## Atribuição e consumo

As telas mantêm visíveis a atribuição MapLibre e os créditos `© MapTiler` e `© OpenStreetMap`; no plano Free também exibem o logo MapTiler. Não remova esses elementos. Consulte as [regras de atribuição](https://docs.maptiler.com/guides/map-design/attribution/add-attribution/).

Com uma biblioteca de terceiros como MapLibre, o uso é contado por requisições de tiles, não por sessão do SDK MapTiler. Autocomplete também gera chamadas e já possui tamanho mínimo e debounce no Flutter. Consulte [sessões e requisições](https://docs.maptiler.com/guides/account/sessions-vs-requests/).

## Validação manual

1. confirme que o mapa híbrido abre sem fallback ou banner de erro;
2. pesquise um endereço e escolha uma sugestão;
3. mova e amplie o mapa, verificando que o pino permanece no centro;
4. confirme que a latitude/longitude só é consolidada ao parar a câmera;
5. teste endereço distante e coordenada sem endereço reconhecível;
6. negue a geolocalização e confirme que pesquisa e navegação manual continuam disponíveis;
7. abra o pedido no admin e confira rota, origem, destino, atribuição e logo;
8. inspecione o console e a rede do navegador, procurando 401, 403, CORS, CSP, quota ou falha de tiles;
9. repita no emulador ou aparelho Android; um build APK bem-sucedido não comprova renderização no dispositivo.

Em 7 de agosto de 2026, além dos requests diretos 200, o Flutter Web e o admin foram validados no Chrome com estilo híbrido, tiles, fontes, sprites, busca, reverse geocoding, câmera, logo e atribuição reais. O fluxo chegou à criação e revisão do pedido sem erro de console. Android continua sem execução em dispositivo, e a chave exposta ainda deve ser rotacionada e substituída por credenciais separadas/restritas.
