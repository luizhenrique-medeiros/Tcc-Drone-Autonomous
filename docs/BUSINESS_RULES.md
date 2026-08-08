# Regras de negócio

## Usuários e acesso

1. Cadastro público cria apenas `CUSTOMER`.
2. O primeiro `ADMIN` é criado por comando/seed controlado; sua senha nunca aparece no log.
3. Cliente acessa apenas seus pontos e pedidos. Administrador acessa a fila operacional.
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

## Pedido

- Pedido sem item ou ponto confirmado não pode ser submetido.
- Submissão move `DRAFT` para `PENDING_ADMIN_APPROVAL`.
- O cliente lista e detalha somente pedidos cujo `customer_id` vem da sessão autenticada; a API nunca aceita um `user_id` escolhido pelo cliente.
- `DRAFT` é interno ao checkout e não aparece em `Meus pedidos`; após a submissão, `COMPLETED`, `CANCELLED`, `REJECTED` e `FAILED` formam o histórico e os demais estados formam o andamento. A interface mantém ativos em destaque e ordena cada grupo do mais recente para o mais antigo.
- O histórico usa `limit/offset`; detalhes expõem somente milestones sanitizados de `SystemEvent`, sem metadados operacionais, e nunca inventam timestamps ausentes.
- Apenas `ADMIN` decide. Rejeição exige motivo; decisão é imutável e auditada.
- Aprovação move para `APPROVED`; não gera upload, execução ou autorização implícita.
- Cancelamento pelo cliente só é permitido antes da aprovação/execução conforme transição definida.
- Estados terminais não reabrem automaticamente.

## Missão e revisão

- Apenas pedido `APPROVED` recebe missão; há no máximo uma ativa por pedido.
- Preparar calcula origem/destino/distância/altitude, cria waypoints e versão/hash do arquivo.
- `GENERATED` não significa revisada. Exportar e abrir no Mission Planner são eventos registrados.
- O revisor marca `UNDER_REVIEW` e depois `READY_FOR_AUTHORIZATION` para a mesma versão.
- Alterar waypoint, altitude ou versão invalida autorizações existentes.

## Autorização de voo

- É endpoint, botão, tabela e evento distintos da aprovação do pedido.
- Requer administrador autenticado, missão revisada, área controlada, três confirmações humanas e snapshot recente/saudável.
- Conexão, heartbeat, GPS, satélites, EKF, bateria, home, geofence, RTL, armamento, preflight e preparo da missão são checks automáticos. `BLOCKING` impede autorizar; `WARNING` informa sem substituir a validação do servidor.
- As confirmações humanas cobrem área/condições/pessoas/retorno, inspeção física do drone/carga e prontidão do operador. Não existe frase digitada.
- A autorização referencia missão e versão, expira em poucos minutos, é de uso único e não é reutilizada após falha/conclusão.
- Repetir a mesma tentativa com a mesma chave de idempotência devolve a autorização original; uma nova tentativa após a transição é recusada.
- Expiração, mudança de versão/hash ou falha técnica atual revoga e audita a autorização; variação de telemetria que continua dentro dos limites seguros não revoga por simples diferença de amostra.
- O gateway consome a autorização ao reivindicar/enviar; repetição recebe o resultado anterior ou conflito, nunca nova execução.

## Execução, entrega e retorno

- Heartbeat, GPS, EKF, bateria, origem, distância, geofence e RTL são verificados antes do upload.
- Startup e health check nunca armam. O gateway não corrige pre-arm mudando parâmetros.
- Upload, confirmação e início são etapas separadas.
- Após início, ArduPilot/telemetria comandam o estado físico; cliente e painel não inventam progresso por relógio local.
- `DELIVERY_CONFIRMED` registra que a etapa/comando do mecanismo foi alcançada; não prova saída, recebimento ou integridade física do pacote. Missão conclui somente após retorno/pouso conforme evidência, e a entrega real continua exigindo registro operacional.
- Abortamento/RTL registram ator, motivo, resultado e estado do veículo. Uma falha continua visível.

## Auditoria e idempotência

- Operações críticas recebem idempotency/event ID.
- Eventos guardam metadados mínimos; senha, JWT, chave, dados bancários e MAVLink bruto não são persistidos.
- Telemetria com timestamp antigo não substitui snapshot atual.
- Toda divergência operacional é registrada; nunca se converte erro em sucesso para a apresentação.
