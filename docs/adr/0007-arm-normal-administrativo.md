# ADR 0007 — ARM normal administrativo e fail-closed

**Status:** aceito — 2026-08-21

## Contexto

Depois de upload e releitura, uma missão `VERIFIED` precisa aguardar o estado físico armado antes de aceitar `START`. Depender de uma ação paralela em outra estação dificulta validar o caminho completo painel → backend → gateway, mas transformar armamento em efeito automático de startup, health, upload, autorização ou início criaria uma superfície operacional perigosa.

A documentação anterior adotava a regra conservadora de que o software não enviava armamento. Esta decisão substitui essa regra apenas por uma exceção estreita, explícita e auditável: ARM normal solicitado presencialmente por administrador. Os limites de SITL antes do hardware, autorização em duas etapas e autoridade física do ArduPilot permanecem.

## Decisão

1. ARM possui endpoint próprio: `POST /api/v1/admin/missions/{id}/arm`. O endpoint genérico `/commands/{action}` recusa `ARM`.
2. O payload é estrito, sem campos extras, e contém somente `reason`, `area_clear_confirmed=true`, `operator_present_confirmed=true` e `safety_switch_ready_confirmed=true`. O request exige JWT `ADMIN` e `Idempotency-Key`; retries ambíguos conservam a mesma chave.
3. O backend serializa a decisão com lock da missão e falha fechado. Chave e `X-Gateway-ID` são vinculados ao `GATEWAY_ID` configurado. Só persiste o comando quando a missão está `VERIFIED`, já foi reivindicada, possui veículo e gateway correspondentes, não tem outro comando crítico aberto e o último snapshot do mesmo veículo está fresco, conectado, desarmado e completo.
4. A origem deve ser `SITL` ou `HARDWARE_REAL`. GPS/satélites, EKF, bateria, home/origem, geofence, RTL e preflight precisam estar presentes e aprovados; o modo deve ser exatamente `STABILIZE`.
5. `ALLOW_VEHICLE_ARM=false` é o default e publica `vehicle_arm_enabled`. A ação exige simultaneamente `vehicle_arm_enabled=true`, `flight_commands_enabled=true` e `mission_start_enabled=true`; falso, nulo ou ausente bloqueia.
6. O gateway confirma identidade, fase, idade, origem, saúde, preflight, modo e gates novamente. Antes de escrever no link, persiste o comando como `ACKNOWLEDGED`, que significa apenas recebimento.
7. A única operação de armamento permitida é `MAV_CMD_COMPONENT_ARM_DISARM` com `param1=1`, `param2=0` e `param3..7=0`. Não existe force/bypass, safety-off, mudança de modo, alteração de parâmetros nem supressão de pre-arm.
8. `MAV_RESULT_ACCEPTED` não basta. O gateway correlaciona `COMMAND_ACK` ao comando/alvos, aguarda o resultado final quando receber `IN_PROGRESS` e depois exige heartbeat novo do autopiloto alvo com o bit armado. Esse health é persistido antes de pedir `COMPLETED`; o backend trava o comando e exige `received_at` e `last_heartbeat_at` estritamente posteriores ao ACK, além de origem, identidade e `armed=true`, conservando o snapshot usado como evidência.
9. ARM não inicia a missão nem a move para `EXECUTING`. `START` continua sendo uma solicitação administrativa posterior e independente, bloqueada enquanto ARM estiver aberto e aceita somente com health armado fresco. `ABORT` cancela ARM ainda `PENDING`; se ARM já estiver `ACKNOWLEDGED`, o resultado físico incerto deve ser resolvido antes de outro comando.
10. Não há rearmamento automático. ARM `PENDING` que encontra o veículo já armado é reconciliado sem escrita e sem alegar ACK MAVLink. Depois de restart, ARM `ACKNOWLEDGED` só conclui quando o heartbeat atual confirma `armed=true`; falso, nulo, timeout, ACK negativo ou resultado incerto termina em falha sem novo envio. Qualquer heartbeat novo que mostre `armed=true` durante uma tentativa sem ACK interrompe os retries, mesmo se depois houver `armed=false`. Desarmamento posterior nunca dispara ARM.

## Consequências

O painel ganha uma ação crítica adicional e o backend precisa persistir o gate, ampliar o tipo de comando e auditar confirmações/resultado. O gateway precisa separar ACK de recebimento, ACK MAVLink e evidência física por heartbeat. Essa complexidade é intencional: impede que sucesso HTTP ou ACK isolado seja apresentado como armamento.

`SIMULATION` não é elegível para esse endpoint, e testes fake continuam provando apenas lógica. SITL deve validar o protocolo antes de qualquer bancada; hardware real exige checklist, área controlada, operador presente, meio imediato de desarmar/intervir e evidência separada. Aceitar este ADR não constitui prova de SITL, Pixhawk, motores ou voo.

## Relação com decisões anteriores

Este ADR refina o [ADR 0004](0004-sitl-antes-do-hardware.md) e o [ADR 0006](0006-autorizacao-em-duas-etapas.md). Ele não reúne aprovação, autorização, ARM e `START`: as quatro decisões continuam separadas.
