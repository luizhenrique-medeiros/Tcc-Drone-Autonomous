# Regras de negócio

## Usuários e acesso

1. Cadastro público cria apenas `CUSTOMER`.
2. O primeiro `ADMIN` é criado por comando/seed controlado; sua senha nunca aparece no log.
3. Cliente acessa apenas seus pontos de pedido, localizações salvas e pedidos. Administrador acessa a fila operacional.
4. O gateway possui chave própria e não usa JWT de usuário nem acessa o banco.

## Produtos, carrinho e pagamento

- Produtos são dados acadêmicos reprodutíveis; indisponível não entra em novo pedido.
- Quantidade deve ser positiva. Nome e preço são copiados para o item ao criar o pedido.
- Totais usam decimal: subtotal + entrega - desconto, nunca `float`.
- Pagamento registra apenas um enum simulado. Número, validade, CVV e titular não entram em UI, request, log ou banco.

## Ponto de entrega

- A localização atual e o endereço pesquisado são aproximações e não viram destino automaticamente.
- A etapa final exige mapa satélite, movimento/posicionamento manual, coordenadas finais e confirmação explícita.
- Latitude fica entre -90 e 90; longitude entre -180 e 180.
- O cliente confirma que avaliou área aberta; isso não substitui avaliação do administrador/operador.
- O backend calcula e registra a distância da base para auditoria, mas não limita a seleção ou a submissão do pedido por cobertura. O limite operacional de missão continua no gateway.
- Após submissão, coordenadas não são alteradas silenciosamente. Um local inadequado causa rejeição ou solicitação de nova seleção.

## Localizações salvas

- `SavedLocation` é um atalho reutilizável e mutável do cliente; `DeliveryPoint` é o snapshot imutável do destino de um pedido. Eles não são a mesma entidade.
- Cada cliente pode possuir de zero a três localizações salvas. O limite não restringe quantos destinos diferentes podem ser usados em pedidos.
- O nome, após remover espaços externos, é obrigatório e possui de 1 a 40 caracteres. Latitude e longitude válidas são obrigatórias; endereço, instruções e precisão são opcionais. O atalho também persiste o `map_provider` realmente usado, `map_type` restrito a `hybrid` ou `satellite` e `region_confirmed`, `exact_point_selected`, `user_confirmed` e `user_confirmed_safe_area` produzidos pelo mesmo fluxo.
- O proprietário vem exclusivamente do JWT. O corpo não escolhe `user_id`, e um cliente não lê, altera, exclui nem usa a localização de outro.
- Para criar, a mesma transação executa `SELECT ... FOR NO KEY UPDATE` na linha do cliente, conta suas localizações e insere somente se o total for menor que três. O lock serializa criações concorrentes do mesmo cliente; um `SELECT count(...)` isolado não é suficiente.
- Ao atingir o limite, a API retorna `409/SAVED_LOCATION_LIMIT_REACHED`; nenhuma localização existente é substituída automaticamente.
- Criar e editar reutilizam o mesmo fluxo MapLibre/MapTiler de busca, mapa híbrido ou satélite e coordenada final. A criação só é aceita quando as quatro confirmações persistidas são verdadeiras; provider, tipo e flags descrevem o fluxo realmente concluído e nunca são preenchidos artificialmente pelo servidor. A edição é uma ação explícita e pode alterar nome, ponto e instruções.
- Excluir exige confirmação simples na interface, sem frase digitada. A exclusão remove apenas o atalho e nunca percorre pedidos antigos.
- A lista da conta exibe somente registros existentes, em quantidade dinâmica, com contador `0 de 3` a `3 de 3`; erro ou offline não gera dados fictícios.

## Pedido

