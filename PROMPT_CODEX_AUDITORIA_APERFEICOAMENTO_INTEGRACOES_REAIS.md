# Prompt para o Codex — Auditoria, Aperfeiçoamento e Integrações Reais

Você está trabalhando em um projeto já criado e parcialmente implementado chamado **Drone de Entregas via Coordenadas**.

Não recrie o projeto do zero.

Sua tarefa é:

1. ler todo o repositório;
2. entender a arquitetura e o fluxo atual;
3. executar uma auditoria completa;
4. corrigir problemas de software que possam ser corrigidos no código;
5. organizar o projeto somente quando houver necessidade real;
6. concluir as integrações entre aplicativo, aplicação web, painel administrativo, backend, banco, Mission Planner, Pixhawk e drone;
7. substituir dados operacionais fictícios por estados reais ou por indicação explícita de indisponibilidade;
8. entregar um relatório técnico completo do que foi corrigido e do que ainda depende de ação manual.

O resultado deve ser um projeto integrado, verificável e preparado para uso com hardware real em ambiente controlado.

---

# 1. Regras obrigatórias antes de alterar o projeto

Antes de modificar qualquer arquivo:

1. Leia integralmente:
   - `AGENTS.md`;
   - `README.md`;
   - todos os documentos em `docs/`;
   - arquivos de configuração;
   - arquivos de ambiente de exemplo;
   - scripts;
   - Docker Compose;
   - código do backend;
   - código do Flutter;
   - código da aplicação web;
   - código do painel administrativo;
   - código do `drone_gateway`;
   - migrações e testes.

2. Gere primeiro um inventário da estrutura atual.

3. Identifique:
   - funcionalidades completas;
   - funcionalidades incompletas;
   - mocks;
   - placeholders;
   - dados hardcoded;
   - TODOs;
   - funções sem uso;
   - arquivos duplicados;
   - código morto;
   - dependências instaladas mas não utilizadas;
   - dependências necessárias mas ausentes;
   - rotas sem implementação;
   - componentes sem ligação real;
   - inconsistências entre documentação e código;
   - problemas de segurança;
   - falhas de configuração;
   - integrações apenas aparentes.

4. Não faça uma reorganização ampla por preferência pessoal.

5. Reorganize apenas quando:
   - existir duplicação relevante;
   - uma responsabilidade estiver no módulo errado;
   - houver código morto;
   - houver acoplamento que bloqueie as integrações;
   - a estrutura atual impedir testes ou manutenção;
   - a documentação estiver incompatível com o projeto real.

6. Preserve:
   - funcionalidades válidas;
   - identidade visual;
   - estrutura modular;
   - histórico de migrações;
   - contratos já utilizados pelo aplicativo e pelo admin.

7. Não declare que algo funciona sem executar uma validação real.

---

# 2. Relatórios obrigatórios

Crie ou atualize os seguintes arquivos:

```text
docs/AUDIT_REPORT.md
docs/MANUAL_ACTIONS_REQUIRED.md
docs/INTEGRATION_STATUS.md
docs/GOOGLE_MAPS_SETUP.md
docs/MISSION_PLANNER_SETUP.md
docs/LOCAL_NETWORK_SETUP.md
docs/BUILD_AND_RUN.md
```

## 2.1 `docs/AUDIT_REPORT.md`

O relatório deve conter:

- resumo executivo;
- estado geral do projeto;
- estrutura encontrada;
- módulos analisados;
- erros corrigidos;
- problemas ainda existentes;
- pontas soltas;
- funções inúteis encontradas;
- arquivos removidos;
- arquivos reorganizados;
- dependências removidas;
- dependências adicionadas;
- problemas de tipagem;
- problemas de banco;
- problemas de API;
- problemas de autenticação;
- problemas do Flutter;
- problemas da aplicação web;
- problemas do painel administrativo;
- problemas do gateway;
- problemas da conexão MAVLink;
- problemas de configuração;
- problemas de segurança;
- testes executados;
- testes que falharam;
- testes que não puderam ser executados;
- riscos;
- prioridade das próximas ações.

Classifique cada item:

```text
CRÍTICO
ALTO
MÉDIO
BAIXO
INFORMATIVO
```

Para cada problema, informe:

```text
Problema
Impacto
Origem
Correção aplicada
Arquivos alterados
Validação executada
Situação atual
Ação manual necessária, se houver
```

