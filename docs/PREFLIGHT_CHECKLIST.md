# Checklist pré-voo

Este checklist é preenchido por operador responsável para uma missão e versão específicas. Um checkbox no painel não substitui inspeção física.

O marco atual é **diagnóstico de comunicação somente leitura**, sem armamento nem voo. Marque upload, ARM, comandos ou início como `NO-GO` enquanto `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false`, `ALLOW_MISSION_START=false` e `ALLOW_VEHICLE_ARM=false`.

## Representação no painel

Este documento continua sendo o procedimento operacional completo para SITL, bancada e voo controlado. A interface não reproduz cada linha como checkbox. Ela apresenta automaticamente os sinais disponíveis do veículo e da missão como `PASS`, `WARNING` ou `BLOCKING` e agrupa somente o que depende de decisão humana em três confirmações:

- área, clima, pessoas, decolagem, destino e retorno livres/controlados;
- drone, estrutura, energia, carga e mecanismo inspecionados fisicamente;
- operador responsável presente, pronto para iniciar e intervir.

Não há frase digitada. Qualquer `BLOCKING` técnico mantém a autorização desabilitada; a saúde é atualizada ao abrir o modal e o backend e o gateway repetem as verificações críticas independentemente do estado visual do navegador. Variações normais dentro dos limites seguros permanecem válidas; expiração, mudança da missão ou falha técnica atual exigem nova autorização e geram evento auditável.

## 1. Pessoas, área e autorização

- [ ] operador responsável identificado e briefing concluído;
- [ ] área controlada/isolada, sem pessoas ou animais não envolvidos;
- [ ] permissões e condições regulatórias verificadas pela equipe responsável;
- [ ] vento, chuva, visibilidade e iluminação dentro dos limites documentados;
- [ ] rota, home, destino, alternativa e zona de pouso visualmente inspecionados;
- [ ] procedimento de abortamento, RTL e intervenção manual comunicado;
- [ ] aprovação do pedido e revisão da versão da missão registradas;
- [ ] carga/mecanismo adequados ou removidos para o estágio do ensaio.

## 1A. Topologia e diagnóstico passivo

- [ ] topologia escolhida e registrada como `direct` ou `mission_planner_forward`, sem combinação implícita;
- [ ] em `direct`, `MAVLINK_CONNECTION=COM7`, `MAVLINK_BAUD=57600` e Mission Planner totalmente desconectado/fechado antes de o gateway abrir a serial;
- [ ] em `mission_planner_forward`, Mission Planner é o único dono de `COM7` a 57600 e o gateway usa `MAVLINK_FORWARD_CONNECTION=udpin:127.0.0.1:14551`;
- [ ] o AutoConnect **Mavlink alt port**, UDP 14551 **Inbound**, está desabilitado; um listener inbound não é `Mavlink Mirror` e não pode ocupar a porta do gateway;
- [ ] `SETUP` → `Advanced` → `Mavlink Mirror` usa **UDP Client** para `127.0.0.1:14551`, com **Write access** desmarcado;
- [ ] `SETUP` → `Advanced` → `MAVLink Inspector` mostra `sysid`, `compid`, heartbeat e taxas que serão comparados com o gateway;
- [ ] o diagnóstico abre/recebe/fecha o transporte sem qualquer `*_send`, `COMMAND_LONG`, missão, mudança de modo ou armamento;
- [ ] porta ausente, acesso negado, zero bytes, bytes inválidos e timeout de heartbeat são registrados como resultados distintos e todos mantêm escrita/voo bloqueados;
- [ ] o processo dono da COM e os listeners UDP 14550/14551 foram verificados imediatamente antes do ensaio.

Em 20 de agosto de 2026, o diagnóstico e o gateway host receberam diretamente cinco minutos de
telemetria COM7/57600, sem escrita: 129 snapshots `HARDWARE_REAL`, alvo `1/1`, `STABILIZE`, sempre
`armed=false`, bateria 74–75%. O GPS chegou a fix 3/5 satélites, mas terminou fix 1/0;
EKF/preflight ficaram falsos e home/origin ausentes. Após parar, o snapshot ficou stale. O
forwarding em 14551 expirou sem heartbeat porque ainda estava configurado como Inbound. Assim, o
checklist atual continua `NO-GO`; link real e bateria observada não preenchem GPS, EKF, home,
SITL, upload, ensaio de motor ou voo.

## 2. Estrutura e energia

- [ ] frame, trem de pouso, fixadores e proteção sem dano/folga;
- [ ] hélices corretas, sem trinca, orientação e aperto conferidos (removidas em bancada);
- [ ] motores/ESCs/cabos/conectores sem dano ou aquecimento;
- [ ] CG e carga dentro do limite calculado e fixados;
- [ ] bateria íntegra, balanceada, carregada, tensão e reserva adequadas;
- [ ] power module e alimentação redundante conforme projeto confirmado.

## 3. Navegação e controle

