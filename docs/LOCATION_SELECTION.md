# Seleção exata do ponto de entrega

## Princípio

Endereço e posição do dispositivo localizam apenas uma **região aproximada**. A missão usa somente latitude e longitude escolhidas manualmente e confirmadas na segunda etapa. Centralizar a câmera nunca equivale a confirmar o destino.

O mesmo fluxo Flutter atende Android e Web com MapLibre e o estilo híbrido MapTiler. O painel administrativo continua separado e somente revisa a escolha; ele não move o ponto em nome do cliente.

## Etapa 1 — encontrar a região

O cliente pode começar de três formas:

1. abrir o mapa diretamente, sem endereço e sem permissão de localização;
2. solicitar a localização aproximada do dispositivo;
3. pesquisar rua, número, bairro, cidade, CEP ou local.

A pesquisa possui debounce de 400 ms, exige pelo menos três caracteres e ignora respostas antigas quando a consulta muda. O aplicativo chama o FastAPI autenticado; o backend consulta a Geocoding API do MapTiler com `autocomplete=true` e adapta o GeoJSON ao contrato interno.

Com `MAPS_SEARCH_COUNTRY=` vazio, a busca não fica restrita a um país. Um código ISO de duas letras aplica o filtro externo, mas nunca substitui a validação local de cobertura.

Selecionar uma sugestão resolve sua coordenada e apenas move o centro inicial. Se o usuário optar pela posição do dispositivo, a interface deixa claro que ela é aproximada.

### Geolocalização indisponível

O pedido de permissão ocorre somente quando o usuário solicita a localização. Os seguintes estados não bloqueiam a seleção manual:

- permissão negada ou bloqueada nas configurações;
- serviço de localização desativado;
- timeout;
- navegador sem suporte;
- falha temporária do provedor.

Nesses casos, o app explica o problema e permite pesquisar ou abrir diretamente a região inicial configurada.

## Etapa 2 — ajustar o ponto exato

1. O MapLibre abre o estilo GL `hybrid-v4`, combinando imagem e rótulos.
2. O pino fica **fixo no centro da viewport**; ele não é um marcador arrastável independente.
3. O usuário move o mapa sob o pino com pan e zoom livres, além de rotação/inclinação quando suportadas.
4. Não há bounds geográficos de UI: é possível navegar por qualquer continente. A cobertura continua sendo validada pelo backend.
5. `onCameraMove` acompanha o alvo e `onCameraIdle` grava em memória a coordenada somente depois de movimento manual.
6. A interface exige pelo menos um ajuste manual, instruções e confirmação explícita de área aberta/adequada.
7. A confirmação persiste latitude e longitude finais; endereço e reverse geocoding são apenas referência.

Em viewport expandida o mapa pode ganhar mais altura, preservando largura limitada do conteúdo. Em telas compactas, os breakpoints controlam a composição. Não mantenha uma meta viewport manual duplicada no `index.html`.

A atribuição MapTiler/OpenStreetMap e o logo oficial MapTiler exigido no plano Free devem permanecer visíveis. O visualizador em `iframe` e Static Maps não fazem parte desse fluxo.

## Dados persistidos

O contrato inclui, conforme disponibilidade:

- `searched_address` e `address_reference` auxiliares;
- `selection_source` final `MANUAL_MAP_SELECTION`;
- latitude/longitude aproximadas;
- latitude/longitude finais;
- ponto PostGIS `location` derivado das coordenadas finais;
- instruções;
- flags de segunda etapa, seleção manual e área segura;
- `map_provider=maptiler`, `map_type=hybrid`, precisão e timestamps aplicáveis.

O endereço nunca substitui as coordenadas. A precisão reportada pelo dispositivo também não é promessa de precisão aeronáutica.

## Validação no backend

