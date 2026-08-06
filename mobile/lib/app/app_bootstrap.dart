import 'package:flutter/foundation.dart';

import '../core/config/app_config.dart';
import '../core/location/location_service.dart';
import '../core/maps/api_google_maps_bridge.dart';
import '../core/maps/map_provider.dart';
import '../core/network/api_client.dart';
import '../core/repositories/auth_repository.dart';
import '../core/repositories/checkout_repository.dart';
import '../core/repositories/product_repository.dart';
import 'app_controller.dart';

abstract final class AppBootstrap {
  static AppController createController() {
    if (AppConfig.demoMode) {
      final MapProvider mapProvider = MapProviderFactory.create(
        googleMapsConfigured: false,
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

    final Uri apiUri = Uri.parse(AppConfig.apiBaseUrl);
    final bool localDebugApi =
        kDebugMode &&
        (apiUri.host == '10.0.2.2' ||
            apiUri.host == 'localhost' ||
            apiUri.host == '127.0.0.1');
    if (apiUri.scheme != 'https' && !localDebugApi) {
      throw StateError(
        'API_BASE_URL deve usar HTTPS fora do desenvolvimento local.',
      );
    }

    final ApiClient client = ApiClient(baseUrl: AppConfig.apiBaseUrl);
    final MapProvider mapProvider = MapProviderFactory.create(
      googleMapsBridge: ApiGoogleMapsBridge(client),
    );
    return AppController(
      authRepository: ApiAuthRepository(client),
      productRepository: ApiProductRepository(client),
      checkoutRepository: ApiCheckoutRepository(client),
      mapProvider: mapProvider,
      locationService: PlatformLocationService(
        const GeolocatorDeviceLocationBridge(),
      ),
      isDemoMode: false,
    );
  }
}
