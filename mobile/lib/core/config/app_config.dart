abstract final class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  static const bool demoMode = bool.fromEnvironment(
    'DEMO_MODE',
    defaultValue: true,
  );

  static const String mapProvider = String.fromEnvironment(
    'MAP_PROVIDER',
    defaultValue: 'google_maps',
  );

  static const bool googleMapsConfigured = bool.fromEnvironment(
    'GOOGLE_MAPS_CONFIGURED',
    defaultValue: false,
  );
}
