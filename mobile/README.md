# Aplicativo Android — Devcore Entregas

Aplicativo Flutter do cliente para o protótipo acadêmico de entregas por drone. Ele cobre cadastro/login, catálogo demonstrativo, detalhe do produto, carrinho, escolha do ponto em duas etapas, pagamento simulado, envio e acompanhamento do pedido.

O aplicativo **não** aprova pedidos, autoriza voos, envia MAVLink, define altitude ou controla o drone. Essas responsabilidades pertencem ao backend, ao painel administrativo e ao gateway.

## O que está funcional

- fluxo vertical completo em modo de demonstração local;
- integração REST configurável com autenticação, produtos, pontos e pedidos;
- estados de carregamento, vazio e erro do catálogo;
- busca de região aproximada e escolha manual do ponto final;
- mapa Google em visão satélite, marcador móvel e geocodificação via backend quando configurado;
- localização aproximada do aparelho via `geolocator`, com tratamento de permissão negada/serviço indisponível;
- fallback cartográfico local identificado e restrito ao modo de demonstração;
- confirmação explícita de área aberta e coordenadas com seis casas decimais;
- seleção de pagamento apenas nominal, sem qualquer campo bancário;
- acompanhamento dos estados do pedido;
- catálogo visual dos tokens e componentes em **Conta → Catálogo do design system**.
- logotipo original preservado pixel a pixel a partir da referência fornecida; somente a região da marca é recortada em tempo de renderização.

## Modos de execução

O padrão é seguro e funciona sem backend, internet, GPS ou chave de mapa:

```powershell
cd mobile
..\flutter\bin\flutter.bat run
```

Para usar o backend no emulador Android:

```powershell
..\flutter\bin\flutter.bat run `
  --dart-define=DEMO_MODE=false `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 `
  --dart-define=MAP_PROVIDER=google_maps `
  --dart-define=GOOGLE_MAPS_CONFIGURED=true
```

Em um aparelho físico, troque `10.0.2.2` pelo endereço alcançável da máquina que executa a API. O token de sessão fica somente em memória; não há persistência insegura em texto puro.

## Mapas

`MapProvider`, `GoogleMapsBridge` e `LocationService` isolam SDK, busca, geocodificação e localização dos widgets. O mapa usa `google_maps_flutter`; busca, geocodificação e geocodificação reversa passam pelas rotas `/api/v1/maps/*` do backend para que a chave web não seja exposta no aplicativo. Sem configuração completa, o app usa `DevelopmentMapProvider` e exibe **FALLBACK DEV** sobre uma prévia desenhada localmente. Essa prévia não é Google Maps e não representa imagem geográfica real. Em `DEMO_MODE=false`, esse fallback bloqueia o envio do pedido.

Para preparar a configuração do Google Maps, use:

```powershell
$env:GOOGLE_MAPS_ANDROID_API_KEY="chave-restrita-local"
..\flutter\bin\flutter.bat run `
  --dart-define=DEMO_MODE=false `
  --dart-define=API_BASE_URL=http://10.0.2.2:8000 `
  --dart-define=MAP_PROVIDER=google_maps `
  --dart-define=GOOGLE_MAPS_CONFIGURED=true
```

A chave é lida pelo Gradle e injetada no manifest; nunca deve ser gravada no repositório. O define `GOOGLE_MAPS_CONFIGURED=true` só deve ser usado quando a chave Android e as credenciais de mapas do backend estiverem válidas. Restrinja a chave no Google Cloud por aplicativo Android, package name e SHA-1.

O fluxo de localização sempre mantém estas regras:

1. endereço e localização do dispositivo apenas centralizam uma região aproximada;
2. a etapa final usa visualização satélite;
3. o cliente deve mover o marcador manualmente;
4. latitude e longitude finais só são registradas na confirmação;
5. a confirmação de área aberta não substitui validação técnica ou aprovação humana.

## Pagamento

PIX e crédito são rótulos simulados enviados ao backend. O app não apresenta nem transmite número de cartão, validade, CVV, titular, chave PIX ou qualquer credencial financeira. Nenhum dinheiro é processado.

## Estrutura

```text
lib/
├── app/                 # bootstrap, escopo e estado único com ChangeNotifier
├── core/
│   ├── config/          # dart-defines
│   ├── location/        # abstração da localização do dispositivo
│   ├── maps/            # abstração e fallback de mapas
│   ├── models/          # produto, ponto, carrinho e estados
│   ├── network/         # cliente REST Android
│   └── repositories/    # implementações demo e API
├── design_system/
│   ├── components/      # somente componentes usados nas telas
│   ├── design_catalog/  # catálogo de desenvolvimento
│   ├── theme/
│   └── tokens/
└── features/            # auth, produtos, carrinho, ponto, pagamento e tracking
```

O projeto usa os plugins `google_maps_flutter` e `geolocator`. A estratégia única de estado é `ChangeNotifier` + `InheritedNotifier`.

## Qualidade

```powershell
cd mobile
..\flutter\bin\flutter.bat pub get
..\flutter\bin\dart.bat format --set-exit-if-changed .
..\flutter\bin\flutter.bat analyze
..\flutter\bin\flutter.bat test
..\flutter\bin\flutter.bat build apk --debug
```

Os testes cobrem cálculo do carrinho, confirmação segura do ponto, fallback do provedor e ausência de campos bancários.

## Limites atuais

- Maps/Places e GPS reais dependem de chaves restritas, permissões Android e backend configurado; não foram exercitados em um aparelho neste ambiente;
- build release exige keystore privado externo e URL HTTPS; a chave debug não é reutilizada para distribuição;
- acompanhamento real prioriza WebSocket autenticado e retoma por polling REST com backoff quando a conexão cai; o modo demo progride localmente e é identificado na interface;
- nenhum teste deste módulo comprova integração com Pixhawk, SITL, Mission Planner ou voo real;
- Android é a única plataforma gerada e suportada neste MVP.
