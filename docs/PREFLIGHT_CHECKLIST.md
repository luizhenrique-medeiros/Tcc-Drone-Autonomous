# Checklist pré-voo

Este checklist é preenchido por operador responsável para uma missão e versão específicas. Um checkbox no painel não substitui inspeção física.

A revisão operacional e todas as ações na aeronave são feitas no
QGroundControl, com proteções nativas do PX4. Use o painel para baixar
o arquivo, observar a telemetria recebida e registrar evidências. A geração
e a exportação independem dos itens deste checklist.

## 1. Pessoas, área e autorização

- [ ] operador responsável identificado e briefing concluído;
- [ ] área controlada/isolada, sem pessoas ou animais não envolvidos;
- [ ] permissões e condições regulatórias verificadas pela equipe responsável;
- [ ] vento, chuva, visibilidade e iluminação dentro dos limites documentados;
- [ ] rota, home, destino, alternativa e zona de pouso visualmente inspecionados;
- [ ] procedimento de abortamento, RTL e intervenção manual comunicado;
- [ ] aprovação do pedido e revisão da versão da missão registradas;
- [ ] carga/mecanismo adequados ou removidos para o estágio do ensaio.

## 1A. Acompanhamento passivo

- [ ] o QGroundControl está conectado ao veículo pretendido e recebe o heartbeat do alvo;
- [ ] somente o processo responsável pelo enlace abre a porta física;
- [ ] o encaminhamento UDP de observação está configurado conforme [Conexão PX4](CONEXAO_DRONE_PX4.md);
- [ ] o gateway publica a origem declarada e o horário da leitura. Valores ausentes e dados antigos aparecem como tal.

## 2. Estrutura e energia

- [ ] frame, trem de pouso, fixadores e proteção sem dano/folga;
- [ ] hélices corretas, sem trinca, orientação e aperto conferidos (removidas em bancada);
- [ ] motores/ESCs/cabos/conectores sem dano ou aquecimento;
- [ ] CG e carga dentro do limite calculado e fixados;
- [ ] bateria íntegra, balanceada, carregada, tensão e reserva adequadas;
- [ ] power module e alimentação redundante conforme projeto confirmado.

## 3. Navegação e controle

- [ ] firmware e estado da aeronave conferidos no QGroundControl;
- [ ] Home, referências de altitude e comportamento de retorno revisados;
- [ ] mensagens, estado do enlace e verificações nativas do PX4 conferidos;
- [ ] operador dispõe de meio de intervenção conforme a configuração da aeronave.

## 4. Sistema e missão

- [ ] pedido, ponto final e instruções correspondem à revisão do arquivo;
- [ ] origem, sequência de itens, altitude e retorno conferidos no QGroundControl;
- [ ] veículo permanece desarmado durante a revisão e a conferência da missão;
- [ ] a evidência de revisão é registrada com pedido, versão e responsável.

## 5. Go/no-go

Registre responsável, horário, revisão e resultado. Se alguma etapa obrigatória estiver incompleta, encerre a revisão sem operar a aeronave. O operador conduz qualquer tentativa posterior pelo QGroundControl.
