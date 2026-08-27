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

## Preparação e revisão

Uma ação posterior prepara missão, exibe versão/hash/waypoints e oferece download QGC WPL. O operador abre no Mission Planner e registra início/conclusão da revisão. Mudar a rota gera versão nova e invalida autorização anterior.

## Saúde automática, confirmações físicas e segunda decisão

Antes de autorizar, `AutomaticPreflightChecks` mostra conexão, origem da evidência, idade do heartbeat, modo, armamento, GPS/satélites, EKF, bateria, home, geofence, RTL, origem/destino/distância/altitude, versão e resultados preflight. Campo desconhecido é `--`, nunca zero/`false`. Cada linha é `PASS`, `WARNING` ou `BLOCKING`; snapshot vencido, origem desconhecida, campo obrigatório nulo, desconexão ou condição técnica insegura são bloqueantes. Um aviso permanece visível, mas não simula falha nem bloqueia quando o backend não o define como crítico. Os mínimos de GPS e bateria e a faixa de aviso de bateria chegam no próprio contrato de saúde; o React não mantém cópias desses limites configuráveis.

O operador confirma somente três grupos que dependem de inspeção humana:

1. área, condições, pessoas, decolagem, destino e retorno livres/controlados;
2. drone, carga, fixação e mecanismo inspecionados fisicamente;
3. operador responsável pronto para iniciar e intervir.

`Autorizar missão` atualiza missão e saúde antes de abrir um único modal final com pedido, destino, distância, bateria, GPS/EKF, veículo/modo, versão/hash e avisos. Se a leitura anterior estava bloqueante, `Revalidar para autorizar` permite buscar um snapshot novo, mas não abre o modal enquanto o bloqueio persistir. Os botões finais são `Cancelar` e `Autorizar missão`; não existe campo ou validação por frase digitada. O endpoint próprio persiste os três nomes canônicos do checklist, missão/versão/hash, administrador, operador, snapshot, validade curta, uso único, idempotência e auditoria de expiração/revogação/consumo. O registro mais recente volta no detalhe da missão após reload com nome real, status e datas; expirada ou revogada nunca é apresentada como aguardando consumo. A ação não aparece como continuação automática do botão Aprovar pedido.

## Acompanhamento e incidentes

Após o upload, o painel diferencia `UPLOADED` (ACK recebido) de `VERIFIED` (conteúdo relido e comparado). `VERIFIED` não arma nem inicia nada. Em uma missão verificada e já reivindicada, o painel pode oferecer `Solicitar armamento` somente quando o snapshot pertence ao mesmo veículo/gateway, está fresco, conectado, desarmado e completo, possui origem `SITL` ou `HARDWARE_REAL`, modo `STABILIZE`, preflight aprovado e os gates `vehicle_arm_enabled`, `flight_commands_enabled` e `mission_start_enabled` verdadeiros. Esses blockers visuais são explicativos; backend e gateway refazem a decisão fail-closed.

O modal de ARM mostra missão, veículo, origem, modo, estado de armamento e horário da leitura. O administrador informa uma justificativa e confirma presencialmente área livre/controlada, operador presente e safety switch pronto; manter o botão pressionado por dois segundos reduz acionamento acidental. A chamada usa o endpoint dedicado `POST /api/v1/admin/missions/{id}/arm`, payload sem campos extras e uma chave de idempotência estável enquanto a mesma tentativa tiver resultado ambíguo. Não há opção de force, bypass ou alteração de parâmetros.

Depois do `202`, a interface guarda o `command.id`, consulta o comando exato e atualiza o snapshot canônico em paralelo. `PENDING` e `ACKNOWLEDGED` continuam pendentes; `FAILED` encerra imediatamente e mostra `result_detail`. Mesmo `COMPLETED` só vira `Veículo armado` quando há heartbeat novo e fresco do mesmo veículo com `armed=true`; timeout ou erro não é convertido em sucesso e exige inspeção antes de uma nova solicitação. O armamento não dispara `START`, e desarmamento posterior nunca causa rearmamento automático.

O botão `Solicitar START` só fica disponível quando o snapshot pertence ao mesmo veículo da missão, está fresco, conectado, com heartbeat atual e informa simultaneamente `flight_commands_enabled=true`, `mission_start_enabled=true` e `armed=true`; o backend e o gateway repetem as validações, portanto o estado visual não é autorização. `PAUSE` é oferecido apenas nos estados executáveis e `CONTINUE` somente em `PAUSED`. Todas as ações usam endpoint, motivo quando aplicável, chave de idempotência, comando persistido e ACK do gateway.

WebSocket só fica visualmente conectado depois do evento de confirmação do servidor, agrupa rajadas de atualização e, após desconexão, marca dados vencidos e refaz o snapshot canônico. ARM, `START`, `PAUSE`, `CONTINUE`, abortamento e RTL são ações separadas; ações críticas usam confirmação e motivo. O operador continua usando Mission Planner como estação de segurança e mantém meio imediato de intervenção.

Alertas operacionais são derivados dos snapshots canônicos e informam o que ocorreu, impacto, última evidência e ação sugerida. A combinação de tipo/veículo/missão é deduplicada e respeita cooldown; alertas não transformam valor ausente em falha física nem inventam diagnóstico.

## Auditoria

Timeline registra ator, decisão/motivo, versão, revisão, checklist, autorização/expiração/consumo, veículo, upload, execução, entrega, retorno e falhas. A UI não permite apagar evidência.

## Estados de interface

Toda página cobre loading, vazio, erro explícito com retry, sucesso, dados vencidos e sessão expirada. Erro de API não é apresentado como lista vazia. Tablet reorganiza painéis; ações críticas continuam próximas do resumo e nunca desaparecem em scroll sem contexto.
