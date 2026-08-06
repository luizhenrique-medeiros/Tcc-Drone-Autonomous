# Plano de demonstração

## Objetivo

Demonstrar fluxo integrado até entrega e retorno. O plano principal prevê drone real apenas depois de todas as portas de segurança; SITL e vídeo são contingências transparentes.

## Preparação comum

- congelar commit, versões, `.env` sem expor segredos e hash da missão;
- migrar/seed e executar testes rápidos;
- criar cliente/admin demo e limpar somente dados permitidos;
- confirmar rede, mapa, painel, API, gateway, Mission Planner e logs;
- imprimir [checklist](PREFLIGHT_CHECKLIST.md), contatos, área e plano de abortamento;
- carregar baterias com procedimento apropriado e confirmar previsão/condições no local.

## Roteiro funcional

1. Cliente entra, vê catálogo demo e produto.
2. Pesquisa uma região, ajusta manualmente o ponto satélite e confirma área.
3. Escolhe pagamento simulado e submete.
4. Admin abre fila/mapa e aprova o pedido.
5. Admin prepara, baixa e revisa a versão no Mission Planner.
6. Gateway mostra saúde; operador conclui checklist.
7. Admin usa a segunda autorização; gateway faz claim/upload.
8. Mobile/admin mostram telemetria, destino, entrega, retorno e conclusão reais ou do modo declarado.
9. Timeline comprova as duas decisões e eventos.

## Plano A — drone real controlado

Só ocorre se SITL, bancada, voo manual e missão curta anteriores estiverem aprovados. Isolar área, manter operador RC/Mission Planner, confirmar carga/CG, checklist e go/no-go. Abortar se qualquer estado/condição divergir. Registrar evidências sem expor dados pessoais.

## Plano B — SITL

Se hardware, clima, área ou checklist impedirem voo, executar o mesmo fluxo com `MAVLINK_MODE=sitl`, rotular claramente “ArduPilot SITL” e preservar logs. Não chamar de voo/Pixhawk real.

## Plano C — vídeo de evidência

Se SITL também falhar no dia, mostrar vídeo previamente registrado com commit, data, modo e checklist identificáveis, seguido de demonstração do software até o ponto seguro. Explicar a falha corrente.

## Critérios de interrupção

Pessoa/animal na área, vento/clima fora do limite, bateria/sensor/RC/telemetria anormal, missão/hash divergente, autorização expirada, log crítico, dano/folga ou operador sem confiança. A apresentação nunca justifica continuar em no-go.

## Registro pós-demo

Salvar resultado, modo usado, versões, logs selecionados, eventos e incidentes; descarregar/armazenar baterias conforme procedimento; revogar credenciais temporárias; registrar pendências. Não marcar etapa posterior com evidência de etapa anterior.
