class GeoCoordinate {
  const GeoCoordinate({required this.latitude, required this.longitude});

  final double latitude;
  final double longitude;

  static bool valuesAreValid(double latitude, double longitude) =>
      latitude.isFinite &&
      longitude.isFinite &&
      latitude >= -90 &&
      latitude <= 90 &&
      longitude >= -180 &&
      longitude <= 180;

  bool get isValid => valuesAreValid(latitude, longitude);

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
    this.mapType = 'hybrid',
    this.addressReference,
  }) : assert(
         approximatePlace.coordinate != null,
         'A região deve ser geocodificada antes de criar o ponto final.',
       );

  final PlaceSuggestion approximatePlace;
  final GeoCoordinate finalCoordinate;
  final String instructions;
  final bool safeAreaConfirmed;
  final String mapProvider;
  final String mapType;
  final String? addressReference;
}

class LocationSelectionResult {
  const LocationSelectionResult({
    required this.approximatePlace,
    required this.finalCoordinate,
    required this.instructions,
    required this.safeAreaConfirmed,
    required this.mapProvider,
    required this.mapType,
    required this.regionConfirmed,
    required this.exactPointSelected,
    required this.userConfirmed,
    required this.wasAdjusted,
    this.addressReference,
    this.savedLocationId,
  });

  final PlaceSuggestion approximatePlace;
  final GeoCoordinate finalCoordinate;
  final String instructions;
  final bool safeAreaConfirmed;
  final String mapProvider;
  final String mapType;
  final bool regionConfirmed;
  final bool exactPointSelected;
  final bool userConfirmed;
  final bool wasAdjusted;
  final String? addressReference;
  final String? savedLocationId;

  bool get usesSavedLocationWithoutAdjustment =>
      savedLocationId != null && !wasAdjusted;

  DeliveryPointDraft toDeliveryPointDraft() {
    return DeliveryPointDraft(
      approximatePlace: approximatePlace,
      finalCoordinate: finalCoordinate,
      instructions: instructions,
      safeAreaConfirmed: safeAreaConfirmed,
      mapProvider: mapProvider,
      mapType: mapType,
      addressReference: addressReference,
    );
  }
}
