import '../config/app_config.dart';
import '../models/delivery_point.dart';

abstract interface class MapProvider {
  String get id;
  String get displayName;
  bool get isDevelopmentFallback;

  Future<List<PlaceSuggestion>> search(String query);

  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion);

  Future<String> reverseGeocode(GeoCoordinate coordinate);

  GeoCoordinate moveMarker({
    required GeoCoordinate center,
    required double normalizedDx,
    required double normalizedDy,
  });
}

/// Boundary between the UI/domain-facing provider and the backend map API.
/// Keeping provider-specific HTTP contracts out of widgets makes the renderer
/// replaceable without changing the delivery-point flow.
abstract interface class OnlineMapBridge {
  Future<List<PlaceSuggestion>> search(String query);
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion);
  Future<String> reverseGeocode(GeoCoordinate coordinate);
}

class MapTilerMapProvider implements MapProvider {
  MapTilerMapProvider(this._bridge);

  final OnlineMapBridge _bridge;

  @override
  String get id => 'maptiler';

  @override
  String get displayName => 'MapTiler';

  @override
  bool get isDevelopmentFallback => false;

  @override
  GeoCoordinate moveMarker({
    required GeoCoordinate center,
    required double normalizedDx,
    required double normalizedDy,
  }) {
    return GeoCoordinate(
      latitude: center.latitude - (normalizedDy * 0.006),
      longitude: center.longitude + (normalizedDx * 0.006),
    );
  }

  @override
  Future<String> reverseGeocode(GeoCoordinate coordinate) {
    return _bridge.reverseGeocode(coordinate);
  }

  @override
  Future<List<PlaceSuggestion>> search(String query) => _bridge.search(query);

  @override
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion) {
    return _bridge.resolve(suggestion);
  }
}

class DevelopmentMapProvider implements MapProvider {
  const DevelopmentMapProvider({this.fallbackForMapTiler = false});

  final bool fallbackForMapTiler;

  static const List<PlaceSuggestion> _places = <PlaceSuggestion>[
    PlaceSuggestion(
      label: 'Campus acadêmico',
      referenceAddress: 'Av. Universitária, 1000 — região aproximada',
      coordinate: GeoCoordinate(latitude: -23.117500, longitude: -46.550200),
    ),
    PlaceSuggestion(
      label: 'Praça central',
      referenceAddress: 'Praça Central — região aproximada',
      coordinate: GeoCoordinate(latitude: -23.115820, longitude: -46.547920),
    ),
    PlaceSuggestion(
      label: 'Parque de testes',
      referenceAddress: 'Área acadêmica controlada — referência',
      coordinate: GeoCoordinate(latitude: -23.120100, longitude: -46.553400),
    ),
  ];

  @override
  String get id => 'development_fallback';

  @override
  String get displayName => fallbackForMapTiler
      ? 'Mapa local (MapTiler não configurado)'
      : 'Mapa local';

  @override
  bool get isDevelopmentFallback => true;

  @override
  GeoCoordinate moveMarker({
    required GeoCoordinate center,
    required double normalizedDx,
    required double normalizedDy,
  }) {
    return GeoCoordinate(
      latitude: center.latitude - (normalizedDy * 0.006),
      longitude: center.longitude + (normalizedDx * 0.006),
    );
  }

  @override
  Future<String> reverseGeocode(GeoCoordinate coordinate) async {
    return 'Ponto manual próximo de ${coordinate.formatted}';
  }

  @override
  Future<List<PlaceSuggestion>> search(String query) async {
    final String normalized = query.trim().toLowerCase();
    if (normalized.isEmpty) return _places;
    return _places
        .where((PlaceSuggestion place) {
          return '${place.label} ${place.referenceAddress}'
              .toLowerCase()
              .contains(normalized);
        })
        .toList(growable: false);
  }

  @override
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion) async {
    if (!suggestion.isResolved) {
      throw StateError('O fallback recebeu uma sugestão sem coordenadas.');
    }
    return suggestion;
  }
}

abstract final class MapProviderFactory {
  static MapProvider create({
    String configuredProvider = AppConfig.mapProvider,
    bool mapTilerConfigured = AppConfig.mapTilerConfigured,
    OnlineMapBridge? onlineMapBridge,
  }) {
    final bool wantsMapTiler = configuredProvider.toLowerCase() == 'maptiler';
    if (wantsMapTiler && mapTilerConfigured && onlineMapBridge != null) {
      return MapTilerMapProvider(onlineMapBridge);
    }
    return DevelopmentMapProvider(fallbackForMapTiler: wantsMapTiler);
  }
}
