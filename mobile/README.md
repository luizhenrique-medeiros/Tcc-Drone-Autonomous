# Aplicativo Flutter Android e Web — Devcore Entregas

Cliente do sistema de entregas por drone. O mesmo código Flutter atende Android e navegador e cobre autenticação, catálogo, carrinho, escolha do ponto, forma de pagamento nominal, envio do pedido e acompanhamento.

O cliente não aprova pedidos, autoriza voo, envia MAVLink, define altitude nem controla a aeronave. Essas responsabilidades permanecem no backend, no admin e no gateway.

## Recursos implementados

- modo local demonstrativo e modo integrado por REST/WebSocket;
- sessão integrada restaurada por armazenamento seguro, sem token em texto puro;
- layout responsivo para celular e desktop, com navegação lateral em telas amplas;
- seleção do ponto em qualquer região do mundo, sem limite por cidade ou país;
- abertura direta do mapa sem endereço e sem exigir GPS;
- mapa híbrido com pino fixo no centro; as coordenadas mudam ao mover a câmera;
- busca e geocodificação reversa opcionais pelo backend;
- fallback cartográfico local claramente identificado e aceito somente em demonstração;
- confirmação manual de área aberta antes do checkout;
- PIX/crédito apenas como opção nominal, sem cartão, CVV, titular ou chave PIX;
- desconto de 20% calculado com arredondamento monetário igual ao backend.

## Execução recomendada

Na raiz do repositório, o script valida perfil, URL e chaves antes de iniciar o Flutter.

Demo local:

```powershell
.\scripts\start_mobile.ps1 -Profile demo
```

Web integrado em Chrome:

```powershell
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile local_web `
  -Device chrome `
  -WebPort 5174
```

Android Emulator:

```powershell
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -ApiBaseUrl http://10.0.2.2:8000
```

Celular físico na rede local:

```powershell
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_physical_device `
  -ApiBaseUrl http://IP_DO_PC:8000 `
  -AllowInsecureLanHttp
```

`localhost` no celular aponta para o próprio celular. Use o IPv4 alcançável do computador e siga [LOCAL_NETWORK_SETUP.md](../docs/LOCAL_NETWORK_SETUP.md). O perfil `hosted` exige HTTPS.

## MapTiler

São usadas chaves separadas e restritas:

- `MAPTILER_ANDROID_API_KEY`, injetada no build Flutter Android;
- `MAPTILER_WEB_API_KEY`, injetada no build Flutter Web;
- `MAPTILER_SERVER_API_KEY`, usada somente pelo backend em busca e geocodificação;
- `MAPTILER_STYLE_URL`, URL base do `style.json`, sem `?key=`.

O aplicativo usa `maplibre_gl` com o estilo vetorial híbrido no Android e no
Web. O iframe do visualizador MapTiler não é usado, pois não expõe à camada
Flutter os eventos de câmera necessários para confirmar as coordenadas.

Exemplo Web com MapTiler configurado:

```powershell
$env:MAPTILER_WEB_API_KEY='CHAVE_WEB_RESTRITA'
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile local_web `
  -MapTilerConfigured `
  -Device chrome
```

Exemplo Android:

```powershell
$env:MAPTILER_ANDROID_API_KEY='CHAVE_ANDROID_RESTRITA'
.\scripts\start_mobile.ps1 `
  -Integrated `
  -Profile android_emulator `
  -MapTilerConfigured
```

Nenhuma chave fica no `web/index.html`, no manifest versionado ou no código
Dart. A URL completa ou o iframe não devem ser usados como chave. Sem o estilo
MapTiler carregado, o modo integrado bloqueia a confirmação das coordenadas.

Veja [MAPS_INTEGRATION.md](../docs/MAPS_INTEGRATION.md).

## Sessão e rede

O cliente HTTP usa `package:http`, portanto não importa `dart:io` no bundle Web. A sessão integrada é validada em `/api/v1/auth/me` na inicialização; token rejeitado é removido.

`flutter_secure_storage` exige contexto seguro no navegador: HTTPS em hospedagem e `localhost` durante desenvolvimento. HTTP em LAN só é permitido por opção explícita e não deve ser usado em produção.

## Qualidade e builds

```powershell
cd mobile
..\flutter\bin\flutter.bat pub get
..\flutter\bin\dart.bat format --output=none --set-exit-if-changed lib test
..\flutter\bin\flutter.bat analyze
..\flutter\bin\flutter.bat test
..\flutter\bin\flutter.bat build web --release `
  --dart-define=APP_ENVIRONMENT=demo `
  --dart-define=DEMO_MODE=true `
  --dart-define=MAP_PROVIDER=maptiler `
  --dart-define=MAPTILER_CONFIGURED=false
..\flutter\bin\flutter.bat build apk --debug `
  --dart-define=APP_ENVIRONMENT=demo `
  --dart-define=DEMO_MODE=true
```

Artefatos:

- Web: `mobile/build/web`;
- APK debug: `mobile/build/app/outputs/flutter-apk/app-debug.apk`.

O caminho do repositório contém acento. Se o Analysis Server/Gradle falhar por isso, use os scripts da raiz; eles criam uma junção ASCII temporária validada.

## Estrutura

```text
lib/
├── app/                 # bootstrap, rotas, sessão e estado
├── core/
│   ├── config/          # perfis e dart-defines validados
│   ├── location/        # localização aproximada opcional
│   ├── maps/            # MapTiler/MapLibre, API bridge e fallback
│   ├── network/         # HTTP multiplataforma
│   ├── repositories/    # demo e API
│   └── security/        # persistência abstrata da sessão
├── design_system/       # tema, tokens e componentes
└── features/            # auth, produtos, carrinho, ponto, pagamento e tracking
```

## Limites de validação

- o checkout integrado aceita qualquer coordenada mundial válida após a confirmação manual; o raio de missão é uma proteção separada do gateway;
- o build Web e o APK debug podem ser validados sem chave, usando fallback honesto;
- Maps/Places/GPS reais exigem credenciais, billing, rede e aparelho e não são comprovados pelo build;
- APK release exige keystore privado externo;
- nenhuma validação deste módulo comprova SITL, Mission Planner, Pixhawk ou voo físico.
