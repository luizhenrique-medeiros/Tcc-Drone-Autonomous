# Seleção exata do ponto de entrega

## Princípio

O endereço e a posição do dispositivo localizam uma **região aproximada**. A missão usa somente o ponto final que o cliente escolhe manualmente e confirma na segunda etapa. Centralizar o mapa nunca equivale a confirmar destino.

## Etapa 1 — encontrar a região

1. Explicar por que a localização será solicitada.
2. Se permitido, obter posição aproximada e centralizar, exibindo “posição inicial aproximada”.
3. Se negado/desativado/timeout, continuar com pesquisa; não bloquear o carrinho.
4. A barra aceita rua, número, bairro, cidade, CEP ou local; autocomplete pode buscar longe da posição atual.
5. Selecionar resultado faz geocode e move a câmera.
6. O usuário confirma apenas “usar esta região”, avançando o indicador `1. Encontrar região → 2. Ajustar ponto exato`.

## Etapa 2 — ajuste fino

1. Abrir visualização satélite (híbrido pode ser alternado temporariamente).
2. Mostrar marcador pequeno arrastável, área de precisão e zoom/pan.
3. Durante movimento, atualizar coordenadas apenas em memória.
4. Ao soltar, fazer reverse geocode apenas para rótulo e mostrar lat/lon com precisão adequada.
5. Solicitar instruções e checklist: área aberta, sem fios/árvores/cobertura/pessoas/animais envolvidos.
6. Exibir sheet de resumo com mapa, aproximação, final, referência, instruções e confirmação.
7. `Confirmar ponto de entrega` persiste; sem movimento/segunda etapa/confirmação, permanece bloqueado.

## Dados

`searched_address`, `address_reference`, `selection_source`, latitude/longitude aproximadas, latitude/longitude finais, `location`, instruções, confirmação de seleção manual/área segura, provedor, tipo de mapa, precisão e timestamps. `MANUAL_MAP_SELECTION` é a fonte final mesmo quando a aproximação veio de `CURRENT_LOCATION`, `ADDRESS_SEARCH` ou `SAVED_POINT`.

## Validação backend

- faixas geográficas completas;
- flags de segunda etapa e área segura;
- cobertura e distância da base calculadas no servidor;
- ponto PostGIS criado do par final;
- propriedade do cliente;
- erro `DELIVERY_POINT_OUT_OF_RANGE` ou campo específico sem perder o estado local.

O endereço nunca substitui as coordenadas. A precisão informada não é promessa de precisão aeronáutica.

## Visualização administrativa

Mapa satélite mostra base, ponto final, aproximação opcional e linha de referência. Ao lado: lat/lon final, endereço pesquisado, deslocamento aproximação→final, distância base→destino, instruções, origem da seleção e declaração do cliente. O administrador rejeita/solicita novo ponto; não arrasta o marcador do cliente.

## Falhas e recuperação

| Falha | Comportamento |
|---|---|
| permissão negada | pesquisa permanece disponível |
| GPS desligado/timeout | explicar e permitir endereço/manual |
| sem internet/limite da API | manter carrinho, retry, não confirmar mapa ausente |
| nenhum resultado | permitir editar consulta, sem coordenada inventada |
| reverse geocode falha | coordenada pode ser exibida, rótulo “indisponível” |
| mapa não carrega | estado de erro e retry; não usar posição aproximada como final |
| fora de cobertura | manter resumo e permitir reposicionar |
| sessão expirada | reautenticar e restaurar rascunho não sensível |
| falha ao salvar | idempotency key e retry sem duplicar |

## Acessibilidade

Etapas possuem títulos textuais; coordenadas ficam copiáveis/lidas por leitor; controles de zoom têm label; mapa não é o único canal; modal prende foco e retorna ao botão; mensagens associam-se aos campos. Marcador/área segura nunca dependem apenas de cor.

## Critérios de aceite e testes

Cobrir permissão concedida/negada, busca próxima/distante/sem resultado, transição explícita, satélite, movimento do marcador, mudança das coordenadas, bloqueio sem confirmação, restauração, erros e ponto fora de cobertura. Backend testa limites, distância, propriedade e PostGIS. Admin testa diferença aproximado/final e impossibilidade de edição silenciosa.