## 2.2 `docs/MANUAL_ACTIONS_REQUIRED.md`

Inclua somente tarefas que exigem ação humana ou acesso externo.

Exemplos:

- criar projeto no Google Cloud;
- ativar faturamento;
- habilitar APIs;
- criar chave;
- restringir chave;
- informar package name;
- informar SHA-1/SHA-256;
- baixar driver;
- instalar dependência do sistema;
- instalar Mission Planner;
- selecionar porta COM;
- configurar rádio de telemetria;
- configurar endpoint UDP;
- liberar porta no firewall;
- definir IP local;
- aceitar licença;
- conectar Pixhawk;
- realizar calibração;
- configurar parâmetros que não podem ser inferidos;
- executar testes físicos.

Para cada ação manual, informe exatamente:

```text
O que fazer
Por que é necessário
Onde fazer
Dados necessários
Como validar
O que enviar ao Codex depois
```

Não diga apenas “configure a API”. Dê instruções objetivas.

## 2.3 `docs/INTEGRATION_STATUS.md`

Crie uma matriz com:

| Integração | Implementada | Configurada | Testada | Resultado | Dependência manual |
|---|---:|---:|---:|---|---|
| Flutter → Backend | | | | | |
| Flutter Web → Backend | | | | | |
| Admin → Backend | | | | | |
| Backend → PostgreSQL | | | | | |
| Gateway → Backend | | | | | |
| Gateway → SITL | | | | | |
| Gateway → Pixhawk | | | | | |
| Mission Planner → Pixhawk | | | | | |
| Mission Planner → Gateway | | | | | |
| Google Maps Android | | | | | |
| Google Maps Web | | | | | |
| Places/Geocoding | | | | | |
| WebSocket cliente | | | | | |
| WebSocket admin | | | | | |
| Build APK | | | | | |
| Build Flutter Web | | | | | |
| Build Admin | | | | | |

Nunca marque como testada uma integração que foi apenas programada.

---

# 3. Google Maps — implementação obrigatória

Tente implementar o Google Maps no aplicativo Android e na versão web do aplicativo.

Não use apenas uma variável chamada genericamente de “Google API”. Identifique quais serviços são realmente necessários.

Verifique a necessidade de:

```text
Maps SDK for Android
Maps JavaScript API
Places API / autocomplete
Geocoding API
Reverse Geocoding
```

Use apenas os serviços realmente utilizados pelo código.

## 3.1 Se a chave ainda não existir

Prepare integralmente o código e a configuração.

Depois:

1. informe que a chave está ausente;
2. informe quais APIs precisam ser habilitadas;
3. informe onde a chave será colocada;
4. informe quais restrições devem ser configuradas;
5. informe quais dados do projeto são necessários;
6. informe se precisa que o usuário forneça:
   - chave Android;
   - chave web;
   - chave de servidor;
   - package name;
   - SHA-1;
   - SHA-256;
   - domínio ou origem autorizada.

Não invente uma chave.

Não coloque chave real em arquivos versionados.

## 3.2 Configuração das chaves

Separe corretamente:

```text
GOOGLE_MAPS_ANDROID_API_KEY
GOOGLE_MAPS_WEB_API_KEY
GOOGLE_MAPS_SERVER_API_KEY
```

A chave Android deve ser configurada pelo mecanismo próprio do Android.

A chave web deve respeitar origens autorizadas.

A chave de servidor não deve ser enviada ao Flutter ou React.

Crie `.env.example` e documentação sem valores reais.

## 3.3 Alternativas quando Google Maps não puder ser usado

Não troque automaticamente de provedor sem informar.

Caso a implementação do Google Maps seja inviável por:

- ausência de faturamento;
- indisponibilidade da chave;
- restrição do SDK;
- incompatibilidade da biblioteca;
- limitação da plataforma;
- custo;
- bloqueio regional;
- problema de licença;

gere uma comparação objetiva entre:

```text
Mapbox
HERE Maps
MapLibre
OpenStreetMap com provedor de tiles adequado
```

Informe para cada alternativa:

- suporte Android;
- suporte web;
- pesquisa de endereço;
- geocodificação;
- visão de satélite;
- necessidade de token;
- custo ou plano gratuito;
- dificuldade de integração;
- alteração necessária no projeto.

