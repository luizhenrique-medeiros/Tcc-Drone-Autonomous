# Registro de testes: migração em andamento

| Funcionalidade | Evidência | Estado |
|---|---|---|
| Heartbeat, bloqueio, protocolo de upload, releitura e telemetria PX4; encaminhamento QGroundControl | `python -m pytest -q` no gateway: 256 testes passaram | Unitários com mensagens simuladas e um teste UDP local com MAVLink sintético; não é SITL |
| Painel administrativo | `npm.cmd test` (119 testes), `npm.cmd run lint` e `npm.cmd run build` | Aprovados; build avisou sobre tamanho de bundle |
| Lint e formatação do gateway | `ruff check .` e `ruff format --check .` | Aprovados |
| Enumeração de portas | `python -m app.tools.list_ports`: COM7, adaptador Silicon Labs CP210x | Detectada porta, sem confirmar equipamento ou baud rate |
| Upload, verificação e execução PX4 | Não executados | Não implementados para PX4 |
| PX4 SITL completo | Docker instalado, mas daemon indisponível; distribuição WSL de uso geral não encontrada | Pendente |
| QGroundControl → gateway passivo | Em 23/11/2026, QGroundControl Daily encaminhou UDP `localhost:14445`; diagnóstico recebeu heartbeat PX4, system/component 1/1, GPS 3D e posição, em modo receive-only | Recepção validada; origem física versus simulada não foi confirmada independentemente |
| Bateria, versão PX4 e EKF | Não chegaram ao diagnóstico passivo durante 10 segundos | Indisponíveis; sem inferir estado |
| Alerta de pré-voo | QGroundControl exibiu `Pre-Flight Error` | Causa não identificada; requer análise do operador |
| Backend e banco | `/health` retornou `ok`; `/ready` retornou `database: true` | Disponíveis na data do teste |
| Testes automatizados do backend | `python -m pytest -q` no ambiente local de testes | Aprovados, com um teste ignorado e aviso de depreciação de dependência |
| Gateway Docker → backend | A imagem antiga em `simulation` enviava HTTP 401 por não incluir `X-Gateway-ID`; o container foi parado para evitar conflito de identidade | Imagem reconstruída e cabeçalho confirmado em container isolado; novo container ainda não iniciado nem testado com backend |
| QGroundControl → gateway local → backend → banco | Em 23/11/2026 o gateway local passivo recebeu MAVLink em UDP e enviou heartbeats autenticados HTTP 200. A última leitura persistida informou PX4, origem `UNKNOWN`, conectado, GPS 3D e veículo desarmado | Comunicação e persistência validadas; origem física não comprovada |
| Painel administrativo | Após acesso administrativo, a tela `Saúde do veículo` apresentou PX4, heartbeat válido, GPS 3D, modo LOITER, veículo desarmado e gates desabilitados | Recepção visual confirmada; versão e bateria indisponíveis |
| Atualização PX4 no painel | Imagem administrativa reconstruída; a tela passou a mostrar `Autopiloto` e `HARDWARE REAL`, conforme confirmação do operador. O estimador não atendeu aos critérios configurados; bateria e preflight permaneceram indisponíveis | Observação passiva confirmada; origem declarada pelo operador, não detectada automaticamente |
| Estimador e origem declarada | `pytest -q` no gateway: 262 testes passaram; lint e formatação aprovados | Flags MAVLink são avaliadas e expiram; declaração padrão permanece `UNKNOWN` |
| Geofence opcional | Testes do backend e gateway e testes do painel; observação do backend e tela após atualização | Backend e gateway não exigem estado da geofence; RTL e demais checks permanecem separados |
| Estado do estimador PX4 | Observação passiva `ESTIMATOR_STATUS.flags=959` incluiu `ESTIMATOR_CONST_POS_MODE` (128) | Dados do estimador recebidos; critério de navegação não confirmado, sem alterar configuração do drone |
| PX4 SIH isolado | Container `px4io/px4-sitl:latest` com `--network none`; cliente pymavlink compartilhou somente sua rede e enviou ARM normal. Recebeu `COMMAND_ACK` 0 e heartbeat `armed=true` | ARM direto no simulador confirmado. Não testa site, backend, gateway, missão nem Pixhawk; container parado após o teste |
| Rascunho de plano | Testes automatizados da API e geração `.plan` com posição atual, destino e RTL | O arquivo revisado pode ser registrado para auditoria, mas não substitui a missão legada nem foi validado por abertura do rascunho gerado no QGroundControl |
| Gateway em PX4 SIH via roteador | PX4 em container isolado `--network none`; MAVProxy e clientes compartilhavam somente sua rede. `PymavlinkVehicleGateway` em PX4/SITL recebeu heartbeat, e um segundo cliente também recebeu heartbeat durante a mesma sessão | Conexão passiva do adaptador validada em simulação; teste de ARM permaneceu bloqueado. Não valida QGroundControl, Pixhawk, envio de comandos nem fluxo site-gateway |

Mensagens simuladas nos testes unitários não constituem teste PX4 SITL nem
comprovam comportamento do hardware.
