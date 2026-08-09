import 'package:flutter/foundation.dart';

import '../../../core/models/saved_location.dart';
import '../../../core/network/api_client.dart';
import '../../../core/repositories/saved_location_repository.dart';

enum SavedLocationsViewState {
  loading,
  success,
  empty,
  limitReached,
  error,
  offline,
}

class SavedLocationsController extends ChangeNotifier {
  SavedLocationsController({required SavedLocationRepository repository})
    : _repository = repository;

  static const int maximumLocations = 3;

  final SavedLocationRepository _repository;
  final List<SavedLocation> _locations = <SavedLocation>[];
  final Set<String> _mutatingIds = <String>{};
  bool _disposed = false;
  int _generation = 0;
  int _sessionGeneration = 0;
  Future<void>? _pendingLoad;

  bool hasLoaded = false;
  bool isLoading = false;
  bool isRefreshing = false;
  bool isCreating = false;
  bool isOffline = false;
  String? loadError;
  String? mutationError;

  List<SavedLocation> get locations =>
      List<SavedLocation>.unmodifiable(_locations);
  bool get isEmpty => hasLoaded && _locations.isEmpty && loadError == null;
  bool get limitReached => _locations.length >= maximumLocations;
  bool isMutating(String id) => _mutatingIds.contains(id);

  SavedLocationsViewState get viewState {
    if (!hasLoaded && loadError == null) {
      return SavedLocationsViewState.loading;
    }
    if (loadError != null) {
      return isOffline
          ? SavedLocationsViewState.offline
          : SavedLocationsViewState.error;
    }
    if (limitReached) return SavedLocationsViewState.limitReached;
    if (_locations.isEmpty) return SavedLocationsViewState.empty;
    return SavedLocationsViewState.success;
  }

  Future<void> load({bool force = false}) {
    if (hasLoaded && !force) return Future<void>.value();
    if (_pendingLoad != null && !force) return _pendingLoad!;
    final int generation = force ? ++_generation : _generation;
    final Future<void> pending = _load(generation, refreshing: hasLoaded);
    _pendingLoad = pending;
    return pending.whenComplete(() {
      if (identical(_pendingLoad, pending)) _pendingLoad = null;
    });
  }

  Future<void> refresh() => load(force: true);

  Future<void> _load(int generation, {required bool refreshing}) async {
    if (refreshing) {
      isRefreshing = true;
    } else {
      isLoading = true;
    }
    loadError = null;
    _notify();
    try {
      final List<SavedLocation> loaded = await _repository.listSavedLocations();
      if (!_isCurrent(generation)) return;
      _locations
        ..clear()
        ..addAll(loaded);
      _sort();
      hasLoaded = true;
      isOffline = false;
      loadError = null;
    } on Object catch (error) {
      if (!_isCurrent(generation)) return;
      loadError = _message(error, 'Não foi possível carregar as localizações.');
      isOffline = _isOffline(error);
    } finally {
      if (_isCurrent(generation)) {
        isLoading = false;
        isRefreshing = false;
        _notify();
      }
    }
  }

  Future<SavedLocation> create(SavedLocationDraft draft) async {
    if (limitReached) {
      throw const ApiException(
        'Você já possui 3 localizações salvas. Exclua ou edite uma delas para adicionar outra.',
        statusCode: 409,
        code: 'SAVED_LOCATION_LIMIT_REACHED',
      );
    }
    final int generation = _sessionGeneration;
    isCreating = true;
    mutationError = null;
    _notify();
    try {
      final SavedLocation created = await _repository.createSavedLocation(
        draft,
      );
      if (!_isCurrentSession(generation)) return created;
      _upsert(created);
      hasLoaded = true;
      isOffline = false;
      return created;
    } on Object catch (error) {
      if (_isCurrentSession(generation)) {
        mutationError = _message(
          error,
          'Não foi possível salvar a localização.',
        );
        isOffline = _isOffline(error);
      }
      rethrow;
    } finally {
      if (_isCurrentSession(generation)) {
        isCreating = false;
        _notify();
      }
    }
  }

  Future<SavedLocation> update(
    String locationId,
    SavedLocationDraft draft,
  ) async {
    final int generation = _sessionGeneration;
    _mutatingIds.add(locationId);
    mutationError = null;
    _notify();
    try {
      final SavedLocation updated = await _repository.updateSavedLocation(
        locationId,
        draft,
      );
      if (!_isCurrentSession(generation)) return updated;
      _upsert(updated);
      isOffline = false;
      return updated;
    } on Object catch (error) {
      if (_isCurrentSession(generation)) {
        mutationError = _message(
          error,
          'Não foi possível atualizar a localização.',
        );
        isOffline = _isOffline(error);
      }
      rethrow;
    } finally {
      if (_isCurrentSession(generation)) {
        _mutatingIds.remove(locationId);
        _notify();
      }
    }
  }

  Future<void> delete(String locationId) async {
    final int generation = _sessionGeneration;
    _mutatingIds.add(locationId);
    mutationError = null;
    _notify();
    try {
      await _repository.deleteSavedLocation(locationId);
      if (!_isCurrentSession(generation)) return;
      _locations.removeWhere(
        (SavedLocation location) => location.id == locationId,
      );
      hasLoaded = true;
      isOffline = false;
    } on Object catch (error) {
      if (_isCurrentSession(generation)) {
        mutationError = _message(
          error,
          'Não foi possível excluir a localização.',
        );
        isOffline = _isOffline(error);
      }
      rethrow;
    } finally {
      if (_isCurrentSession(generation)) {
        _mutatingIds.remove(locationId);
        _notify();
      }
    }
  }

  Future<void> reset({bool clearSessionData = false}) async {
    _generation++;
    _sessionGeneration++;
    if (clearSessionData &&
        _repository is SessionScopedSavedLocationRepository) {
      await (_repository as SessionScopedSavedLocationRepository)
          .clearSessionData();
    }
    _locations.clear();
    _mutatingIds.clear();
    hasLoaded = false;
    isLoading = false;
    isRefreshing = false;
    isCreating = false;
    isOffline = false;
    loadError = null;
    mutationError = null;
    _notify();
  }

  void clearMutationError() {
    if (mutationError == null) return;
    mutationError = null;
    _notify();
  }

  void _upsert(SavedLocation location) {
    final int index = _locations.indexWhere(
      (SavedLocation current) => current.id == location.id,
    );
    if (index < 0) {
      _locations.add(location);
    } else {
      _locations[index] = location;
    }
    _sort();
  }

  void _sort() {
    _locations.sort((SavedLocation first, SavedLocation second) {
      final DateTime firstDate =
          first.updatedAt ??
          first.createdAt ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
      final DateTime secondDate =
          second.updatedAt ??
          second.createdAt ??
          DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
      return secondDate.compareTo(firstDate);
    });
  }

  bool _isCurrent(int generation) => !_disposed && generation == _generation;

  bool _isCurrentSession(int generation) =>
      !_disposed && generation == _sessionGeneration;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    super.dispose();
  }
}

String _message(Object error, String fallback) {
  final String message = error.toString().trim();
  return message.isEmpty ? fallback : message;
}

bool _isOffline(Object error) =>
    error is ApiException && error.isConnectivityFailure;