- latitude entre -90 e 90 e longitude entre -180 e 180;
- segunda etapa e confirmação de área segura obrigatórias;
- cobertura e distância da base calculadas no servidor;
- ponto PostGIS criado do par final;
- propriedade do cliente;
- erro de domínio claro sem transformar uma aproximação em destino.

Busca mundial não remove a regra de cobertura: ela permite localizar qualquer região, mas um ponto fora do alcance configurado pode ser rejeitado na validação/submissão.

## Visualização administrativa

O admin usa MapLibre GL JS com o mesmo estilo híbrido. Ele mostra base, ponto final, aproximação quando disponível, rota/pontos e linha de referência, enquadrando o conjunto por bounds. Ao lado aparecem lat/lon final, endereço pesquisado, deslocamento aproximação→final, distância base→destino, instruções, origem da seleção e declaração do cliente.

O administrador pode rejeitar ou solicitar nova seleção. Ele não altera silenciosamente a coordenada confirmada.

## Falhas e recuperação

| Falha | Comportamento esperado |
|---|---|
| permissão negada | pesquisa e abertura direta do mapa continuam disponíveis |
| GPS desligado/timeout | mensagem específica e seleção manual |
| navegador sem geolocalização | informar indisponibilidade sem quebrar a tela |
| chave MapTiler ausente/inválida | exibir configuração ausente ou erro real; não liberar confirmação integrada |
| provedor responde 403/429, timeout ou rede falha | erro acionável, retry controlado e nenhuma coordenada fabricada |
| nenhum resultado | permitir editar a consulta, sem coordenada fabricada |
| reverse geocoding falha | preservar/exibir a coordenada e usar rótulo de indisponibilidade |
| estilo ou tiles falham | distinguir loading/erro/fallback e não declarar o mapa carregado |
| fora de cobertura | manter o rascunho e permitir reposicionar |
| sessão expirada | reautenticar sem registrar token na UI/log |
| falha ao salvar | retry/idempotência sem duplicar o ponto |

O fallback de desenvolvimento é identificado, não mostra cartografia real e não libera checkout integrado. Use `-WithoutMapTiler` somente para validar esses estados locais.

## Diagnóstico e testes

Em build debug e ambiente não hospedado, `/debug` permite testar mapa, busca MapTiler e geolocalização, além de API/WebSocket. A tela informa presença de sessão, nunca seu token ou a chave.

Em 2026-08-07, o smoke Flutter Web pesquisou Atibaia, abriu o estilo híbrido no zoom 18, moveu a câmera sob o pino, atualizou coordenadas/rótulo por reverse geocoding e exigiu a declaração de área segura antes do checkout. Tiles, fontes, sprites, logo e atribuição foram observados sem erro de console. Isso valida o browser local, não Android; a chave usada foi exposta e deve ser rotacionada.

Separadamente, uma chamada de integração controlada à API persistiu no PostgreSQL as coordenadas finais `-23.1178450,-46.5507630` e criou o pedido `27207fa7-df70-45b5-bb2f-d9279a0347f8` em `PENDING_ADMIN_APPROVAL`. Isso comprova backend/persistência, não seleção pelo mapa. **Não despachar esse pedido.**

O fluxo Web criou ainda o pedido `92198217-c06b-41f5-b91e-61b985b86803` nas coordenadas finais `-23.117843,-46.554947`; o admin autenticado mostrou o mesmo ponto. **Não aprovar, autorizar ou despachar nenhum pedido de teste.**

Cobrir:

- permissão concedida, negada, desativada, timeout e navegador sem suporte;
- busca próxima, distante, mundial, sem resultado e erro do provedor;
- debounce e descarte de resposta antiga;
- abertura direta do mapa;
- estilo híbrido, pan/zoom livres, atribuição/logo e pino central;
- mudança somente após movimento e `onCameraIdle`;
- bloqueio sem segunda etapa/confirmação;
- viewport compacta sem overflow;
- limites, distância, propriedade e PostGIS no backend;
- admin somente leitura da coordenada final, com rota e fallback honesto.
