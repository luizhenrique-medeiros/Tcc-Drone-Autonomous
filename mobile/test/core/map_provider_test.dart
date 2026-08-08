import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('coordenada rejeita faixa inválida e valores não finitos', () {
    expect(
      const GeoCoordinate(latitude: -23.1, longitude: -46.5).isValid,
      isTrue,
    );
    expect(const GeoCoordinate(latitude: 91, longitude: 0).isValid, isFalse);
    expect(
      const GeoCoordinate(latitude: 0, longitude: double.infinity).isValid,
      isFalse,
    );
  });

  group('MapProviderFactory', () {
    test('usa fallback explícito quando MapTiler não possui bridge', () {
      final MapProvider provider = MapProviderFactory.create(
        configuredProvider: 'maptiler',
      );

      expect(provider, isA<DevelopmentMapProvider>());
      expect(provider.isDevelopmentFallback, isTrue);
      expect(provider.displayName, contains('MapTiler não configurado'));
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

    test('usa MapTiler somente quando configurado e com bridge', () {
      final MapProvider provider = MapProviderFactory.create(
        configuredProvider: 'maptiler',
        mapTilerConfigured: true,
        onlineMapBridge: _FakeOnlineMapBridge(),
      );

      expect(provider, isA<MapTilerMapProvider>());
      expect(provider.isDevelopmentFallback, isFalse);
      expect(provider.id, 'maptiler');
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

class _FakeOnlineMapBridge implements OnlineMapBridge {
  @override
  Future<String> reverseGeocode(GeoCoordinate coordinate) async => 'Teste';

  @override
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion) async =>
      suggestion;

  @override
  Future<List<PlaceSuggestion>> search(String query) async =>
      <PlaceSuggestion>[];
}
