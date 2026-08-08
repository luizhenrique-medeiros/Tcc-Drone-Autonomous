import '../core/config/app_config.dart';
import '../core/location/location_service.dart';
import '../core/maps/api_map_bridge.dart';
import '../core/maps/map_provider.dart';
import '../core/network/api_client.dart';
import '../core/repositories/auth_repository.dart';
import '../core/repositories/checkout_repository.dart';
import '../core/repositories/product_repository.dart';
import '../core/security/session_token_store.dart';
import 'app_controller.dart';

abstract final class AppBootstrap {
  static AppController createController() {
    if (AppConfig.demoMode) {
      final MapProvider mapProvider = MapProviderFactory.create(
        mapTilerConfigured: false,
      );
      return AppController(
        authRepository: DemoAuthRepository(),
        productRepository: DemoProductRepository(),
        checkoutRepository: const DemoCheckoutRepository(),
        mapProvider: mapProvider,
        locationService: const DevelopmentLocationService(),
        isDemoMode: true,
      );
    }

    final ApiClient client = ApiClient(baseUrl: AppConfig.apiBaseUrl);
    final MapProvider mapProvider = MapProviderFactory.create(
      mapTilerConfigured: AppConfig.mapTilerConfigured,
      onlineMapBridge: ApiMapBridge(client),
    );
    return AppController(
      authRepository: ApiAuthRepository(client, SecureSessionTokenStore()),
      productRepository: ApiProductRepository(client),
      checkoutRepository: ApiCheckoutRepository(client),
      mapProvider: mapProvider,
      locationService: PlatformLocationService(
        const GeolocatorDeviceLocationBridge(),
      ),
      isDemoMode: false,
      mapInitializationMessage: AppConfig.mapTilerConfigured
          ? null
          : 'MapTiler não configurado. Defina as variáveis MAPTILER_* antes '
                'de confirmar coordenadas no modo integrado.',
      disposeResources: client.close,
    );
  }
}
