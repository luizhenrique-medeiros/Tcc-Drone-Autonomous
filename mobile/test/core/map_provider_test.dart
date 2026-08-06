import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MapProviderFactory', () {
    test('usa fallback explícito quando Google não possui bridge', () {
      final MapProvider provider = MapProviderFactory.create(
        configuredProvider: 'google_maps',
      );

      expect(provider, isA<DevelopmentMapProvider>());
      expect(provider.isDevelopmentFallback, isTrue);
      expect(provider.displayName, contains('Google não conectado'));
    });

    test('converte movimento do marcador em novas coordenadas', () {
      const MapProvider provider = DevelopmentMapProvider();
      const GeoCoordinate center = GeoCoordinate(
        latitude: -23.1175,
        longitude: -46.5502,
      );

      final GeoCoordinate moved = provider.moveMarker(
        center: center,
        normalizedDx: 0.25,
        normalizedDy: -0.25,
      );

      expect(moved.latitude, greaterThan(center.latitude));
      expect(moved.longitude, greaterThan(center.longitude));
      expect(moved.formatted, isNot(center.formatted));
    });

    test('usa Google somente quando configurado e com bridge', () {
      final MapProvider provider = MapProviderFactory.create(
        configuredProvider: 'google_maps',
        googleMapsConfigured: true,
        googleMapsBridge: _FakeGoogleMapsBridge(),
      );

      expect(provider, isA<GoogleMapsProvider>());
      expect(provider.isDevelopmentFallback, isFalse);
    });

    test(
      'fallback informa zero resultados sem sugerir locais errados',
      () async {
        const MapProvider provider = DevelopmentMapProvider();
        expect(await provider.search('endereco que nao existe'), isEmpty);
      },
    );
  });
}

class _FakeGoogleMapsBridge implements GoogleMapsBridge {
  @override
  Future<String> reverseGeocode(GeoCoordinate coordinate) async => 'Teste';

  @override
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion) async =>
      suggestion;

  @override
  Future<List<PlaceSuggestion>> search(String query) async =>
      <PlaceSuggestion>[];
}
