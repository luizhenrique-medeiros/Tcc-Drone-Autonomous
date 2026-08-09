# Seleção exata do ponto de entrega

## Princípio

Endereço e posição do dispositivo localizam apenas uma **região aproximada**. Uma localização salva também é apenas um ponto inicial reutilizável no checkout. A missão usa somente latitude e longitude revisadas no mapa e confirmadas para aquele pedido. Centralizar a câmera ou tocar em um atalho nunca equivale a confirmar o destino.

O mesmo fluxo Flutter atende Android e Web com MapLibre/MapTiler e registra o provider e o tipo realmente exibidos; o modo final pode ser `hybrid` ou `satellite`. O painel administrativo continua separado e somente revisa a escolha; ele não move o ponto em nome do cliente.

## Etapa 1 — encontrar a região

O cliente pode começar de quatro formas:

1. abrir o mapa diretamente, sem endereço e sem permissão de localização;
2. solicitar a localização aproximada do dispositivo;
3. pesquisar rua, número, bairro, cidade, CEP ou local;
4. escolher uma `SavedLocation` própria, quando a lista autenticada não estiver vazia.

A pesquisa possui debounce de 400 ms, exige pelo menos três caracteres e ignora respostas antigas quando a consulta muda. O aplicativo chama o FastAPI autenticado; o backend consulta a Geocoding API do MapTiler com `autocomplete=true` e adapta o GeoJSON ao contrato interno.

Com `MAPS_SEARCH_COUNTRY=` vazio, a busca não fica restrita a um país. Um código ISO de duas letras aplica somente o filtro externo de busca e não restringe a aceitação mundial do checkout.

Selecionar uma sugestão resolve sua coordenada e apenas move o centro inicial. Se o usuário optar pela posição do dispositivo, a interface deixa claro que ela é aproximada.

As localizações salvas aparecem em quantidade dinâmica, sem placeholders. Ao tocar em uma delas, o aplicativo carrega suas coordenadas e mantém `map_provider`/`map_type` no contrato, mas abre o mesmo `SatelliteMapView` com o estilo ativo da aplicação; não cria pedido, não atualiza o atalho e não ignora a revisão. Recurso alheio ou removido entre listagem e uso recebe o `404` não enumerável da API.

### Geolocalização indisponível

O pedido de permissão ocorre somente quando o usuário solicita a localização. Os seguintes estados não bloqueiam a seleção manual:

- permissão negada ou bloqueada nas configurações;
- serviço de localização desativado;
- timeout;
- navegador sem suporte;
- falha temporária do provedor.

Nesses casos, o app explica o problema e permite pesquisar ou abrir diretamente a região inicial configurada.

## Etapa 2 — ajustar o ponto exato

1. O MapLibre abre o estilo MapTiler configurado para a aplicação; o fluxo Flutter atual usa `hybrid-v4`, combinando imagem e rótulos. O contrato/backend aceitam `hybrid` ou `satellite`: a cópia direta de um atalho preserva o tipo armazenado, enquanto um ajuste manual registra o tipo efetivamente ativo no novo ponto.
2. O pino fica **fixo no centro da viewport**; ele não é um marcador arrastável independente.
3. O usuário move o mapa sob o pino com pan e zoom livres, além de rotação/inclinação quando suportadas.
4. Não há bounds geográficos de UI: é possível navegar por qualquer continente, e o backend aceita no checkout qualquer coordenada mundial válida.
5. `onCameraMove` acompanha o alvo e `onCameraIdle` grava em memória a coordenada somente depois de movimento manual.
6. Para busca, posição aproximada ou abertura direta, a interface exige pelo menos um ajuste manual. Arrastar o mapa e os controles semânticos `Norte`, `Sul`, `Leste` e `Oeste` atualizam o mesmo centro e atendem essa exigência, permitindo concluir a etapa também por teclado, switch ou leitor de tela. Uma localização salva já nasce de um ponto final e de evidência real, mas ainda exige revisão e confirmação atuais no mapa; o cliente pode confirmá-la sem deslocar ou movê-la somente para o pedido.
7. A revisão atual e a confirmação de área aberta/adequada continuam obrigatórias para o pedido. Somente depois delas o app envia `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true`. Instruções podem ser revisadas, e endereço/reverse geocoding permanecem apenas referência.
8. Se o ponto salvo for deslocado ou suas instruções forem alteradas no checkout, o aplicativo persiste um `DeliveryPoint` manual ajustado; não envia PATCH para `SavedLocation` nem descarta a instrução específica daquele pedido. Atualizar o atalho exige entrar explicitamente em `Editar`.

Em viewport expandida o mapa pode ganhar mais altura, preservando largura limitada do conteúdo. Em telas compactas, os breakpoints controlam a composição. Não mantenha uma meta viewport manual duplicada no `index.html`.

