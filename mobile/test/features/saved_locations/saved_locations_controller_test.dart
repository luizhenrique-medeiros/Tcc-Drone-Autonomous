import 'dart:async';

import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/saved_location.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/saved_location_repository.dart';
import 'package:drone_delivery_mobile/features/saved_locations/application/saved_locations_controller.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('controla estados 0, 1, 2 e 3 sem criar posições vazias', () async {
    final SavedLocationsController controller = SavedLocationsController(
      repository: DemoSavedLocationRepository(),
    );
    addTearDown(controller.dispose);

    expect(controller.viewState, SavedLocationsViewState.loading);
    await controller.load();
    expect(controller.viewState, SavedLocationsViewState.empty);

    for (int index = 1; index <= 3; index++) {
      await controller.create(_draft(index));
      expect(controller.locations, hasLength(index));
      expect(
        controller.viewState,
        index == 3
            ? SavedLocationsViewState.limitReached
            : SavedLocationsViewState.success,
      );
    }
    expect(controller.limitReached, isTrue);
    await expectLater(
      controller.create(_draft(4)),
      throwsA(isA<ApiException>()),
    );
  });

  test('atualiza, exclui e reseta o cache autenticado', () async {
    final SavedLocationsController controller = SavedLocationsController(
      repository: DemoSavedLocationRepository(),
    );
    addTearDown(controller.dispose);
    await controller.load();
    final SavedLocation created = await controller.create(_draft(1));

    await controller.update(
      created.id,
      _confirmedDraft(
        'Trabalho',
        const GeoCoordinate(latitude: -23.2, longitude: -46.2),
      ),
    );
    expect(controller.locations.single.name, 'Trabalho');
    await controller.delete(created.id);
    expect(controller.viewState, SavedLocationsViewState.empty);

    await controller.create(_draft(2));
    await controller.reset();
    expect(controller.locations, isEmpty);
    expect(controller.hasLoaded, isFalse);
    expect(controller.viewState, SavedLocationsViewState.loading);
  });

  test('distingue offline de erro comum', () async {
    final SavedLocationsController offline = SavedLocationsController(
      repository: const _FailingRepository(
        ApiException('Sem rede', isConnectivityFailure: true),
      ),
    );
    addTearDown(offline.dispose);
    await offline.load();
    expect(offline.viewState, SavedLocationsViewState.offline);

    final SavedLocationsController error = SavedLocationsController(
      repository: _FailingRepository(StateError('API inválida')),
    );
    addTearDown(error.dispose);
    await error.load();
    expect(error.viewState, SavedLocationsViewState.error);
  });

  test('refresh offline não apresenta cache antigo como sucesso', () async {
    final SavedLocationsController controller = SavedLocationsController(
      repository: _LoadThenFailRepository(),
    );
    addTearDown(controller.dispose);

    await controller.load();
    expect(controller.viewState, SavedLocationsViewState.success);
    expect(controller.locations, hasLength(1));

    await controller.refresh();
    expect(controller.locations, hasLength(1));
    expect(controller.viewState, SavedLocationsViewState.offline);
  });

  test('reset de sessão limpa armazenamento demo', () async {
    final DemoSavedLocationRepository repository =
        DemoSavedLocationRepository();
    final SavedLocationsController controller = SavedLocationsController(
      repository: repository,
    );
    addTearDown(controller.dispose);
    await controller.load();
    await controller.create(_draft(1));

    await controller.reset(clearSessionData: true);
    await controller.load();

    expect(controller.locations, isEmpty);
  });

  test(
    'resposta de criação anterior ao reset não contamina a sessão',
    () async {
      final _DelayedCreateRepository repository = _DelayedCreateRepository();
      final SavedLocationsController controller = SavedLocationsController(
        repository: repository,
      );
      addTearDown(controller.dispose);
      await controller.load();

      final Future<SavedLocation> staleCreate = controller.create(_draft(1));
      await Future<void>.delayed(Duration.zero);
      await controller.reset();
      await controller.load();
      repository.complete();
      await staleCreate;

      expect(controller.locations, isEmpty);
      expect(controller.viewState, SavedLocationsViewState.empty);
      expect(controller.isCreating, isFalse);
    },
  );

  test('refresh da mesma sessão não abandona criação em andamento', () async {
    final _DelayedCreateRepository repository = _DelayedCreateRepository();
    final SavedLocationsController controller = SavedLocationsController(
      repository: repository,
    );
    addTearDown(controller.dispose);
    await controller.load();

    final Future<SavedLocation> create = controller.create(_draft(1));
    await Future<void>.delayed(Duration.zero);
    await controller.refresh();
    repository.complete();
    await create;

    expect(controller.locations.single.name, 'Local 1');
    expect(controller.isCreating, isFalse);
  });
}

SavedLocationDraft _draft(int index) {
  return _confirmedDraft(
    'Local $index',
    GeoCoordinate(latitude: -23 + index / 1000, longitude: -46),
  );
}

SavedLocationDraft _confirmedDraft(String name, GeoCoordinate coordinate) {
  return SavedLocationDraft(
    name: name,
    coordinate: coordinate,
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    userConfirmedSafeArea: true,
  );
}

class _FailingRepository implements SavedLocationRepository {
  const _FailingRepository(this.error);

  final Object error;

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) =>
      Future<SavedLocation>.error(error);

  @override
  Future<void> deleteSavedLocation(String locationId) =>
      Future<void>.error(error);

  @override
  Future<List<SavedLocation>> listSavedLocations() =>
      Future<List<SavedLocation>>.error(error);

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) => Future<SavedLocation>.error(error);
}

class _LoadThenFailRepository implements SavedLocationRepository {
  int _loads = 0;

  @override
  Future<List<SavedLocation>> listSavedLocations() async {
    _loads++;
    if (_loads > 1) {
      throw const ApiException('Sem rede', isConnectivityFailure: true);
    }
    return <SavedLocation>[
      const SavedLocation(
        id: 'cached-1',
        name: 'Casa',
        coordinate: GeoCoordinate(latitude: -23, longitude: -46),
        mapProvider: 'maptiler',
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        userConfirmedSafeArea: true,
      ),
    ];
  }

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) async =>
      throw UnimplementedError();

  @override
  Future<void> deleteSavedLocation(String locationId) async =>
      throw UnimplementedError();

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) async => throw UnimplementedError();
}

class _DelayedCreateRepository implements SavedLocationRepository {
  final Completer<SavedLocation> _create = Completer<SavedLocation>();
  SavedLocationDraft? _draft;

  void complete() {
    final SavedLocationDraft draft = _draft!;
    _create.complete(
      SavedLocation(
        id: 'stale-create',
        name: draft.name,
        coordinate: draft.coordinate,
        mapProvider: draft.mapProvider,
        mapType: draft.mapType,
        regionConfirmed: draft.regionConfirmed,
        exactPointSelected: draft.exactPointSelected,
        userConfirmed: draft.userConfirmed,
        userConfirmedSafeArea: draft.userConfirmedSafeArea,
      ),
    );
  }

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) {
    _draft = draft;
    return _create.future;
  }

  @override
  Future<void> deleteSavedLocation(String locationId) async {}

  @override
  Future<List<SavedLocation>> listSavedLocations() async => <SavedLocation>[];

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) async => throw UnimplementedError();
}