Não afirme que OpenStreetMap puro fornece visão de satélite. Caso use MapLibre/OpenStreetMap, identifique um provedor de tiles compatível e suas condições.

Peça ao usuário a credencial necessária quando a alternativa exigir token.

---

# 4. Mapa realista e navegação mundial

O mapa do cliente deve permitir exploração ampla e não deve ficar preso à localização atual, à cidade ou à área de atendimento.

## 4.1 Visualização

Quando a API estiver configurada:

- usar visão de satélite ou híbrida como padrão para ajuste do ponto;
- permitir nomes de ruas e referências quando o modo híbrido for mais útil;
- permitir zoom;
- permitir rotação quando suportada;
- permitir inclinação quando suportada;
- manter boa leitura dos controles;
- exibir construções, terrenos e áreas abertas com a melhor qualidade disponível.

## 4.2 Sem limitação de navegação

Remova:

- `cameraTargetBounds` restritivo;
- bounding box fixo;
- bloqueio por cidade;
- bloqueio por raio na interface;
- reposicionamento forçado para a localização atual;
- zoom mínimo excessivo;
- qualquer código que impeça o cliente de navegar pelo mundo.

O usuário deve conseguir:

- mover o mapa para qualquer país;
- visualizar ruas distantes;
- escolher terrenos sem endereço conhecido;
- selecionar áreas rurais;
- selecionar pontos por coordenadas;
- pesquisar endereço distante;
- ignorar a pesquisa e escolher manualmente.

A área de atendimento não deve limitar a exploração do mapa.

A validação de cobertura deve ocorrer apenas:

1. ao validar o ponto;
2. ao enviar o pedido;
3. no painel administrativo.

Se o ponto estiver fora da cobertura, mostre aviso e permita escolher outro ponto.

## 4.3 Fluxo de seleção

Mantenha o fluxo em duas etapas:

```text
Localização atual aproximada ou pesquisa
        ↓
Mapa centraliza na região
        ↓
Cliente entra no ajuste fino
        ↓
Visão satélite/híbrida
        ↓
Cliente move o mapa ou marcador
        ↓
Coordenadas finais são atualizadas
        ↓
Cliente confirma o ponto
```

Permita também:

```text
Abrir mapa
        ↓
Ignorar localização e endereço
        ↓
Navegar livremente
        ↓
Selecionar um ponto sem endereço conhecido
```

O endereço textual é opcional.

Latitude e longitude finais são obrigatórias.

## 4.4 Comportamento do marcador

Escolha uma única interação clara e consistente:

### Opção preferencial

- marcador/seta fixo no centro;
- usuário movimenta o mapa por baixo;
- coordenadas finais são o centro da câmera;
- comportamento semelhante a aplicativos de transporte.

Ou, caso a implementação atual já utilize marcador arrastável de forma correta:

- mantenha marcador arrastável;
- não combine duas interações confusas;
- documente a escolha.

Ao finalizar o movimento:

- atualizar coordenadas;
- executar geocodificação reversa apenas como referência;
- não impedir confirmação se não houver endereço;
- mostrar “Local sem endereço identificado” quando necessário.

---

# 5. Remoção dos avisos de conteúdo fictício

Remova das telas do aplicativo:

- banners genéricos dizendo que o aplicativo inteiro é fictício;
- mensagens repetidas de protótipo;
- avisos que prejudiquem a demonstração;
- placeholders visuais desnecessários;
- textos técnicos voltados ao desenvolvedor.

Porém, preserve a veracidade:

- não diga que um pagamento real foi processado;
- não colete dados reais de cartão;
- não exiba “pagamento aprovado pelo banco”;
- não simule transação financeira como real;
- não invente estoque ou restaurante real.

Substitua textos genéricos como:

```text
Este aplicativo é fictício
Este é apenas um protótipo
Dados simulados
```

por textos naturais da experiência.

Na área de pagamento, utilize uma implementação segura:

- seleção de método;
- confirmação do método;
- nenhum número real de cartão persistido;
- nenhuma comunicação bancária;
- status interno de pagamento de demonstração.

Não exiba um aviso chamativo ao usuário, mas não apresente alegações falsas de processamento financeiro real.

---

# 6. Criar versão web do aplicativo do cliente

Crie uma versão web funcional do aplicativo do cliente para acompanhar alterações em tempo real durante o desenvolvimento.

