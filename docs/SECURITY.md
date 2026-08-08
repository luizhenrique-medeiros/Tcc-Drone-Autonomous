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

RBAC não é substituído por esconder botão. Aprovação, rejeição, preparação, revisão, autorização, abortamento e RTL geram evento com ator/hora/motivo. Autorização expira, é de uso único e vinculada à versão/snapshot; mudança crítica invalida.

## Chaves e atribuição MapTiler

As três superfícies não compartilham credencial:

- `MAPTILER_WEB_API_KEY` aparece nos bundles do Flutter Web e admin. Ela não é segredo e deve aceitar somente as origens HTTP/HTTPS exatas autorizadas;
- `MAPTILER_ANDROID_API_KEY` aparece no APK. Observe e valide o `User-Agent` efetivamente enviado pelo app/dispositivo antes de restringi-la;
- `MAPTILER_SERVER_API_KEY` fica somente no FastAPI. Nunca a envie ao navegador/APK nem a inclua em erro, log ou URL retornada ao cliente; em hospedagem, considere credencial de serviço assinada.

A chave recebida durante a migração foi exposta em conversa e deve ser rotacionada antes de demonstração pública. O `.env` impede versionamento acidental, mas não protege uma chave cliente observável em rede/bundle. Configure quotas e alertas, separe ambientes e revogue a credencial exposta depois de testar as substitutas.

`MAPTILER_STYLE_URL` guarda somente a URL HTTPS de `style.json`, sem query ou credencial. O projeto não incorpora o visualizador em `iframe` e não usa Static Maps. Atribuição MapTiler/OpenStreetMap e logo MapTiler exigido pelo plano Free permanecem visíveis e linkados; removê-los não é uma otimização permitida.

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
| uso indevido da chave de mapas | credenciais separadas, origem/`User-Agent`, quota, alerta e rotação |
| chave de servidor chega ao cliente | proxy autenticado e filtragem de URL/erro/log no FastAPI |
| replay de autorização | versão, TTL, consumo atômico e idempotência |
| coordenada adulterada | propriedade, snapshot após submit, auditoria e revisão no mapa |
| gateway falso | chave separada, rede restrita e identidade registrada |
| missão alterada após revisão | hash/versão e invalidação |
| dado de saúde antigo | timestamp/limite de staleness |
| telemetria simulada confundida com real | origem persistida, badge visível e prontidão conservadora |
| comando duplicado | claim/estado/event ID e confirmação |
| conexão perdida | ArduPilot/failsafe + reconciliação, sem execução repetida |

## Resposta a incidente

Interromper novas autorizações, preservar logs/eventos/arquivo/versão, manter o veículo sob procedimento seguro do operador, rotacionar credenciais afetadas e documentar causa/ação. Não apagar falha para restaurar a demo. Vulnerabilidade de software recebe teste de regressão; incidente de voo exige revisão operacional antes de retomar.

## Risco de dependência acompanhado

Em 2026-08-07, `pip-audit` detectou `PYSEC-2026-1845` no pytest 8.4.2. O risco médio envolve tratamento de `tmpdir` em sistemas UNIX e atingia uma dependência de desenvolvimento, não o runtime publicado. A constraint de desenvolvimento foi elevada para `pytest>=9.0.3,<10` no backend e gateway; ambas as suítes passaram depois da atualização e o `pip-audit` final retornou zero vulnerabilidades conhecidas.

No mesmo ponto de verificação, `npm audit` das dependências de produção do admin retornou zero vulnerabilidades conhecidas. Esses resultados são evidência datada, não garantia permanente: repetir os audits depois de mudar locks/constraints e antes de publicar.
