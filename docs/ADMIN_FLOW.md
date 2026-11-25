# Fluxo administrativo

## Login e sessão

Não há cadastro público admin. Um usuário provisionado entra pela rota separada; frontend armazena sessão pelo mecanismo mais seguro disponível e evita incluir token em URL/log. Rotas validam papel também no servidor.

## Fila e análise

Dashboard resume pendentes, aprovados, missões em revisão/autorização/execução e saúde do veículo com horário de recebimento. Telemetria e saúde sempre exibem a origem `Simulação`, `SITL`, `Hardware real` ou `Origem desconhecida`; dados vencidos recebem destaque explícito. A fila suporta filtro/paginação. O detalhe mostra cliente, snapshots de produto/preço, forma simulada, mapa satélite, aproximação/final, instruções, distância e validações.

## Primeira decisão

- **Aprovar pedido:** modal resume pedido e coordenadas; a ação move apenas para `APPROVED`.
- **Rejeitar pedido:** exige motivo legível, confirmação e auditoria.
- Local inadequado causa rejeição/solicitação de novo ponto; coordenada não é editada silenciosamente.

Botões ficam disabled/loading durante envio e usam idempotency key para impedir duplo clique.

## Preparação e exportação

1. No detalhe do pedido aprovado, selecione **Preparar missão**. A revisão registra origem, ponto final do pedido, altitude relativa configurada e hash.
2. Em **Revisão da missão**, selecione **Baixar missão para QGroundControl**. O nome do `.plan` inclui pedido, revisão e parte do hash da missão. A exportação registra o horário e o administrador, mesmo se a aeronave estiver desconectada.
3. No QGroundControl, abra o arquivo em **Plan → Open**. Revise Home, sequência, coordenadas, altitude e retorno. O operador realiza upload e toda ação na aeronave pelo QGroundControl. O arquivo revisado pode ser registrado opcionalmente no painel para auditoria.

## Acompanhamento e conclusão

Em **Acompanhamento do voo**, na tela da missão, veja estado, eventos, posições e trajeto observados. Se o plano a bordo já possui evidência de vínculo com uma revisão única, o acompanhamento aparece automaticamente durante a execução. Caso contrário, após baixar o arquivo da revisão atual, selecione **Acompanhar esta missão**, escolha o PX4 conectado e confirme. O painel registra o administrador, a revisão, o veículo e o horário. A associação identifica qual voo acompanhar e mantém a correspondência dos itens como não verificada.

Em **Telemetria**, o veículo continua visível sem uma missão associada. Durante perda do enlace, o último estado fica desatualizado e o mapa separa trechos com lacunas. A retomada usa o que o PX4 informar naquele momento. Consulte [as evidências por etapa](DRONE_PROTOCOL.md#observação-automática-do-voo).

No detalhe do pedido, use **Confirmar entrega** depois de obter evidência da entrega física. Informe a evidência. O sistema guarda administrador, horário e pedido. Waypoint, pouso e desarmamento são observações e não concluem a entrega.

## Auditoria

A linha do tempo separa decisão, geração, exportação, registro de revisão, observação correlacionada e confirmação de entrega. Baixar ou registrar uma revisão não confirma upload à Pixhawk.

## Estados de interface

Toda página cobre loading, vazio, erro explícito com retry, sucesso, dados vencidos e sessão expirada. Erro de API não é apresentado como lista vazia. Tablet reorganiza painéis; ações críticas continuam próximas do resumo e nunca desaparecem em scroll sem contexto.
