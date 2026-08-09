import 'dart:convert';
import 'dart:math';

import '../models/saved_location.dart';
import '../network/api_client.dart';

abstract interface class SavedLocationRepository {
  Future<List<SavedLocation>> listSavedLocations();

  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft);

  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  );

  Future<void> deleteSavedLocation(String locationId);
}

abstract interface class SessionScopedSavedLocationRepository {
  Future<void> clearSessionData();
}

class ApiSavedLocationRepository implements SavedLocationRepository {
  ApiSavedLocationRepository(this._client);

  final ApiClient _client;
  String? _createAttemptKey;
  String? _createAttemptFingerprint;

  @override
  Future<List<SavedLocation>> listSavedLocations() async {
    final Object? response = await _client.get('/api/v1/saved-locations');
    final Object? rawItems = response is Map ? response['items'] : response;
    if (rawItems is! List) {
      throw const ApiException(
        'A API retornou uma lista de localizações inválida.',
      );
    }
    return rawItems
        .map<SavedLocation>((Object? item) {
          return SavedLocation.fromJson(expectJsonMap(item));
        })
        .toList(growable: false);
  }

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) async {
    final Map<String, Object?> payload = draft.toJson();
    final String fingerprint = jsonEncode(payload);
    if (_createAttemptFingerprint != fingerprint || _createAttemptKey == null) {
      _createAttemptFingerprint = fingerprint;
      _createAttemptKey = _newAttemptKey();
    }
    final SavedLocation created = SavedLocation.fromJson(
      expectJsonMap(
        await _client.post(
          '/api/v1/saved-locations',
          body: payload,
          headers: <String, String>{'Idempotency-Key': _createAttemptKey!},
        ),
      ),
    );
    _createAttemptKey = null;
    _createAttemptFingerprint = null;
    return created;
  }

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) async {
    return SavedLocation.fromJson(
      expectJsonMap(
        await _client.patch(
          '/api/v1/saved-locations/${Uri.encodeComponent(locationId)}',
          body: draft.toJson(),
        ),
      ),
    );
  }

  @override
  Future<void> deleteSavedLocation(String locationId) async {
    await _client.delete(
      '/api/v1/saved-locations/${Uri.encodeComponent(locationId)}',
    );
  }

  static String _newAttemptKey() {
    final Random random = Random.secure();
    final String entropy = List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((int value) => value.toRadixString(16).padLeft(2, '0')).join();
    return 'mobile-saved-location-$entropy';
  }
}

class DemoSavedLocationRepository
    implements SavedLocationRepository, SessionScopedSavedLocationRepository {
  DemoSavedLocationRepository({
    Iterable<SavedLocation> initialLocations = const <SavedLocation>[],
  }) : _locations = List<SavedLocation>.of(initialLocations),
       _nextId = initialLocations.length + 1;

  static const int maximumLocations = 3;
  final List<SavedLocation> _locations;
  int _nextId;

  @override
  Future<List<SavedLocation>> listSavedLocations() async =>
      List<SavedLocation>.unmodifiable(_locations);

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) async {
    if (_locations.length >= maximumLocations) {
      throw const ApiException(
        'Você pode salvar no máximo 3 localizações.',
        statusCode: 409,
        code: 'SAVED_LOCATION_LIMIT_REACHED',
      );
    }
    final DateTime now = DateTime.now().toUtc();
    final SavedLocation created = SavedLocation(
      id: 'demo-saved-location-${_nextId++}',
      name: draft.name.trim(),
      coordinate: draft.coordinate,
      mapProvider: draft.mapProvider,
      mapType: draft.mapType,
      regionConfirmed: draft.regionConfirmed,
      exactPointSelected: draft.exactPointSelected,
      userConfirmed: draft.userConfirmed,
      userConfirmedSafeArea: draft.userConfirmedSafeArea,
      addressReference: _nullable(draft.addressReference),
      instructions: _nullable(draft.instructions),
      accuracyMeters: draft.accuracyMeters,
      createdAt: now,
      updatedAt: now,
    );
    _locations.add(created);
    return created;
  }

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) async {
    final int index = _locations.indexWhere(
      (SavedLocation location) => location.id == locationId,
    );
    if (index < 0) {
      throw const ApiException(
        'Localização salva não encontrada.',
        statusCode: 404,
      );
    }
    final String? address = _nullable(draft.addressReference);
    final String? instructions = _nullable(draft.instructions);
    final SavedLocation updated = _locations[index].copyWith(
      name: draft.name.trim(),
      coordinate: draft.coordinate,
      mapProvider: draft.mapProvider,
      mapType: draft.mapType,
      regionConfirmed: draft.regionConfirmed,
      exactPointSelected: draft.exactPointSelected,
      userConfirmed: draft.userConfirmed,
      userConfirmedSafeArea: draft.userConfirmedSafeArea,
      addressReference: address,
      clearAddressReference: address == null,
      instructions: instructions,
      clearInstructions: instructions == null,
      accuracyMeters: draft.accuracyMeters,
      clearAccuracyMeters: draft.accuracyMeters == null,
      updatedAt: DateTime.now().toUtc(),
    );
    _locations[index] = updated;
    return updated;
  }

  @override
  Future<void> deleteSavedLocation(String locationId) async {
    final int previousLength = _locations.length;
    _locations.removeWhere(
      (SavedLocation location) => location.id == locationId,
    );
    if (_locations.length == previousLength) {
      throw const ApiException(
        'Localização salva não encontrada.',
        statusCode: 404,
      );
    }
  }

  @override
  Future<void> clearSessionData() async {
    _locations.clear();
    _nextId = 1;
  }
}

String? _nullable(String? value) {
  final String text = value?.trim() ?? '';
  return text.isEmpty ? null : text;
}
