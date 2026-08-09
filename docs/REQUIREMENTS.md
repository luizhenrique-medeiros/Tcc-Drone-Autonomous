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
- **RF-CLI-06:** escolher `CREDIT_CARD` ou `PIX` como forma simulada, sem informar dados bancários.
- **RF-CLI-07:** submeter pedido e acompanhar todos os estados, inclusive rejeição e falha.
- **RF-CLI-08:** visualizar somente os próprios pedidos, separados entre andamento e histórico, com ordenação recente, filtros e paginação.
- **RF-CLI-09:** visualizar todas as informações de um pedido, inclusive itens, valores, forma de pagamento simulada, ponto exato, instruções, andamento e somente as datas realmente registradas.
- **RF-CLI-10:** listar, cadastrar, editar e excluir de zero a três localizações salvas próprias pela aba `Conta`, com nome livre de 1 a 40 caracteres e endereço textual opcional; o atalho persiste `map_provider`, `map_type` (`hybrid` ou `satellite`) e as quatro confirmações reais produzidas pelo mesmo fluxo de mapa, e só pode ser criado com todas verdadeiras.
- **RF-CLI-11:** escolher uma localização salva no checkout, abri-la no mesmo mapa MapLibre/MapTiler, revisar, ajustar opcionalmente apenas para aquele pedido e confirmar novamente o destino e a área segura; o caminho por `saved_location_id` envia `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true` somente depois dessa revisão atual.
- **RF-CLI-12:** oferecer, quando houver vaga, o salvamento opcional de um novo ponto manual depois da criação do pedido, sem cancelar ou invalidar o pedido se o cliente recusar, estiver offline, atingir o limite ou se a chamada falhar.

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
- **RNF-11 Concorrência:** a criação de localização salva bloqueia a linha do usuário com `FOR NO KEY UPDATE`, conta e insere na mesma transação, impedindo que requisições paralelas excedam três.
- **RNF-12 Histórico e evidência:** cada pedido referencia seu próprio `DeliveryPoint`; uma `SavedLocation` é somente fonte para cópia transacional e nunca a fonte mutável do destino histórico. Provedor, tipo de mapa e confirmações vêm do fluxo realmente executado e não podem ser preenchidos por constantes para aparentar uma revisão inexistente.

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
- **CA-18:** a tela `Minhas localizações` mostra exatamente zero, uma, duas ou três localizações reais, contador correspondente e ação de adicionar indisponível no limite, sem cards fictícios.
- **CA-19:** a quarta criação, inclusive sob concorrência, retorna `409/SAVED_LOCATION_LIMIT_REACHED`; criações simultâneas para o mesmo cliente nunca deixam mais de três registros.
- **CA-20:** rotas de localização usam o cliente do JWT, nunca um `user_id` escolhido no corpo, e leitura/edição/exclusão de recurso alheio usam a resposta não enumerável do projeto.
- **CA-21:** `OrderCreate` aceita exatamente um de `delivery_point_id` ou `saved_location_id`; o segundo também exige `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true` e cria, na mesma transação, um novo `DeliveryPoint` com origem interna `SAVED_POINT`, provedor/tipo copiados do atalho e confirmações da revisão atual, nunca sintetizadas.
- **CA-22:** editar ou excluir uma localização salva depois de criar um pedido não altera coordenadas, endereço, instruções nem disponibilidade do destino histórico.
- **CA-23:** mover o mapa após escolher uma localização salva altera somente o snapshot do novo pedido; atualizar o atalho exige ação explícita na tela de edição, e as duas confirmações atuais são solicitadas novamente depois da revisão.
- **CA-24:** uma localização com nome e coordenadas válidas pode ser salva sem endereço textual, desde que `map_provider` seja o realmente usado, `map_type` seja `hybrid` ou `satellite` e `region_confirmed`, `exact_point_selected`, `user_confirmed` e `user_confirmed_safe_area` sejam verdadeiros; falha no salvamento opcional posterior não muda o resultado do pedido.

## Matriz de rastreabilidade

| Requisito | Componentes | Contrato principal | Teste esperado |
|---|---|---|---|
| RF-CLI-01 | mobile, auth/users | `/auth/register`, `/auth/login` | backend + widget |
| RF-CLI-04/05 | mobile, delivery_points, admin | `/delivery-points/validate` e `POST` | widget + domínio + admin |
| RF-CLI-07/08/09 | mobile, orders, system_events | `/orders`, `/orders/{id}`, `/ws/orders/{id}` | ownership + paginação + widget + WebSocket |
| RF-CLI-10 | mobile, saved_locations, users | `/saved-locations` e `/saved-locations/{id}` | CRUD + ownership + limite concorrente + evidência real + estados 0–3 |
| RF-CLI-11/12 | mobile, saved_locations, delivery_points, orders | `/orders`, `/saved-locations` | picker/mapa + confirmação atual + snapshot fiel + salvamento posterior não bloqueante |
| RF-ADM-03 | orders, approvals, admin | `/admin/orders/{id}/approve|reject` | RBAC/transição/auditoria |
| RF-ADM-04/05 | missions, admin | prepare/review/download | exportador e componente |
| RF-ADM-06/07 | vehicles, approvals, admin | health/authorize-flight | checks automáticos, três confirmações, TTL e idempotência |
| RF-GTW-01/03 | gateway, missions | authorized/claim/status | idempotência e timeout |
| RF-GTW-04 | telemetry, WebSocket | telemetry/events/ws | normalização e ordenação |
| RF-OPS-01 | gateway, documentação | configuração real/checklist | ensaio manual, nunca CI |

Os detalhes executáveis estão em [API](API.md), [Banco](DATABASE.md), [Plano de testes](TEST_PLAN.md) e [Protocolo](DRONE_PROTOCOL.md).
