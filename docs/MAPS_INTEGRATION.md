# Integração de mapas

## Provedor e abstrações

Google Maps é o provedor principal. `google_maps_flutter` fica atrás de `SatelliteMapView`/`MapProvider`; o `geolocator` fica atrás de `LocationService`; Places e geocodificação passam pelo adapter do backend. Isso permite doubles em testes e um fallback de desenvolvimento sem contaminar as regras da feature com SDKs.

O mapa de ajuste abre como `satellite`; `hybrid` é opcional para nomes. Mapa terrestre não é confirmação final.

## Configuração Android

1. Crie uma chave restrita ao pacote Android e fingerprints de assinatura usados.
2. Habilite somente Maps SDK for Android e APIs de Places/Geocoding necessárias.
3. Forneça a chave pelo mecanismo local/manifest placeholder documentado no `mobile/README.md`.
4. Não coloque chave em Dart, commit, screenshot ou log.
5. Chave de servidor, se usada por proxy FastAPI, é diferente e restrita por serviço/IP.

`.env.example` contém apenas nomes vazios. O backend protege quotas, normaliza erros e não devolve a chave.

## Fluxo técnico

- localização atual: permissão just-in-time, precisão aproximada e timeout;
- Places: debounce, cancelamento de busca anterior, viés regional BR sem impedir destino distante;
- geocode: somente centralização aproximada;
- câmera: controller abstrato, zoom limitado à capacidade do SDK;
- marcador: arrastável ou crosshair controlado, atualização em memória;
- reverse geocode: rótulo auxiliar após parada;
- submit: backend recalcula cobertura/distância e persiste coordenada final.

## Fallback de desenvolvimento

Sem chaves ou configuração habilitada, uma superfície local identificada como **“Mapa demonstrativo — sem Google Maps”** permite testar estados e deslocamento determinístico. Ela não mostra cartografia, não chama isso de satélite real e não habilita uma demonstração operacional. O cliente bloqueia o checkout integrado enquanto esse fallback estiver ativo.

## Limites e indisponibilidade

Debounce e cache curto evitam consumo desnecessário. `429`, quota, timeout, zero results e erro de rede possuem mensagens distintas e retry. Logs registram código/correlação, não consulta completa e coordenadas quando dispensáveis. Termos, atribuição e política do Google devem permanecer visíveis conforme SDK.

## Backend

O proxy de busca é opcional e protege a chave de servidor. Independentemente do provedor, o backend valida lat/lon, flags de etapa manual, distância, cobertura e propriedade. Uma resposta do Google não é prova de área segura nem autorização aeronáutica.

## Testes

- adapters falsos para permissão, Places/geocode e movimento;
- teste do tipo `satellite` na configuração real;
- instrumentado Android para manifest/chave em ambiente próprio;
- contrato do proxy com respostas gravadas, sem internet em teste rápido;
- verificação manual de atribuição, zoom, arrasto, precisão e endereço distante.
