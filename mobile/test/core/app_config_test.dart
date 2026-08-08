import 'package:drone_delivery_mobile/core/config/app_config.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('AppConfig.buildMapTilerStyleUrl', () {
    test('adiciona a chave sem perder parâmetros existentes', () {
      final String result = AppConfig.buildMapTilerStyleUrl(
        baseStyleUrl:
            'https://api.maptiler.com/maps/hybrid-v4/style.json?language=pt',
        apiKey: 'test-key',
      );
      final Uri uri = Uri.parse(result);

      expect(uri.queryParameters['language'], 'pt');
      expect(uri.queryParameters['key'], 'test-key');
    });

    test('rejeita URL que já contém chave', () {
      expect(
        () => AppConfig.buildMapTilerStyleUrl(
          baseStyleUrl:
              'https://api.maptiler.com/maps/hybrid-v4/style.json?key=exposta',
          apiKey: 'test-key',
        ),
        throwsA(isA<AppConfigurationException>()),
      );
    });

    test('rejeita host ou protocolo não permitido', () {
      expect(
        () => AppConfig.buildMapTilerStyleUrl(
          baseStyleUrl: 'http://example.test/style.json',
          apiKey: 'test-key',
        ),
        throwsA(isA<AppConfigurationException>()),
      );
    });

    test('rejeita URL completa no lugar da chave', () {
      expect(
        () => AppConfig.buildMapTilerStyleUrl(
          baseStyleUrl: 'https://api.maptiler.com/maps/hybrid-v4/style.json',
          apiKey:
              'https://api.maptiler.com/maps/hybrid-v4/style.json?key=teste',
        ),
        throwsA(isA<AppConfigurationException>()),
      );
    });
  });
}