A preferência é utilizar a mesma base Flutter:

```text
Flutter Android
Flutter Web
```

Evite criar uma segunda aplicação web do cliente em React se o Flutter Web puder atender.

## 6.1 Requisitos da versão web

- funcionar em `localhost`;
- utilizar o mesmo backend;
- utilizar os mesmos modelos;
- utilizar os mesmos serviços;
- utilizar o mesmo design system;
- reutilizar o máximo de componentes possível;
- ter layout responsivo;
- adaptar navegação para desktop sem duplicar regras;
- permitir hot reload;
- permitir mapa;
- permitir login;
- permitir pedido;
- permitir acompanhamento;
- não interferir no painel administrativo React.

## 6.2 Compatibilidade entre plataformas

Crie abstrações para diferenças entre:

```text
Android
Web
```

Exemplos:

- armazenamento de token;
- configuração da URL da API;
- localização;
- Google Maps;
- permissões;
- WebSocket;
- download de arquivos.

Não espalhe verificações de plataforma por todas as telas.

Centralize em adaptadores ou serviços.

## 6.3 Execução em localhost

Documente comandos como:

```powershell
flutter run -d chrome
flutter build web
```

Confirme os comandos corretos para o ambiente atual.

Configure CORS do backend para:

```text
http://localhost:<porta>
http://127.0.0.1:<porta>
```

Use portas realmente configuradas no projeto.

## 6.4 Erros de compatibilidade

Caso alguma biblioteca Flutter não suporte web:

1. identifique a biblioteca;
2. informe o erro;
3. procure alternativa compatível;
4. implemente adapter por plataforma;
5. documente a decisão;
6. não deixe o projeto inteiro bloqueado.

---

# 7. APK atualizado e conectado corretamente

O APK deve continuar sendo mantido e atualizado, mesmo que a demonstração use Flutter Web.

Execute e valide:

```powershell
flutter analyze
flutter test
flutter build apk --debug
```

Quando possível:

```powershell
flutter build apk --release
```

Não afirme que o APK funciona em dispositivo físico sem instalar e testar.

## 7.1 Arquitetura correta da conexão

O APK não deve se conectar diretamente ao banco nem ao painel administrativo.

A arquitetura correta é:

```text
APK Flutter
      ↓ HTTP/HTTPS + WebSocket
Backend FastAPI
      ↓
PostgreSQL/PostGIS

Painel Admin
      ↓ HTTP/HTTPS + WebSocket
Mesmo Backend FastAPI
```

O backend é a fonte de verdade.

O admin e o APK compartilham:

- pedidos;
- status;
- missões;
- telemetria;
- eventos;

por meio da API.

## 7.2 Configuração da URL por ambiente

Crie configurações separadas:

```text
local_web
android_emulator
android_physical_device
demo_network
hosted
```

Exemplos que devem ser explicados, não hardcoded indiscriminadamente:

```text
Web local: http://localhost:8000
Emulador Android: http://10.0.2.2:8000
Celular físico: http://IP_DO_COMPUTADOR_NA_REDE:8000
```

O celular físico não pode utilizar `localhost` para acessar o computador.

Crie:

- configuração por `--dart-define`;
- arquivo de exemplo;
- documentação;
- validação da URL;
- tela ou log de diagnóstico em modo de desenvolvimento.

## 7.3 Hospedagem

Não assuma que hospedagem paga é obrigatória.

Primeiro implemente e documente funcionamento em:

```text
localhost
rede local
```

Caso o APK precise funcionar fora da mesma rede, explique opções:

- hospedagem do backend;
- túnel de desenvolvimento;
- VPN;
- servidor próprio;
- VPS;
- serviços cloud.

Não contrate nem configure serviço pago sem autorização.

Caso uma função dependa de hospedagem externa, mantenha a aplicação web funcional em localhost e registre a limitação.

---

# 8. Revisão e reorganização do projeto

Faça uma revisão completa, mas refatore somente quando necessário.

## 8.1 Procurar

