import 'delivery_point.dart';

class SavedLocation {
  const SavedLocation({
    required this.id,
    required this.name,
    required this.coordinate,
    required this.mapProvider,
    required this.mapType,
    required this.regionConfirmed,
    required this.exactPointSelected,
    required this.userConfirmed,
    required this.userConfirmedSafeArea,
    this.addressReference,
    this.instructions,
    this.accuracyMeters,
    this.createdAt,
    this.updatedAt,
  });

  factory SavedLocation.fromJson(Map<String, Object?> json) {
    final double latitude = _requiredNumber(
      json['final_latitude'] ?? json['latitude'],
      'final_latitude',
    );
    final double longitude = _requiredNumber(
      json['final_longitude'] ?? json['longitude'],
      'final_longitude',
    );
    if (!GeoCoordinate.valuesAreValid(latitude, longitude)) {
      throw const FormatException(
        'A localização salva possui coordenadas inválidas.',
      );
    }
    final String id = json['id']?.toString().trim() ?? '';
    final String name = json['name']?.toString().trim() ?? '';
    if (id.isEmpty || name.isEmpty) {
      throw const FormatException('A localização salva está incompleta.');
    }
    return SavedLocation(
      id: id,
      name: name,
      coordinate: GeoCoordinate(latitude: latitude, longitude: longitude),
      mapProvider: _requiredText(json['map_provider'], 'map_provider'),
      mapType: _requiredText(json['map_type'], 'map_type'),
      regionConfirmed: _requiredBool(
        json['region_confirmed'],
        'region_confirmed',
      ),
      exactPointSelected: _requiredBool(
        json['exact_point_selected'],
        'exact_point_selected',
      ),
      userConfirmed: _requiredBool(json['user_confirmed'], 'user_confirmed'),
      userConfirmedSafeArea: _requiredBool(
        json['user_confirmed_safe_area'],
        'user_confirmed_safe_area',
      ),
      addressReference: _optionalText(json['address_reference']),
      instructions: _optionalText(json['instructions']),
      accuracyMeters: _optionalNumber(json['accuracy_meters']),
      createdAt: _optionalDate(json['created_at']),
      updatedAt: _optionalDate(json['updated_at']),
    );
  }

  final String id;
  final String name;
  final GeoCoordinate coordinate;
  final String mapProvider;
  final String mapType;
  final bool regionConfirmed;
  final bool exactPointSelected;
  final bool userConfirmed;
  final bool userConfirmedSafeArea;
  final String? addressReference;
  final String? instructions;
  final double? accuracyMeters;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  PlaceSuggestion get asPlaceSuggestion => PlaceSuggestion(
    label: name,
    referenceAddress: addressReference ?? 'Local sem endereço identificado',
    coordinate: coordinate,
    providerId: 'saved-location:$id',
  );

  SavedLocation copyWith({
    String? name,
    GeoCoordinate? coordinate,
    String? mapProvider,
    String? mapType,
    bool? regionConfirmed,
    bool? exactPointSelected,
    bool? userConfirmed,
    bool? userConfirmedSafeArea,
    String? addressReference,
    bool clearAddressReference = false,
    String? instructions,
    bool clearInstructions = false,
    double? accuracyMeters,
    bool clearAccuracyMeters = false,
    DateTime? updatedAt,
  }) {
    return SavedLocation(
      id: id,
      name: name ?? this.name,
      coordinate: coordinate ?? this.coordinate,
      mapProvider: mapProvider ?? this.mapProvider,
      mapType: mapType ?? this.mapType,
      regionConfirmed: regionConfirmed ?? this.regionConfirmed,
      exactPointSelected: exactPointSelected ?? this.exactPointSelected,
      userConfirmed: userConfirmed ?? this.userConfirmed,
      userConfirmedSafeArea:
          userConfirmedSafeArea ?? this.userConfirmedSafeArea,
      addressReference: clearAddressReference
          ? null
          : addressReference ?? this.addressReference,
      instructions: clearInstructions
          ? null
          : instructions ?? this.instructions,
      accuracyMeters: clearAccuracyMeters
          ? null
          : accuracyMeters ?? this.accuracyMeters,
      createdAt: createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

class SavedLocationDraft {
  const SavedLocationDraft({
    required this.name,
    required this.coordinate,
    required this.mapProvider,
    required this.mapType,
    required this.regionConfirmed,
    required this.exactPointSelected,
    required this.userConfirmed,
    required this.userConfirmedSafeArea,
    this.addressReference,
    this.instructions,
    this.accuracyMeters,
  });

  static const int maxNameLength = 40;

  final String name;
  final GeoCoordinate coordinate;
  final String mapProvider;
  final String mapType;
  final bool regionConfirmed;
  final bool exactPointSelected;
  final bool userConfirmed;
  final bool userConfirmedSafeArea;
  final String? addressReference;
  final String? instructions;
  final double? accuracyMeters;

  Map<String, Object?> toJson() => <String, Object?>{
    'name': name.trim(),
    'final_latitude': coordinate.latitude,
    'final_longitude': coordinate.longitude,
    'map_provider': mapProvider,
    'map_type': mapType,
    'region_confirmed': regionConfirmed,
    'exact_point_selected': exactPointSelected,
    'user_confirmed': userConfirmed,
    'user_confirmed_safe_area': userConfirmedSafeArea,
    'address_reference': _nullableTrimmed(addressReference),
    'instructions': _nullableTrimmed(instructions),
    'accuracy_meters': accuracyMeters,
  };
}

double _requiredNumber(Object? value, String field) {
  final double? parsed = _optionalNumber(value);
  if (parsed == null) {
    throw FormatException('Campo numérico ausente: $field.');
  }
  return parsed;
}

double? _optionalNumber(Object? value) {
  if (value is num) return value.toDouble();
  if (value is String) return double.tryParse(value);
  return null;
}

String? _optionalText(Object? value) {
  final String text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

String? _nullableTrimmed(String? value) {
  final String text = value?.trim() ?? '';
  return text.isEmpty ? null : text;
}

DateTime? _optionalDate(Object? value) {
  final String text = value?.toString() ?? '';
  return text.isEmpty ? null : DateTime.tryParse(text)?.toUtc();
}

String _requiredText(Object? value, String field) {
  final String text = value?.toString().trim() ?? '';
  if (text.isEmpty) throw FormatException('Campo textual ausente: $field.');
  return text;
}

bool _requiredBool(Object? value, String field) {
  if (value is bool) return value;
  throw FormatException('Campo booleano ausente: $field.');
}
