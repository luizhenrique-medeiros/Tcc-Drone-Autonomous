# Requisitos e rastreabilidade

## Convenções

`RF` identifica requisito funcional, `RNF` requisito não funcional e `CA` critério de aceite. Catálogo e pagamento são demonstrativos; coordenadas, aprovação, missão e telemetria usam contratos reais.

## Requisitos funcionais

### Cliente

- **RF-CLI-01:** cadastrar e autenticar cliente sem permitir escolha de papel administrativo.
- **RF-CLI-02:** listar produtos acadêmicos disponíveis e seus detalhes.
- **RF-CLI-03:** criar carrinho com quantidade positiva e snapshot de preço.
- **RF-CLI-04:** pesquisar uma região e, em etapa distinta, mover manualmente o marcador no mapa satélite.
- **RF-CLI-05:** confirmar coordenadas finais, instruções e declaração de área segura.
- **RF-CLI-06:** escolher `CREDIT_CARD_SIMULATED` ou `PIX_SIMULATED` sem informar dados bancários.
- **RF-CLI-07:** submeter pedido e acompanhar todos os estados, inclusive rejeição e falha.
- **RF-CLI-08:** visualizar somente os próprios pedidos, separados entre andamento e histórico, com ordenação recente, filtros e paginação.
- **RF-CLI-09:** visualizar todas as informações de um pedido, inclusive itens, valores, forma de pagamento simulada, ponto exato, instruções, andamento e somente as datas realmente registradas.

### Administração

- **RF-ADM-01:** autenticar somente usuário pré-provisionado com papel `ADMIN`.
- **RF-ADM-02:** listar pedidos, filtrar pendentes e abrir mapa/coordenadas/instruções/validações.
- **RF-ADM-03:** aprovar pedido ou rejeitar com motivo e auditoria.
- **RF-ADM-04:** preparar missão apenas de pedido aprovado e exportar arquivo compatível com Mission Planner.
- **RF-ADM-05:** registrar início e conclusão da revisão da mesma versão da missão.
- **RF-ADM-06:** visualizar checks automáticos recentes do veículo e da missão como `PASS`, `WARNING` ou `BLOCKING` antes da autorização.
- **RF-ADM-07:** autorizar voo em endpoint separado, com três confirmações físicas, resumo final e área controlada, sem frase digitada.
- **RF-ADM-08:** acompanhar telemetria/eventos e solicitar abortamento ou RTL com confirmação.

### Missão, gateway e hardware

- **RF-MIS-01:** criar no máximo uma missão ativa por pedido, com origem, decolagem, destino, espera, retorno e pouso.
- **RF-MIS-02:** versionar missão, arquivo, hash, waypoints, autor da preparação e revisão.
- **RF-MIS-03:** invalidar autorização se versão ou estado crítico mudar; expirar e consumir uma única vez.
- **RF-GTW-01:** autenticar gateway, registrar heartbeat e reivindicar missão autorizada idempotentemente.
- **RF-GTW-02:** conectar fake, SITL ou Pixhawk conforme configuração explícita e nunca armar no startup/health.
- **RF-GTW-03:** validar preflight, enviar missão, confirmar conteúdo e só então iniciar uma missão autorizada.
- **RF-GTW-04:** normalizar posição, altitude, velocidade, bateria, GPS, modo e armamento.
- **RF-GTW-05:** tratar timeout, reconexão, duplicidade, falha, abortamento e RTL sem desativar failsafes.
- **RF-OPS-01:** permitir execução real apenas em área controlada, com operador e checklist documentado.
- **RF-OPS-02:** concluir somente após entrega e retorno confirmados por eventos válidos.

### Auditoria

- **RF-AUD-01:** registrar ator, pedido, missão, veículo, evento, severidade, timestamp e metadados não sensíveis.
- **RF-AUD-02:** registrar decisão, rejeição, preparação, revisão, autorização, claim, upload, início, chegada, entrega, retorno, abortamento e falha.

## Requisitos não funcionais

