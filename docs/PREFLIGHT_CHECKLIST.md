# Checklist pré-voo

Este checklist é preenchido por operador responsável para uma missão e versão específicas. Um checkbox no painel não substitui inspeção física.

O marco atual é **diagnóstico de comunicação somente leitura**, sem armamento nem voo. Marque upload, comandos ou início como `NO-GO` enquanto `REAL_HARDWARE_ACKNOWLEDGED=false`, `ALLOW_MISSION_UPLOAD=false`, `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false`.

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

Em 17 de agosto de 2026, a primeira tentativa passiva direta falhou porque o Mission Planner ocupava `COM7`. Depois de liberar a porta, dois diagnósticos receberam heartbeat real `1/1`, `STABILIZE`, `armed=false`, e um ciclo limitado publicou sete heartbeats no backend sem escrita MAVLink. Ao final, a COM7 foi desconectada: não há porta serial nem listeners 14550/14551, e o diagnóstico retorna `VEHICLE_PORT_NOT_FOUND`. Assim, o checklist atual continua `NO-GO`; o heartbeat anterior e o TLOG histórico não podem preencher itens ao vivo.

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
- [ ] `REAL_HARDWARE_ACKNOWLEDGED=true` e `ALLOW_MISSION_UPLOAD=true` foram registrados pelo operador; `ALLOW_FLIGHT_COMMANDS=false` e `ALLOW_MISSION_START=false` permanecem;
- [ ] upload concluiu somente com `MISSION_ACK.type=MAV_MISSION_ACCEPTED` do alvo;
- [ ] download posterior confirmou contagem, ordem, tipo e campos permitidos da mesma missão;
- [ ] timeout/retry esgotado ou ACK negativo foi registrado como falha, nunca como upload confirmado;
- [ ] nenhum comando de modo, armamento, início, decolagem ou voo foi enviado durante o ensaio.

### Gate separado para comandos e início

Não combine esta etapa com o primeiro upload. Só depois de SITL, upload/releitura desarmados,
telemetria atual e autorização operacional específica:

- [ ] `ALLOW_FLIGHT_COMMANDS=true` foi habilitado deliberadamente para a sessão;
- [ ] para `START`, `ALLOW_MISSION_START=true` também foi habilitado e a missão está `VERIFIED`;
- [ ] o operador armou fisicamente após todos os checks; o gateway não enviou armamento;
- [ ] o `START` administrativo é fresco, idempotente e foi novamente validado pelo gateway;
- [ ] `PAUSE` recebeu ACK e publicou `PAUSED`; `CONTINUE` só foi solicitado a partir de `PAUSED`;
- [ ] todos os ACKs, falhas, timeouts e intervenções foram preservados em log/evento.

## 5. Go/no-go

Qualquer item obrigatório incompleto é **NO-GO**. Registrar responsável, horário, missão/versão, resultado, observações e motivo do no-go. Depois de alteração de hardware, software, missão, bateria ou estado crítico, repetir os itens afetados e emitir nova autorização. Armar/decolar continua sendo procedimento humano deliberado, não efeito do checkbox.