- funções duplicadas;
- componentes duplicados;
- classes não utilizadas;
- arquivos abandonados;
- código comentado;
- mocks esquecidos;
- endpoints fictícios;
- dados hardcoded;
- estados impossíveis;
- rotas que não chegam ao backend;
- serviços que não são usados;
- DTOs inconsistentes;
- enums diferentes entre aplicações;
- dependências circulares;
- imports quebrados;
- configurações duplicadas;
- valores de URL espalhados;
- cores e estilos duplicados;
- código específico de plataforma misturado à interface;
- código de MAVLink dentro do backend;
- acesso direto ao banco fora do backend;
- telemetria inventada.

## 8.2 Remover somente quando seguro

Antes de remover algo:

1. procure referências;
2. verifique testes;
3. verifique documentação;
4. confirme que não é usado por build;
5. registre a remoção;
6. execute regressão.

Não apague por parecer inútil.

## 8.3 Reorganização

Caso reorganize:

- mantenha mudanças pequenas;
- preserve APIs públicas;
- atualize imports;
- atualize testes;
- atualize documentação;
- explique o motivo no relatório;
- não reescreva o projeto inteiro.

---

# 9. Painel administrativo sem dados fictícios do drone

Remova do painel administrativo qualquer telemetria operacional hardcoded, aleatória ou simulada quando o sistema estiver em modo real.

Não mostrar como se fossem reais:

- bateria fictícia;
- satélites fictícios;
- GPS fictício;
- EKF fictício;
- modo de voo fictício;
- drone conectado fictício;
- coordenada fictícia;
- velocidade fictícia;
- missão em execução fictícia;
- heartbeat fictício.

## 9.1 Estados corretos

Quando não houver conexão:

```text
Status: Desconectado
Última comunicação: nunca ou timestamp real
Bateria: --
GPS: --
Satélites: --
EKF: --
Modo: --
Armado: --
Posição: --
```

Quando houver conexão parcial:

- mostre apenas valores recebidos;
- campos ausentes ficam `--`;
- não complete com valor padrão;
- exiba alerta curto e claro.

Exemplo:

```text
Conexão estabelecida, mas o nível de bateria ainda não foi recebido.
```

Quando um valor estiver desatualizado:

```text
Dado desatualizado
Última atualização: ...
```

## 9.2 Fonte dos dados

Cada valor exibido deve vir de:

```text
Pixhawk/ArduPilot → MAVLink → drone_gateway → backend → WebSocket/API → admin
```

O admin não deve gerar telemetria.

Adicione metadados:

```text
received_at
source
is_stale
```

## 9.3 Modo simulação

Se o projeto mantiver SITL ou fake para testes:

- o modo deve estar claramente identificado apenas no painel técnico;
- nunca misturar simulação com modo real;
- impedir dados fake quando `MAVLINK_MODE=real`;
- adicionar badge discreto:
  - `SIMULAÇÃO`;
  - `SITL`;
  - `HARDWARE REAL`.

Não mostrar dados fake em modo real para preencher espaço.

---

# 10. Alertas rápidos de conexão

Implemente alertas rápidos e não invasivos no admin.

Alertas mínimos:

- drone desconectado;
- heartbeat perdido;
- GPS não disponível;
- poucos satélites;
- EKF não saudável;
- bateria não recebida;
- bateria abaixo do limite;
- modo inesperado;
- veículo armado sem missão autorizada;
- missão não carregada;
- upload falhou;
- telemetria desatualizada;
- backend desconectado;
- gateway desconectado;
- porta serial indisponível;
- Mission Planner ocupando a porta;
- autorização expirada.

O alerta deve informar:

```text
O que aconteceu
Impacto
Última atualização
Ação recomendada
```

Não crie alertas intermináveis a cada pacote de telemetria.

Implemente deduplicação e cooldown.

---

# 11. Mission Planner, Pixhawk e MAVLink

Prepare tudo o que puder no código para a conexão real.

Crie ou revise:

```text
docs/MISSION_PLANNER_SETUP.md
docs/DRONE_PROTOCOL.md
docs/HARDWARE.md
docs/PREFLIGHT_CHECKLIST.md
```

## 11.1 Identificar a topologia de conexão

O Codex deve inspecionar o projeto e documentar qual das opções será utilizada.

### Opção A — Gateway conecta diretamente à Pixhawk

```text
Pixhawk/radio de telemetria
        ↓ porta serial ou UDP
drone_gateway
        ↓
backend
        ↓
admin e aplicativo
```

Mission Planner pode monitorar por encaminhamento MAVLink.

### Opção B — Mission Planner conecta à Pixhawk e encaminha MAVLink

