# Checklist pré-voo

Este checklist é preenchido por operador responsável para uma missão e versão específicas. Um checkbox no painel não substitui inspeção física.

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

## 4. Sistema e missão

- [ ] pedido, cliente, ponto final e instruções correspondem à missão;
- [ ] hash/versão exibidos são os revisados no Mission Planner;
- [ ] distância e altitude respeitam limites;
- [ ] veículo está desarmado durante revisão/upload;
- [ ] health snapshot recebido pelo servidor é recente, possui origem conhecida e todos os checks automatizados passaram;
- [ ] autorização de voo ainda não expirou e pertence à versão;
- [ ] logs/API/gateway estão prontos, sem depender deles para failsafe físico;
- [ ] comando de abortamento/RTL foi verificado no estágio anterior (fake/SITL/bancada).

## 5. Go/no-go

Qualquer item obrigatório incompleto é **NO-GO**. Registrar responsável, horário, missão/versão, resultado, observações e motivo do no-go. Depois de alteração de hardware, software, missão, bateria ou estado crítico, repetir os itens afetados e emitir nova autorização. Armar/decolar continua sendo procedimento humano deliberado, não efeito do checkbox.
