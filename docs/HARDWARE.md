# Hardware real

## Estado e princípio

Este documento prepara a integração, mas não confirma montagem. O único controlador explicitamente informado é a **Pixhawk 6C** com **ArduPilot**. Modelo de frame, GPS, rádio, receptor, ESC, motor, hélice, bateria, power module e mecanismo de entrega ainda precisam de part numbers e diagrama aprovados. Não se inventam pinagens nem parâmetros.

## Inventário a confirmar

| Componente | Função | Informação necessária antes de ligar |
|---|---|---|
| Pixhawk 6C | autopiloto | revisão, firmware suportado, alimentação correta |
| GPS + bússola | posição/heading | modelo, orientação e cabo/porta confirmados |
| telemetria | link Mission Planner/gateway | modelo, frequência legal, níveis e porta |
| receptor/rádio RC | controle e intervenção | protocolo, bind, failsafe e operador |
| power module/bateria | alimentação/medição | química, células, tensão/corrente, conectores |
| ESCs/motores/hélices | propulsão | compatibilidade elétrica/mecânica e sentido |
| frame/trem de pouso | estrutura | carga útil, CG, fixação e vibração |
| mecanismo de carga | entrega | massa, alimentação, retenção, fail-safe |

## Conexão em bancada

1. Produzir diagrama físico com manuais oficiais dos part numbers.
2. Inspecionar polaridade, tensão, isolamento, fixação e continuidade.
3. Alimentar Pixhawk por fonte/power module apropriado; USB não alimenta propulsão.
4. Conectar Mission Planner, identificar placa/firmware e salvar backup de parâmetros.
5. Calibrar sensores conforme procedimento oficial no local adequado.
6. Confirmar RC/failsafes, geofence e RTL com hélices removidas.
7. Testar gateway apenas para leitura/heartbeat; depois upload sem armar.
8. Testar motores individualmente sem hélices e com contenção/área segura.

## Pixhawk, ArduPilot e Mission Planner

Firmware/frame e parâmetros só são definidos após a montagem. O software não desativa `ARMING_CHECK`, geofence ou failsafes, nem força EKF/GPS. Mission Planner permanece ferramenta de calibração, mensagens, logs e operação.

## Energia e propulsão

Calcular corrente máxima, capacidade, C-rating, autonomia com reserva, peso, empuxo e CG a partir dos componentes reais. `MIN_BATTERY_PERCENT` do software não substitui limites de célula/tensão definidos pela equipe. Bateria danificada, inchada, quente ou fora de balanceamento interrompe o ensaio.

## Telemetria e RF

Confirmar frequência/potência permitidas no local, antenas afastadas de interferência, baud/porta e coexistência com RC/GPS. Perda de link deve acionar comportamento previamente testado no SITL e bancada; gateway não assume que internet e rádio falharão juntos.

## Mecanismo de entrega

Definir retenção mecânica, massa/CG, comando, confirmação e estado seguro sem carga. Falha não pode liberar carga sobre pessoas/animais. Acionamento real só entra depois do voo básico validado e análise de risco.

## Limitações atuais

- nenhuma pinagem validada;
- nenhum frame/propulsão/bateria identificado;
- nenhuma conexão Pixhawk executada nesta implementação de software;
- nenhuma calibração, bancada, motor, voo manual, missão ou entrega real comprovados.

Use [Checklist](PREFLIGHT_CHECKLIST.md), [Segurança](SECURITY.md) e [Plano de demonstração](DEMO_PLAN.md) para registrar evidências.
