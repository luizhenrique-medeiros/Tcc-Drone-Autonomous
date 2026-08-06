import '../models/delivery_point.dart';
import '../network/api_client.dart';
import 'map_provider.dart';

class ApiGoogleMapsBridge implements GoogleMapsBridge {
  ApiGoogleMapsBridge(this._client);

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
    return PlaceSuggestion(
      label: suggestion.label,
      referenceAddress:
          (json['formatted_address'] ?? suggestion.referenceAddress).toString(),
      providerId: (json['place_id'] ?? suggestion.providerId)?.toString(),
      coordinate: GeoCoordinate(
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
      ),
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
