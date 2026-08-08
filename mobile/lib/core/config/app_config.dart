import 'package:flutter/foundation.dart';

class AppConfigurationException implements Exception {
  const AppConfigurationException(this.message);

  final String message;

  @override
  String toString() => message;
}

abstract final class AppConfig {
  static const String appVersion = String.fromEnvironment(
    'APP_VERSION',
    defaultValue: '0.1.0+1',
  );

  static const Set<String> supportedEnvironments = <String>{
    'demo',
    'local_web',
    'android_emulator',
    'android_physical_device',
    'demo_network',
    'hosted',
  };

  static const String environment = String.fromEnvironment(
    'APP_ENVIRONMENT',
    defaultValue: 'demo',
  );

  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const bool demoMode = bool.fromEnvironment(
    'DEMO_MODE',
    defaultValue: true,
  );

  static const bool allowInsecureLanHttp = bool.fromEnvironment(
    'ALLOW_INSECURE_LAN_HTTP',
    defaultValue: false,
  );

  static const String mapProvider = String.fromEnvironment(
    'MAP_PROVIDER',
    defaultValue: 'maptiler',
  );

  static const bool mapTilerConfigured = bool.fromEnvironment(
    'MAPTILER_CONFIGURED',
    defaultValue: false,
  );

  static const String mapTilerStyleUrl = String.fromEnvironment(
    'MAPTILER_STYLE_URL',
    defaultValue: 'https://api.maptiler.com/maps/hybrid-v4/style.json',
  );

  static const String mapTilerWebApiKey = String.fromEnvironment(
    'MAPTILER_WEB_API_KEY',
  );

  static const String mapTilerAndroidApiKey = String.fromEnvironment(
    'MAPTILER_ANDROID_API_KEY',
  );

  static String get mapTilerPlatformApiKey =>
      kIsWeb ? mapTilerWebApiKey : mapTilerAndroidApiKey;

  static String get mapTilerStyleUrlWithKey => buildMapTilerStyleUrl(
    baseStyleUrl: mapTilerStyleUrl,
    apiKey: mapTilerPlatformApiKey,
  );

  static const String _defaultMapLatitudeValue = String.fromEnvironment(
    'MAPS_DEFAULT_LATITUDE',
    defaultValue: '-23.1175',
  );

  static const String _defaultMapLongitudeValue = String.fromEnvironment(
    'MAPS_DEFAULT_LONGITUDE',
    defaultValue: '-46.5502',
  );

  static double get defaultMapLatitude =>
      double.tryParse(_defaultMapLatitudeValue) ?? -23.1175;

  static double get defaultMapLongitude =>
      double.tryParse(_defaultMapLongitudeValue) ?? -46.5502;

  static bool get diagnosticsEnabled => kDebugMode && environment != 'hosted';

  static String get buildMode => kDebugMode
      ? 'debug'
      : kProfileMode
      ? 'profile'
      : 'release';