```text
Pixhawk/radio
        ↓
Mission Planner
        ↓ saída UDP/TCP
drone_gateway
        ↓
backend
```

### Opção C — MAVProxy ou roteador MAVLink distribui a conexão

```text
Pixhawk/radio
        ↓
MAVProxy/MAVLink Router
        ├── Mission Planner
        └── drone_gateway
```

Não assuma que dois programas podem abrir a mesma porta COM ao mesmo tempo.

Detecte o ambiente e recomende a topologia mais adequada.

## 11.2 O que deve ser implementado

No `drone_gateway`:

- configuração serial/UDP/TCP;
- lista ou detecção assistida de portas;
- conexão;
- timeout;
- heartbeat;
- identificação de sistema e componente;
- leitura de versão do autopiloto quando disponível;
- estado do veículo;
- GPS;
- satélites;
- EKF;
- bateria;
- modo de voo;
- armamento;
- posição;
- home position;
- missão atual;
- upload de missão;
- download e verificação da missão;
- confirmação do número de itens;
- comandos autorizados;
- RTL;
- abortamento controlado;
- eventos;
- reconexão;
- logs;
- status para o backend;
- proteção contra execução duplicada.

Não armar automaticamente ao iniciar o gateway.

Não iniciar missão apenas porque conectou.

## 11.3 Missão e Mission Planner

Prepare:

- geração de arquivo `.waypoints` compatível;
- visualização dos waypoints no admin;
- download do arquivo;
- hash e versão da missão;
- registro da revisão;
- upload MAVLink;
- comparação entre missão enviada e confirmada;
- indicação no admin:
  - gerada;
  - exportada;
  - revisada;
  - autorizada;
  - enviada;
  - confirmada;
  - executando.

Não automatize cliques na interface do Mission Planner.

Prefira integração por MAVLink e arquivos suportados.

## 11.4 Dados necessários do usuário

Caso não seja possível concluir a conexão sem informações externas, informe exatamente o que precisa.

Exemplos:

```text
Modelo exato da Pixhawk
Firmware e versão do ArduPilot
Porta COM
Baud rate
Tipo de rádio de telemetria
Conexão USB ou rádio
Sistema operacional
Modo de voo utilizado
Frame configurado
Endpoint UDP do Mission Planner
Parâmetros de serial relevantes
Mensagem de heartbeat
Logs de conexão
```

Não invente esses valores.

## 11.5 Guia de ligação rápida

Em `docs/MISSION_PLANNER_SETUP.md`, crie um passo a passo rápido para colocar o sistema em funcionamento:

1. conectar Pixhawk;
2. abrir Mission Planner;
3. identificar COM e baud;
4. verificar firmware;
5. conectar;
6. confirmar heartbeat;
7. verificar GPS;
8. verificar EKF;
9. verificar bateria;
10. verificar home;
11. configurar encaminhamento MAVLink, se necessário;
12. configurar o `.env` do gateway;
13. iniciar backend;
14. iniciar gateway;
15. validar status no admin;
16. carregar missão;
17. revisar;
18. autorizar;
19. executar teste sem hélices;
20. executar teste controlado.

Não dê como concluído qualquer passo físico sem execução real.

---

# 12. Banco, backend, aplicativo e admin

Revise o fluxo completo:

```text
Aplicativo/Flutter Web
        ↓
Backend
        ↓
Banco

Admin
        ↓
Mesmo backend
        ↓
Mesmo banco

Gateway
        ↓
Backend
        ↓
Telemetria e eventos
```

Verifique:

- autenticação;
- roles;
- CORS;
- WebSocket;
- serialização;
- enums;
- estados;
- IDs;
- timestamps;
- migrações;
- seeds;
- atualização em tempo real;
- reconexão;
- erros;
- loading;
- empty states;
- stale data;
- concorrência;
- autorização administrativa;
- autorização de voo;
- auditoria.

Corrija pontas soltas.

---

# 13. Testes e validações

Execute o máximo possível no ambiente disponível.

## 13.1 Backend

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

## 13.2 Flutter Android e Web

```powershell
cd mobile
flutter pub get
dart format --set-exit-if-changed .
flutter analyze
flutter test
flutter run -d chrome
flutter build web
flutter build apk --debug
```

Execute `flutter build apk --release` se o ambiente estiver corretamente configurado.

