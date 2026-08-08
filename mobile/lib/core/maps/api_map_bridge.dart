import '../models/delivery_point.dart';
import '../network/api_client.dart';
import 'map_provider.dart';

/// Adapter for the normalized map endpoints exposed by the backend.
class ApiMapBridge implements OnlineMapBridge {
  ApiMapBridge(this._client);

  final ApiClient _client;

  @override
  Future<List<PlaceSuggestion>> search(String query) async {
    final Object? payload = await _client.get(
      '/api/v1/maps/places/search?q=${Uri.encodeQueryComponent(query)}',
    );
    if (payload is! List) {
      throw const ApiException('Resposta inválida da pesquisa de lugares.');
    }
    return payload
        .map<PlaceSuggestion>((Object? item) {
          final Map<String, Object?> json = expectJsonMap(item);
          return PlaceSuggestion(
            label: (json['main_text'] ?? json['description'] ?? '').toString(),
            referenceAddress: (json['description'] ?? '').toString(),
            providerId: json['place_id']?.toString(),
          );
        })
        .toList(growable: false);
  }

  @override
  Future<PlaceSuggestion> resolve(PlaceSuggestion suggestion) async {
    if (suggestion.coordinate != null) return suggestion;
    final String geocodeQuery = suggestion.providerId == null
        ? 'address=${Uri.encodeQueryComponent(suggestion.referenceAddress)}'
        : 'place_id=${Uri.encodeQueryComponent(suggestion.providerId!)}';
    final Map<String, Object?> json = expectJsonMap(
      await _client.get('/api/v1/maps/geocode?$geocodeQuery'),
    );
    final Object? rawLatitude = json['latitude'];
    final Object? rawLongitude = json['longitude'];
    if (rawLatitude is! num || rawLongitude is! num) {
      throw const ApiException(
        'O serviço de mapas retornou coordenadas inválidas.',
      );
    }
    final double latitude = rawLatitude.toDouble();
    final double longitude = rawLongitude.toDouble();
    if (!GeoCoordinate.valuesAreValid(latitude, longitude)) {
      throw const ApiException(
        'O serviço de mapas retornou coordenadas fora da faixa válida.',
      );
    }
    return PlaceSuggestion(
      label: suggestion.label,
      referenceAddress:
          (json['formatted_address'] ?? suggestion.referenceAddress).toString(),
      providerId: (json['place_id'] ?? suggestion.providerId)?.toString(),
      coordinate: GeoCoordinate(latitude: latitude, longitude: longitude),
    );
  }

  @override
  Future<String> reverseGeocode(GeoCoordinate coordinate) async {
    final Map<String, Object?> json = expectJsonMap(
      await _client.get(
        '/api/v1/maps/reverse-geocode?latitude=${coordinate.latitude}&longitude=${coordinate.longitude}',
      ),
    );
    return (json['formatted_address'] ?? 'Referência textual indisponível')
        .toString();
  }
}