  static void validate({bool debugMode = kDebugMode, bool web = kIsWeb}) {
    if (!supportedEnvironments.contains(environment)) {
      throw const AppConfigurationException(
        'APP_ENVIRONMENT inválido: $environment.',
      );
    }
    if (mapProvider.toLowerCase() != 'maptiler') {
      throw const AppConfigurationException(
        'MAP_PROVIDER não suportado nesta versão: $mapProvider.',
      );
    }
    if (demoMode != (environment == 'demo')) {
      throw const AppConfigurationException(
        'DEMO_MODE deve ser true somente no perfil demo.',
      );
    }
    if (web &&
        <String>{
          'android_emulator',
          'android_physical_device',
          'demo_network',
        }.contains(environment)) {
      throw const AppConfigurationException(
        'O perfil $environment não é compatível com Flutter Web.',
      );
    }
    if (!web && environment == 'local_web') {
      throw const AppConfigurationException(
        'O perfil local_web é exclusivo do Flutter Web.',
      );
    }
    if (mapTilerConfigured) {
      final String apiKey = web ? mapTilerWebApiKey : mapTilerAndroidApiKey;
      if (apiKey.trim().isEmpty) {
        throw AppConfigurationException(
          web
              ? 'MAPTILER_CONFIGURED=true no Web exige '
                    'MAPTILER_WEB_API_KEY.'
              : 'MAPTILER_CONFIGURED=true no Android exige '
                    'MAPTILER_ANDROID_API_KEY.',
        );
      }
      buildMapTilerStyleUrl(baseStyleUrl: mapTilerStyleUrl, apiKey: apiKey);
    }
    if (!defaultMapLatitude.isFinite ||
        !defaultMapLongitude.isFinite ||
        defaultMapLatitude < -90 ||
        defaultMapLatitude > 90 ||
        defaultMapLongitude < -180 ||
        defaultMapLongitude > 180) {
      throw const AppConfigurationException(
        'MAPS_DEFAULT_LATITUDE/LONGITUDE devem formar uma coordenada válida.',
      );
    }
    if (demoMode) return;

    final Uri? uri = Uri.tryParse(apiBaseUrl);
    if (uri == null ||
        !uri.hasScheme ||
        uri.host.isEmpty ||
        !<String>{'http', 'https'}.contains(uri.scheme)) {
      throw const AppConfigurationException(
        'API_BASE_URL deve ser uma URL HTTP/HTTPS absoluta: $apiBaseUrl.',
      );
    }
    if (environment == 'hosted' && uri.scheme != 'https') {
      throw const AppConfigurationException(
        'O perfil hosted exige API_BASE_URL com HTTPS.',
      );
    }
    if (web && uri.host == '10.0.2.2') {
      throw const AppConfigurationException(
        'Flutter Web não pode usar 10.0.2.2; use localhost, LAN ou HTTPS.',
      );
    }
    if (environment == 'android_emulator' &&
        <String>{'localhost', '127.0.0.1', '::1'}.contains(uri.host)) {
      throw const AppConfigurationException(
        'Android Emulator deve usar 10.0.2.2 para acessar o backend do host.',
      );
    }
    if (<String>{
          'android_physical_device',
          'demo_network',
        }.contains(environment) &&
        <String>{
          'localhost',
          '127.0.0.1',
          '::1',
          '10.0.2.2',
        }.contains(uri.host)) {
      throw const AppConfigurationException(
        'Celular físico exige IP alcançável na LAN ou uma URL HTTPS.',
      );
    }

    final bool localDevelopmentHost = <String>{
      'localhost',
      '127.0.0.1',
      '::1',
      '10.0.2.2',
    }.contains(uri.host);
    if (uri.scheme == 'http' && !localDevelopmentHost) {
      final bool explicitlyAllowedLan =
          debugMode &&
          allowInsecureLanHttp &&
          <String>{
            'android_physical_device',
            'demo_network',
          }.contains(environment);
      if (!explicitlyAllowedLan) {
        throw const AppConfigurationException(
          'HTTP fora do host local exige build debug, perfil de LAN e '
          'ALLOW_INSECURE_LAN_HTTP=true. Prefira HTTPS.',
        );
      }
    }
    final bool localWebReleaseOnLoopback =
        web && environment == 'local_web' && localDevelopmentHost;
    if (!debugMode && uri.scheme != 'https' && !localWebReleaseOnLoopback) {
      throw const AppConfigurationException(
        'Build não-debug integrado exige API_BASE_URL com HTTPS, exceto no '
        'perfil local_web restrito ao loopback.',
      );
    }
  }

  static String get diagnosticSummary =>
      'ambiente=$environment; demo=$demoMode; api=$apiBaseUrl; '
      'mapa=$mapProvider; mapTiler=$mapTilerConfigured; plataforma='
      '${kIsWeb ? 'web' : defaultTargetPlatform.name}';

  static String buildMapTilerStyleUrl({
    required String baseStyleUrl,
    required String apiKey,
  }) {
    final Uri? uri = Uri.tryParse(baseStyleUrl.trim());
    if (uri == null ||
        uri.scheme != 'https' ||
        uri.host.toLowerCase() != 'api.maptiler.com' ||
        !uri.path.endsWith('/style.json')) {
      throw const AppConfigurationException(
        'MAPTILER_STYLE_URL deve ser uma URL HTTPS de style.json em '
        'api.maptiler.com.',
      );
    }
    if (uri.queryParameters.containsKey('key')) {
      throw const AppConfigurationException(
        'MAPTILER_STYLE_URL deve ser a URL base sem o parâmetro key.',
      );
    }
    final String normalizedKey = apiKey.trim();
    if (normalizedKey.isEmpty) {
      throw const AppConfigurationException('A chave MapTiler está vazia.');
    }
    final String lowerKey = normalizedKey.toLowerCase();
    if (lowerKey.contains('://') || lowerKey.contains('key=')) {
      throw const AppConfigurationException(
        'MAPTILER_*_API_KEY deve conter somente a chave, não uma URL ou iframe.',
      );
    }
    return uri
        .replace(
          queryParameters: <String, String>{
            ...uri.queryParameters,
            'key': normalizedKey,
          },
        )
        .toString();
  }
}
