# Fluxo administrativo

## Login e sessão

Não há cadastro público admin. Um usuário provisionado entra pela rota separada; frontend armazena sessão pelo mecanismo mais seguro disponível e evita incluir token em URL/log. Rotas validam papel também no servidor.

## Fila e análise

Dashboard resume pendentes, aprovados, missões em revisão/autorização/execução e saúde do veículo com timestamp. A fila suporta filtro/paginação. O detalhe mostra cliente, snapshots de produto/preço, forma simulada, mapa satélite, aproximação/final, instruções, distância e validações.

## Primeira decisão

- **Aprovar pedido:** modal resume pedido e coordenadas; a ação move apenas para `APPROVED`.
- **Rejeitar pedido:** exige motivo legível, confirmação e auditoria.
- Local inadequado causa rejeição/solicitação de novo ponto; coordenada não é editada silenciosamente.

Botões ficam disabled/loading durante envio e usam idempotency key para impedir duplo clique.

## Preparação e revisão

Uma ação posterior prepara missão, exibe versão/hash/waypoints e oferece download QGC WPL. O operador abre no Mission Planner e registra início/conclusão da revisão. Mudar a rota gera versão nova e invalida autorização anterior.

## Saúde, checklist e segunda decisão

Antes de autorizar, o painel mostra conexão, idade do heartbeat, modo, armamento, GPS/satélites, EKF, bateria, origem/destino/distância/altitude, versão e resultados preflight. O checklist inclui área controlada e operador.

`Autorizar voo` abre confirmação reforçada com frase/checkbox, envia endpoint próprio e mostra validade curta. Não aparece como continuação automática do botão Aprovar.

## Acompanhamento e incidentes

WebSocket atualiza missão, posição, bateria e eventos; desconexão marca dados vencidos e faz refetch. Abortamento e RTL são botões separados, vermelhos somente quando destrutivos, com motivo, modal e resultado. O operador continua usando Mission Planner como estação de segurança.

## Auditoria

Timeline registra ator, decisão/motivo, versão, revisão, checklist, autorização/expiração/consumo, veículo, upload, execução, entrega, retorno e falhas. A UI não permite apagar evidência.

## Estados de interface

Toda página cobre loading, vazio, erro com retry, sucesso e sessão expirada. Tablet reorganiza painéis; ações críticas continuam próximas do resumo e nunca desaparecem em scroll sem contexto.
