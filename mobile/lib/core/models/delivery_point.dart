class GeoCoordinate {
  const GeoCoordinate({required this.latitude, required this.longitude});

  final double latitude;
  final double longitude;

  String get formatted =>
      '${latitude.toStringAsFixed(6)}, ${longitude.toStringAsFixed(6)}';
}

class PlaceSuggestion {
  const PlaceSuggestion({
    required this.label,
    required this.referenceAddress,
    this.coordinate,
    this.providerId,
  });

  final String label;
  final String referenceAddress;
  final GeoCoordinate? coordinate;
  final String? providerId;

  bool get isResolved => coordinate != null;
}

class DeliveryPointDraft {
  DeliveryPointDraft({
    required this.approximatePlace,
    required this.finalCoordinate,
    required this.instructions,
    required this.safeAreaConfirmed,
    required this.mapProvider,
  }) : assert(
         approximatePlace.coordinate != null,
         'A região deve ser geocodificada antes de criar o ponto final.',
       );

  final PlaceSuggestion approximatePlace;
  final GeoCoordinate finalCoordinate;
  final String instructions;
  final bool safeAreaConfirmed;
  final String mapProvider;
}