## 13.3 Admin

```powershell
cd admin_web
npm install
npm run lint
npm run test
npm run build
```

## 13.4 Gateway

```powershell
cd drone_gateway
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
ruff check .
ruff format --check .
pytest
```

## 13.5 Docker

```powershell
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=200
```

## 13.6 Fluxos mínimos

Valide:

### Fluxo cliente

```text
Login
Produtos
Carrinho
Mapa
Seleção do ponto
Pedido
Status
```

### Fluxo admin

```text
Login
Pedido pendente
Aprovação
Missão
Revisão
Autorização
Status do drone
```

### Fluxo de integração

```text
Cliente → Backend → Banco → Admin
Gateway → Backend → Admin
Admin → Backend → Cliente
```

### Fluxo de mapa

```text
Permissão
Localização aproximada
Pesquisa
Navegação mundial
Satélite/híbrido
Ponto sem endereço
Confirmação
Persistência
```

### Fluxo MAVLink

Quando houver ambiente:

```text
Conexão
Heartbeat
Telemetria
Missão
Upload
Confirmação
RTL
```

---

# 14. Conduta diante de bloqueios

Quando faltar:

- chave;
- conta;
- API;
- driver;
- programa;
- firmware;
- dispositivo;
- porta;
- conexão;
- credencial;
- domínio;
- hospedagem;
- parâmetro;

não interrompa todo o trabalho.

Faça:

1. toda implementação independente do bloqueio;
2. adapter ou configuração;
3. tratamento de ausência;
4. documentação;
5. teste com fake ou SITL somente no ambiente de teste;
6. relatório do que falta;
7. instrução exata ao usuário.

Não deixe dados fake aparecendo como reais.

---

# 15. Resultado final obrigatório

Ao concluir, responda com:

## 15.1 Resumo

- o que foi analisado;
- o que foi corrigido;
- o que foi reorganizado;
- o que foi removido;
- o que foi implementado.

## 15.2 Arquivos alterados

Liste por módulo.

## 15.3 Google Maps

Informe:

- APIs usadas;
- bibliotecas usadas;
- estado Android;
- estado web;
- credenciais ausentes;
- ações manuais;
- alternativa recomendada, caso necessário.

## 15.4 Flutter Web

Informe:

- como executar;
- URL;
- limitações;
- recursos funcionais.

## 15.5 APK

Informe:

- build executado;
- caminho do APK;
- resultado;
- como configurar backend para celular físico.

## 15.6 Admin

Informe:

- dados reais implementados;
- dados fictícios removidos;
- alertas;
- comportamento desconectado.

## 15.7 Banco e backend

Informe:

- migrações;
- conexão;
- APIs;
- WebSockets;
- CORS;
- testes.

## 15.8 Mission Planner e drone

Informe separadamente:

```text
Implementado no código
Testado com fake
Testado com SITL
Testado com Mission Planner
Testado com Pixhawk
Testado com drone real
```

Não misture esses níveis.

## 15.9 Ações manuais

Liste em ordem de prioridade.

## 15.10 Erros

Liste:

- erros corrigidos;
- erros restantes;
- erros externos;
- dependências ausentes;
- credenciais ausentes.

## 15.11 Próximo passo

Forneça apenas o próximo passo mais importante para aproximar o drone do funcionamento real.

---

# 16. Restrições finais

- Não recriar o projeto do zero.
- Não criar telemetria falsa em modo real.
- Não esconder erros.
- Não afirmar que Google Maps está funcionando sem chave e teste.
- Não afirmar que Mission Planner está conectado sem heartbeat real.
- Não afirmar que a Pixhawk está conectada sem dados reais.
- Não conectar APK diretamente ao banco.
- Não usar `localhost` incorretamente em celular físico.
- Não limitar a navegação mundial do mapa.
- Não exigir endereço textual para um ponto geográfico válido.
- Não coletar dados financeiros reais.
- Não colocar chaves no Git.
- Não automatizar cliques no Mission Planner.
- Não armar o drone ao iniciar o sistema.
- Não desativar verificações de segurança.
- Não reorganizar sem necessidade.
- Não remover código sem verificar uso.
- Não atualizar golden tests para esconder regressões.
- Não deixar o admin mostrar valores inventados.
- Não confundir “programado” com “testado”.