- Pedido sem item ou ponto confirmado não pode ser submetido.
- A criação recebe exatamente um de `delivery_point_id` ou `saved_location_id`; enviar nenhum ou ambos é inválido. O segundo caminho exige ainda `saved_location_review_confirmed=true` e `saved_location_safe_area_confirmed=true`, informados somente após a revisão atual no mapa.
- Com `delivery_point_id`, o backend valida que o ponto final confirmado pertence ao cliente. Com `saved_location_id`, valida a propriedade e copia coordenadas, dados auxiliares, `map_provider` e `map_type` persistidos para um novo `DeliveryPoint`, com origem interna `SAVED_POINT`, na mesma transação que cria o pedido. As confirmações do snapshot refletem a revisão atual recebida no request; o servidor não presume nem sintetiza evidência.
- Escolher uma localização salva apenas centraliza o mesmo mapa do checkout. O cliente revisa e confirma novamente o ponto e a área segura; mover o ponto ou alterar as instruções para aquele pedido usa um novo `DeliveryPoint` manual e modifica somente o snapshot, nunca o atalho.
- Editar ou excluir `SavedLocation` depois da criação não altera nem invalida o `DeliveryPoint` histórico.
- Salvar um novo ponto manual como atalho é opcional e ocorre em chamada separada depois de o pedido ser criado. O aplicativo não aguarda essa chamada para concluir o checkout; recusa do cliente, latência, limite, ausência de endereço, offline ou falha não revertem nem bloqueiam o pedido e geram, no máximo, um aviso posterior sobre o atalho.
- Se a API devolver `401` durante o envio, o checkout pede nova autenticação da mesma conta e preserva o carrinho, o ponto de entrega e a forma de pagamento. O cliente confirma o envio novamente. O reenvio do mesmo checkout reaproveita as chaves de idempotência para evitar pedidos duplicados.
- Submissão move `DRAFT` para `PENDING_ADMIN_APPROVAL`.
- O cliente lista e detalha somente pedidos cujo `customer_id` vem da sessão autenticada; a API nunca aceita um `user_id` escolhido pelo cliente.
- `DRAFT` é interno ao checkout e não aparece em `Meus pedidos`; após a submissão, `COMPLETED`, `CANCELLED`, `REJECTED` e `FAILED` formam o histórico e os demais estados formam o andamento. A interface mantém ativos em destaque e ordena cada grupo do mais recente para o mais antigo.
- O histórico usa `limit/offset`; detalhes expõem somente milestones sanitizados de `SystemEvent`, sem metadados operacionais, e nunca inventam timestamps ausentes.
- Apenas `ADMIN` decide. Rejeição exige motivo; decisão é imutável e auditada.
- Aprovação move para `APPROVED`; não gera upload, execução ou autorização implícita.
- Cancelamento pelo cliente só é permitido antes da aprovação/execução conforme transição definida.
- Estados terminais não reabrem automaticamente.

## Missão e revisão

- Apenas pedido aprovado recebe missão. Há no máximo uma missão ativa por pedido.
- A exportação usa a origem planejada, o destino confirmado e a altitude relativa da revisão. O Home planejado admite altitude AMSL opcional para revisão no QGroundControl.
- Aprovação, geração e exportação são fatos distintos. O download grava evento com administrador, pedido, missão, versão, hashes e arquivo. A exportação independe da telemetria.
- O painel pode registrar e recuperar o arquivo revisado da versão atual conferindo seu hash.

## Operação do veículo

- O operador importa e revisa o plano e controla a aeronave pelo QGroundControl. O PX4 aplica suas proteções nativas.
- O gateway real recebe mensagens passivamente. Consultas ativas, comandos, transferências e reprodução de solicitações anteriores ficam fora do fluxo operacional.

## Execução, entrega e retorno

- Leituras ausentes são indisponíveis. Telemetria antiga não substitui snapshot atual.
- O download ou registro do plano não comprova upload ou execução. Telemetria geral do veículo não é associada ao último pedido exportado.
- Uma missão é vinculada automaticamente quando as evidências identificam o veículo e uma revisão atual única. O administrador também pode selecionar veículo e revisão exportada para acompanhar o voo. Nessa associação os índices são mostrados como sequências do protocolo até existir verificação do plano. Uma divergência posterior suspende o vínculo dos itens.
- Observação de waypoint, pouso, retorno ou desarmamento não conclui entrega. Informar todos os itens concluídos, pousar e desarmar são evidências separadas do recebimento físico.
- Um administrador confirma a entrega física com evidência. O pedido concluído mantém ator, data e evento de confirmação. A revisão da missão conserva seu próprio estado.

## Auditoria e idempotência

- Eventos guardam metadados mínimos, sem segredos ou mensagens MAVLink brutas.
- Confirmações repetidas não geram novas conclusões ou eventos. Resultados de ensaios legados continuam identificados pela origem.
