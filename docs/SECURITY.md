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
- `.env`, chaves MapTiler, firmware, log e banco local ignorados.

## Dados e privacidade

Coletar apenas nome/contato necessários, coordenada e instrução. Endereço/posição são sensíveis: logs preferem IDs/correlação. Nenhum número, CVV, validade ou titular de cartão é coletado. Telemetria bruta recebe amostragem/retenção; exportação e descarte exigem autorização.

## Ações administrativas

RBAC não é substituído por esconder botão. Aprovação, rejeição, preparação, revisão, autorização, ARM, abortamento e RTL geram evento com ator/hora/motivo. Autorização expira, é de uso único e vinculada à versão/snapshot; mudança crítica invalida. ARM possui endpoint e payload próprios, `Idempotency-Key`, confirmações presenciais, identidade missão/veículo/gateway, snapshot usado, ACK e resultado auditáveis; o endpoint genérico não o aceita.

## Chaves e atribuição MapTiler

As três superfícies não compartilham credencial:

- `MAPTILER_WEB_API_KEY` aparece nos bundles do Flutter Web e admin. Ela não é segredo e deve aceitar somente as origens HTTP/HTTPS exatas autorizadas;
- `MAPTILER_ANDROID_API_KEY` aparece no APK. Observe e valide o `User-Agent` efetivamente enviado pelo app/dispositivo antes de restringi-la;
- `MAPTILER_SERVER_API_KEY` fica somente no FastAPI. Nunca a envie ao navegador/APK nem a inclua em erro, log ou URL retornada ao cliente; em hospedagem, considere credencial de serviço assinada.

A chave recebida durante a migração foi exposta em conversa e deve ser rotacionada antes de demonstração pública. Na inspeção de 20/08, as três variáveis estavam preenchidas, mas compartilhavam o mesmo valor; isso não constitui separação de credenciais. O `.env` impede versionamento acidental, mas não protege uma chave cliente observável em rede/bundle. Crie três substitutas com restrições próprias, troque-as no `.env` ignorado, refaça builds/testes das superfícies e só então revogue a credencial exposta. Configure quotas e alertas.

`MAPTILER_STYLE_URL` guarda somente a URL HTTPS de `style.json`, sem query ou credencial. O projeto não incorpora o visualizador em `iframe` e não usa Static Maps. Atribuição MapTiler/OpenStreetMap e logo MapTiler exigido pelo plano Free permanecem visíveis e linkados; removê-los não é uma otimização permitida.

## Segurança operacional

- modo padrão simulado; `real` exige configuração e reconhecimento explícitos;
- o profile Docker recebe configuração `GATEWAY_CONTAINER_*` isolada e rejeita `real`, `direct` e `mission_planner_forward`; hardware/forwarding executam somente no host;
- `ALLOW_VEHICLE_ARM=false` é independente e conservador e publica `vehicle_arm_enabled`; ARM requer também `flight_commands_enabled=true` e `mission_start_enabled=true`, sem herdar permissão de outro gate;
- requests do gateway exigem chave e `X-Gateway-ID` vinculados ao mesmo `GATEWAY_ID`; query e payload divergentes falham antes de claim, comando ou ACK;
- nenhum startup, readiness, health, upload, autorização, reconnect ou progressão automática arma/decola;
- o único ARM por software é a solicitação administrativa normal para missão `VERIFIED` e reivindicada, origem `SITL` ou `HARDWARE_REAL`, health/preflight completo, modo `STABILIZE`, operador presente e área controlada;
- nunca há force/bypass, safety-off, mudança automática de modo/parâmetros, supressão de pre-arm ou rearmamento automático;
- `202`/ACK de recebimento não prova armamento; conclusão exige `COMMAND_ACK` correlacionado e heartbeat novo/fresco com `armed=true` do alvo correto;
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
| uso indevido da chave de mapas | credenciais separadas, origem/`User-Agent`, quota, alerta e rotação |
| chave de servidor chega ao cliente | proxy autenticado e filtragem de URL/erro/log no FastAPI |
| replay de autorização | versão, TTL, consumo atômico e idempotência |
| coordenada adulterada | propriedade, snapshot após submit, auditoria e revisão no mapa |
| gateway falso | chave separada, rede restrita e identidade registrada |
| missão alterada após revisão | hash/versão e invalidação |
| dado de saúde antigo | timestamp/limite de staleness |
| telemetria simulada confundida com real | origem persistida, badge visível e prontidão conservadora |
| comando duplicado | claim/estado/event ID e confirmação |
| ARM acidental, forçado ou repetido | endpoint dedicado, payload estrito, hold-to-confirm, gates independentes, modo `STABILIZE`, sem force e idempotência/reconciliação sem rearmar |
| ACK MAVLink confundido com estado físico | correlação de comando/alvo + heartbeat posterior `armed=true` + validação final no backend |
| conexão perdida | ArduPilot/failsafe + reconciliação, sem execução repetida |

## Resposta a incidente

Interromper novas autorizações, preservar logs/eventos/arquivo/versão, manter o veículo sob procedimento seguro do operador, rotacionar credenciais afetadas e documentar causa/ação. Não apagar falha para restaurar a demo. Vulnerabilidade de software recebe teste de regressão; incidente de voo exige revisão operacional antes de retomar.

## Risco de dependência acompanhado

Em 2026-08-07, `pip-audit` detectou `PYSEC-2026-1845` no pytest 8.4.2. O risco médio envolve tratamento de `tmpdir` em sistemas UNIX e atingia uma dependência de desenvolvimento, não o runtime publicado. A constraint de desenvolvimento foi elevada para `pytest>=9.0.3,<10` no backend e gateway; ambas as suítes passaram depois da atualização e o `pip-audit` final retornou zero vulnerabilidades conhecidas.

Em 20 de agosto de 2026, `pip check` e `pip-audit` retornaram zero vulnerabilidades conhecidas tanto nos ambientes virtuais quanto nas imagens finais de backend e gateway. No admin, `npm audit` completo e de produção retornou zero, e `npm ci --dry-run`/`npm ls` confirmaram a árvore do lock. Esses resultados são evidência datada, não garantia permanente: repetir os audits depois de mudar locks/constraints e antes de publicar.