- [ ] firmware/frame/versão e parâmetros esperados conferidos no Mission Planner;
- [ ] GPS 3D e número de satélites acima do limite configurado;
- [ ] EKF saudável, bússola/orientação coerentes e ausência de mensagem crítica;
- [ ] home/origem corretos e altitude/referência revisadas;
- [ ] geofence habilitada e compatível com a área;
- [ ] RTL altitude/destino/comportamento revisados;
- [ ] RC conectado, modos e failsafe testados; operador mantém controle;
- [ ] telemetria e heartbeat estáveis, antenas corretas e bateria exibida coerente.
- [ ] painel identifica `HARDWARE REAL`, `received_at` recente e nenhum campo obrigatório como `--`;
- [ ] Mission Planner e gateway recebem o mesmo veículo sem disputar a porta COM.
- [ ] o heartbeat recebido pertence ao `system/component` alvo; abrir a porta ou receber bytes não foi aceito como `connected=true`;
- [ ] estado ao vivo e TLOG histórico estão rotulados separadamente, sem reutilizar amostra antiga como snapshot atual;
- [ ] taxas de mensagens têm um único responsável; no ensaio passivo o gateway não envia `MAV_CMD_SET_MESSAGE_INTERVAL` nem compete com `REQUEST_DATA_STREAM` do Mission Planner.

## 4. Sistema e missão

- [ ] pedido, cliente, ponto final e instruções correspondem à missão;
- [ ] hash/versão exibidos são os revisados no Mission Planner;
- [ ] distância e altitude respeitam limites;
- [ ] veículo está desarmado durante revisão/upload;
- [ ] health snapshot recebido pelo servidor é recente, possui origem conhecida e todos os checks automatizados passaram;
- [ ] autorização de voo ainda não expirou e pertence à versão;
- [ ] logs/API/gateway estão prontos, sem depender deles para failsafe físico;
- [ ] comando de abortamento/RTL foi verificado no estágio anterior (fake/SITL/bancada).

### Gate separado para upload desarmado

Não marque estes itens no diagnóstico passivo. Uma sessão posterior exige autorização específica, veículo desarmado e evidência ao vivo:

- [ ] no modo encaminhado, **Write access** foi habilitado deliberadamente só para esta sessão;
- [ ] `REAL_HARDWARE_ACKNOWLEDGED=true` e `ALLOW_MISSION_UPLOAD=true` foram registrados pelo operador; `ALLOW_FLIGHT_COMMANDS=false`, `ALLOW_MISSION_START=false` e `ALLOW_VEHICLE_ARM=false` permanecem;
- [ ] upload concluiu somente com `MISSION_ACK.type=MAV_MISSION_ACCEPTED` do alvo;
- [ ] download posterior confirmou contagem, ordem, tipo e campos permitidos da mesma missão;
- [ ] timeout/retry esgotado ou ACK negativo foi registrado como falha, nunca como upload confirmado;
- [ ] nenhum comando de modo, armamento, início, decolagem ou voo foi enviado durante o ensaio.

### Gate separado para ARM, comandos e início

Não combine esta etapa com o primeiro upload. Só depois de SITL, upload/releitura desarmados,
telemetria atual e autorização operacional específica:

- [ ] a missão está `VERIFIED`, já reivindicada pelo gateway ligado ao mesmo veículo e sem outro comando crítico aberto;
- [ ] a origem ao vivo é `SITL` ou `HARDWARE_REAL`; em hardware, `REAL_HARDWARE_ACKNOWLEDGED=true` foi registrado para esta sessão;
- [ ] `ALLOW_VEHICLE_ARM=true`, `ALLOW_FLIGHT_COMMANDS=true` e `ALLOW_MISSION_START=true` foram habilitados deliberadamente; `vehicle_arm_enabled`, `flight_commands_enabled` e `mission_start_enabled` aparecem verdadeiros no snapshot;
- [ ] snapshot/heartbeat são frescos e pertencem ao alvo correto; GPS/satélites, EKF, bateria, home/origem, geofence, RTL e preflight estão completos e aprovados;
- [ ] o veículo está desarmado e em `STABILIZE`; o operador está presente, a área dos motores está livre/controlada e o safety switch está pronto;
- [ ] o administrador registrou motivo e as três confirmações do payload dedicado; a solicitação ARM é fresca e idempotente;
- [ ] não existe opção/valor de force, bypass, safety-off, mudança automática de modo/parâmetros ou supressão de pre-arm;
- [ ] `ACKNOWLEDGED` foi persistido antes da transmissão normal e o `COMMAND_ACK` recebido corresponde ao comando e aos alvos esperados;
- [ ] um heartbeat posterior do mesmo veículo confirmou `armed=true` e foi persistido antes de marcar ARM `COMPLETED`;
- [ ] o `START` administrativo ocorreu somente em ação posterior, fresca e idempotente, e foi novamente validado pelo gateway; ARM não iniciou a missão;
- [ ] `PAUSE` recebeu ACK e publicou `PAUSED`; `CONTINUE` só foi solicitado a partir de `PAUSED`;
- [ ] timeout, ACK negativo, restart, resultado incerto ou desarmamento não produziram reenvio/rearmamento automático;
- [ ] todos os ACKs, heartbeats de confirmação, falhas, timeouts e intervenções foram preservados em log/evento.

## 5. Go/no-go

Qualquer item obrigatório incompleto é **NO-GO**. Registrar responsável, horário, missão/versão, resultado, observações e motivo do no-go. Depois de alteração de hardware, software, missão, bateria ou estado crítico, repetir os itens afetados e emitir nova autorização. Solicitar ARM e solicitar `START` continuam sendo decisões humanas deliberadas e separadas; nunca são efeito de checkbox, health, startup ou reconexão.
