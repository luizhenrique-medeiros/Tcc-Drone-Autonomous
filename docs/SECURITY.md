# Segurança da aplicação e da operação

## Objetivos

Proteger identidade, localização, decisões críticas, missão e veículo; impedir que facilidade de demonstração contorne segurança física.

## Controles de aplicação

- senha com hash moderno e política mínima; nunca logada/devolvida;
- JWT curto, segredo de pelo menos 32 bytes fora do Git e papel validado no backend;
- cadastro público sempre `CUSTOMER`; seed admin explícito;
- chave do gateway separada, rotacionável e restrita à rede;
- CORS por origem, validação Pydantic e respostas sem stack trace;
- propriedade do ponto/pedido, paginação e proteção contra enumeração;
- idempotency key em submissão/decisões/claim/upload;
- dependências fixadas e imagens não executadas como root quando possível;
- `.env`, chave Google, firmware, log e banco local ignorados.

## Dados e privacidade

Coletar apenas nome/contato necessários, coordenada e instrução. Endereço/posição são sensíveis: logs preferem IDs/correlação. Nenhum número, CVV, validade ou titular de cartão é coletado. Telemetria bruta recebe amostragem/retenção; exportação e descarte exigem autorização.

## Ações administrativas

RBAC não é substituído por esconder botão. Aprovação, rejeição, preparação, revisão, autorização, abortamento e RTL geram evento com ator/hora/motivo. Autorização expira, é de uso único e vinculada à versão/snapshot; mudança crítica invalida.

## Chaves Google Maps

Chave Android restrita por package/fingerprint e APIs; chave server-side separada por serviço/IP. Não expor chave de servidor no app e não registrar consultas completas desnecessariamente.

## Segurança operacional

- modo padrão simulado; `real` exige configuração e reconhecimento explícitos;
- nenhum startup, readiness ou teste arma/decola;
- SITL precede bancada; hélices removidas precedem motor; voo manual precede missão;
- operador com RC/Mission Planner e acesso a interrupção permanece responsável;
- geofence, RTL, bateria, GPS, EKF, bússola, RC e failsafes não são desativados;
- pre-arm é investigado, não ocultado;
- área isolada, condições meteorológicas e exigências regulatórias são verificadas pela equipe competente;
- carga nunca sobrevoa pessoas não envolvidas.

## Modelo básico de ameaças

| Ameaça | Controle |
|---|---|
| cliente se torna admin | papel ignorado no cadastro + teste RBAC |
| token/chave vazado | secrets externos, logs filtrados, expiração/rotação |
| replay de autorização | versão, TTL, consumo atômico e idempotência |
| coordenada adulterada | propriedade, snapshot após submit, auditoria e revisão no mapa |
| gateway falso | chave separada, rede restrita e identidade registrada |
| missão alterada após revisão | hash/versão e invalidação |
| dado de saúde antigo | timestamp/limite de staleness |
| comando duplicado | claim/estado/event ID e confirmação |
| conexão perdida | ArduPilot/failsafe + reconciliação, sem execução repetida |

## Resposta a incidente

Interromper novas autorizações, preservar logs/eventos/arquivo/versão, manter o veículo sob procedimento seguro do operador, rotacionar credenciais afetadas e documentar causa/ação. Não apagar falha para restaurar a demo. Vulnerabilidade de software recebe teste de regressão; incidente de voo exige revisão operacional antes de retomar.

## Risco de dependência acompanhado

Em 2026-08-06, `npm audit` reportou duas ocorrências altas derivadas do mesmo aviso `GHSA-qwww-vcr4-c8h2` no React Router. O ataque descrito depende de RSC Actions; este painel é uma aplicação Vite client-side e não oferece React Server Components nem Actions. Isso reduz a aplicabilidade ao desenho atual, mas não elimina o alerta: manter `react-router-dom` atualizado, repetir o audit e adotar uma versão corrigida assim que houver atualização segura para este conjunto de dependências.
