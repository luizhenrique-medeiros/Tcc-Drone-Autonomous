# Mission Planner e formato de missão

## Geração

Para pedido aprovado, o backend cria uma versão imutável com origem, decolagem, destino, espera/entrega, retorno e pouso. Coordenadas vêm do ponto final validado; altitude vem de configuração, nunca do cliente.

## Exportação QGC WPL 110

O arquivo texto começa com `QGC WPL 110`. Cada linha representa índice, current, frame, command, params 1–4, latitude, longitude, altitude e autocontinue, separados por tab. O exportador registra SHA-256, versão, data e administrador.

O formato ser aceito pelo Mission Planner não torna a rota segura. O operador deve:

1. baixar a versão exibida no painel;
2. abrir/importar em Flight Plan;
3. conferir home, frames, comandos, altitude, geofence, terreno, destino, retorno e pouso;
4. salvar evidência e marcar a mesma versão como revisada;
5. não autorizar se houver divergência.

## Upload MAVLink

Após autorização válida, o gateway aguarda heartbeat, identifica veículo, refaz preflight e usa o protocolo de missão MAVLink com timeout. Ele envia a contagem e os itens canônicos sem disparar `CLEAR_ALL` indiscriminadamente, confirma o ACK, relê a missão enviada e compara campos permitidos antes de publicar o resultado. Upload não equivale a início.

Início exige autorização ainda válida/consumida de forma atômica e procedimento operacional. O gateway nunca arma no startup ou health check. Mission Planner permanece aberto para monitoramento, mensagens e logs.

## SITL

SITL valida parsing, upload, ACK, telemetria, chegada, retorno, perda de link e abortamento antes do hardware. Scripts usam WSL 2 quando necessário. Resultados ficam separados dos testes unitários.

## Pixhawk real

`MAVLINK_MODE=real`, conexão explícita e confirmação externa são necessários. Validar primeiro comunicação e sensores, depois motores sem hélices, voo manual, missão curta sem carga e somente então carga leve/mecanismo. Parâmetros e pinagem não são definidos por este software sem confirmação da montagem.

## Limites

Não automatizamos a GUI do Mission Planner, não ignoramos pre-arm, não mudamos parâmetros para “fazer funcionar” e não afirmamos upload/voo real sem log/evidência. Telemetria normalizada complementa, não substitui, a estação de solo.