- **RNF-01 Segurança:** hash de senha robusto, JWT expirável, autorização por papel/propriedade e segredo externo.
- **RNF-02 Integridade:** UUID, UTC, `Decimal/NUMERIC`, constraints e transações atômicas.
- **RNF-03 Geografia:** ponto final `geography(Point,4326)` e faixa mundial válida; checkout aceita qualquer coordenada válida, enquanto a distância máxima configurável continua sendo uma proteção operacional da missão/gateway.
- **RNF-04 Disponibilidade:** `/health` mede processo e `/ready` dependências; falhas possuem retry controlado.
- **RNF-05 Observabilidade:** logs estruturados e correlação sem credenciais ou localização desnecessária.
- **RNF-06 Usabilidade:** mobile responsivo, alvos de toque, estados loading/vazio/erro e texto escalável.
- **RNF-07 Acessibilidade:** foco visível, labels, contraste WCAG AA e estado não comunicado apenas por cor.
- **RNF-08 Manutenibilidade:** monólito modular, tokens centrais, componentes reutilizáveis e contratos tipados.
- **RNF-09 Testabilidade:** unitários sem rede/hardware; integração, SITL e hardware em camadas separadas.
- **RNF-10 Segurança operacional:** nenhuma ação automática de armamento, alteração de parâmetro ou supressão de pre-arm.

## Critérios de aceite

- **CA-01:** cadastro público sempre cria `CUSTOMER`; login admin só funciona com seed controlado.
- **CA-02:** endereço distante centraliza a câmera, mas não salva destino sem etapa manual final.
- **CA-03:** mover o marcador altera latitude/longitude; confirmar sem área segura ou segunda etapa é rejeitado.
- **CA-04:** ponto dentro da faixa mundial, confirmado na segunda etapa, cria e submete pedido mesmo distante; somente coordenada fora de faixa retorna erro de domínio claro.
- **CA-05:** pedido submetido fica pendente; cliente não consegue aprovar.
- **CA-06:** rejeição sem motivo falha; aprovação cria apenas permissão para preparar missão.
- **CA-07:** missão exportada abre como QGC WPL 110 e seus waypoints/hash são auditáveis.
- **CA-08:** autorizar antes da revisão, com saúde vencida ou checklist incompleto falha.
- **CA-09:** autorização e aprovação têm endpoints, registros e timestamps diferentes.
- **CA-10:** duas tentativas de claim/upload não executam duas vezes.
- **CA-11:** telemetria mais antiga não sobrescreve snapshot recente.
- **CA-12:** app e painel exibem atualização; desconexão mostra dado como vencido, não saudável.
- **CA-13:** testes rápidos não abrem MAVLink real.
- **CA-14:** nenhuma documentação marca Pixhawk/SITL/voo como testado sem comando ou evidência correspondente.
- **CA-15:** a listagem paginada e o detalhe do cliente nunca expõem pedido de outro usuário; tentativa direta usa a resposta não enumerável do projeto.
- **CA-16:** pedidos ativos atualizam por WebSocket; queda conserva o último estado, indica degradação, tenta reconectar e permite atualização manual.
- **CA-17:** autorização não possui campo de frase, exige exatamente três confirmações humanas e continua bloqueada por qualquer check técnico `BLOCKING`; `WARNING` permanece visível sem impedir a ação.

## Matriz de rastreabilidade

| Requisito | Componentes | Contrato principal | Teste esperado |
|---|---|---|---|
| RF-CLI-01 | mobile, auth/users | `/auth/register`, `/auth/login` | backend + widget |
| RF-CLI-04/05 | mobile, delivery_points, admin | `/delivery-points/validate` e `POST` | widget + domínio + admin |
| RF-CLI-07/08/09 | mobile, orders, system_events | `/orders`, `/orders/{id}`, `/ws/orders/{id}` | ownership + paginação + widget + WebSocket |
| RF-ADM-03 | orders, approvals, admin | `/admin/orders/{id}/approve|reject` | RBAC/transição/auditoria |
| RF-ADM-04/05 | missions, admin | prepare/review/download | exportador e componente |
| RF-ADM-06/07 | vehicles, approvals, admin | health/authorize-flight | checks automáticos, três confirmações, TTL e idempotência |
| RF-GTW-01/03 | gateway, missions | authorized/claim/status | idempotência e timeout |
| RF-GTW-04 | telemetry, WebSocket | telemetry/events/ws | normalização e ordenação |
| RF-OPS-01 | gateway, documentação | configuração real/checklist | ensaio manual, nunca CI |

Os detalhes executáveis estão em [API](API.md), [Banco](DATABASE.md), [Plano de testes](TEST_PLAN.md) e [Protocolo](DRONE_PROTOCOL.md).