A atribuição MapTiler/OpenStreetMap e o logo oficial MapTiler exigido no plano Free devem permanecer visíveis. O visualizador em `iframe` e Static Maps não fazem parte desse fluxo.

## Dados persistidos

O contrato inclui, conforme disponibilidade:

- `searched_address` e `address_reference` auxiliares;
- `selection_source` final `MANUAL_MAP_SELECTION` no caminho manual ou `SAVED_POINT` na cópia direta de um atalho;
- latitude/longitude aproximadas;
- latitude/longitude finais;
- ponto PostGIS `location` derivado das coordenadas finais;
- instruções;
- flags de segunda etapa, seleção manual e área segura produzidas pela interação real;
- `map_provider` realmente usado, `map_type` igual a `hybrid` ou `satellite`, precisão e timestamps aplicáveis.

O endereço nunca substitui as coordenadas. A precisão reportada pelo dispositivo também não é promessa de precisão aeronáutica.

Uma `SavedLocation` guarda `id`, proprietário, nome de 1 a 40 caracteres, latitude/longitude finais, `location` PostGIS derivada, referência de endereço opcional, instruções opcionais, precisão opcional, `map_provider`, `map_type`, `region_confirmed`, `exact_point_selected`, `user_confirmed`, `user_confirmed_safe_area` e timestamps. A criação exige que as quatro flags sejam verdadeiras e provenientes do mesmo fluxo MapLibre/MapTiler. Quando usada sem ajuste, seus valores e provider/tipo são copiados para um novo `DeliveryPoint` com `selection_source=SAVED_POINT` na mesma transação do pedido, enquanto as confirmações do snapshot vêm da revisão atual; editar ou excluir o registro original não altera a cópia.

O pedido aceita exatamente um identificador de ponto já confirmado ou de localização salva. Com `saved_location_id`, aceita também as duas confirmações atuais obrigatórias; flags antigas não dispensam a nova revisão. Se o cliente optar por salvar um novo ponto manual, o aplicativo cria o pedido primeiro e só então dispara `/saved-locations` sem aguardar essa segunda resposta para concluir o checkout. Essa chamada é opcional; latência, offline, limite ou falha produzem apenas aviso sobre o atalho e não atrasam, revertem nem ocultam o pedido já criado.

## Validação no backend

- latitude entre -90 e 90 e longitude entre -180 e 180;
- segunda etapa e confirmação de área segura obrigatórias;
- distância da base calculada no servidor para auditoria;
- ponto PostGIS criado do par final;
- propriedade do cliente;
- erro de domínio claro sem transformar uma aproximação em destino;
- exatamente um de `delivery_point_id` ou `saved_location_id` na criação do pedido;
- com `saved_location_id`, `saved_location_review_confirmed` e `saved_location_safe_area_confirmed` obrigatoriamente verdadeiros após a revisão atual;
- propriedade da localização salva e cópia transacional para `DeliveryPoint`, com provider/tipo persistidos e confirmações atuais, nunca sintetizadas;
- nome aparado de 1 a 40 caracteres e máximo de três atalhos, com criação serializada por `FOR NO KEY UPDATE` na linha do usuário;
- criação do atalho apenas com as quatro confirmações verdadeiras, provider real e `map_type` `hybrid` ou `satellite`;
- endereço textual opcional e `409/SAVED_LOCATION_LIMIT_REACHED` sem substituir registro existente.

Busca mundial e checkout mundial usam o mesmo critério geográfico: qualquer ponto dentro das faixas de latitude/longitude pode ser validado, persistido e submetido. O raio máximo permanece uma validação operacional de missão no gateway, não uma restrição de pedido.

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
| coordenada fora da faixa mundial | informar erro de validação e manter o rascunho para correção |
| sessão expirada | reautenticar sem registrar token na UI/log |
| falha ao salvar | retry/idempotência sem duplicar o ponto |
| lista de localizações falha/offline | estado de erro/offline e retry; nunca fabricar cards |
| localização salva foi removida ou é alheia | resposta não enumerável e retorno seguro à escolha de destino |
| limite de três atingido | ocultar/desabilitar salvamento; servidor retorna `SAVED_LOCATION_LIMIT_REACHED` se houver corrida |
| salvamento opcional após pedido falha | preservar pedido e destino; informar que apenas o atalho não foi salvo |

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
- faixa mundial, distância para auditoria, propriedade e PostGIS no backend;
- admin somente leitura da coordenada final, com rota e fallback honesto.
- lista autenticada com zero, uma, duas e três localizações, sem placeholders;
- CRUD próprio, recurso alheio não enumerável, nome 1–40, endereço ausente e limite concorrente no PostgreSQL;
- seleção salva abrindo o mesmo mapa, revisão sem conclusão instantânea e ajuste que não altera o atalho;
- snapshot do pedido preservado depois de editar/excluir `SavedLocation`;
- salvamento opcional posterior aprovado, recusado, offline, no limite e com erro, sempre sem bloquear o pedido.
