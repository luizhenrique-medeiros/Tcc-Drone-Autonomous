import 'dart:async';

import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/models/saved_location.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/saved_location_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('cria pedido antes e transforma falha ao salvar em aviso', () async {
    final _FailingCreateRepository savedRepository = _FailingCreateRepository();
    final _CapturingCheckoutRepository checkout =
        _CapturingCheckoutRepository();
    final AppController controller = _controller(
      checkout: checkout,
      savedRepository: savedRepository,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    controller.addProduct(controller.products.first);
    controller.applyLocationSelection(_manualSelection());
    controller.configureSavedLocation(enabled: true, name: 'Casa');

    final String? error = await controller.submitOrder();
    await controller.pendingSavedLocationSave;

    expect(error, isNull);
    expect(controller.order, isNotNull);
    expect(checkout.calls, 1);
    expect(savedRepository.createCalls, 1);
    expect(controller.savedLocationWarning, contains('pedido foi criado'));
    expect(controller.savedLocations.limitReached, isTrue);
  });

  test('pedido não aguarda salvamento opcional pendente', () async {
    final _PendingCreateRepository savedRepository = _PendingCreateRepository();
    final AppController controller = _controller(
      checkout: _CapturingCheckoutRepository(),
      savedRepository: savedRepository,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    controller.addProduct(controller.products.first);
    controller.applyLocationSelection(_manualSelection());
    controller.configureSavedLocation(enabled: true, name: 'Casa');

    final String? error = await controller.submitOrder().timeout(
      const Duration(seconds: 1),
    );

    expect(error, isNull);
    expect(controller.order, isNotNull);
    expect(controller.isSavingLocationAfterOrder, isTrue);
    savedRepository.complete();
    await controller.pendingSavedLocationSave;
    await Future<void>.delayed(Duration.zero);
    expect(controller.isSavingLocationAfterOrder, isFalse);
    expect(controller.savedLocations.locations.single.name, 'Casa');
  });

  test('logout invalida salvamento opcional ainda pendente', () async {
    final _PendingCreateRepository savedRepository = _PendingCreateRepository();
    final AppController controller = _controller(
      checkout: _CapturingCheckoutRepository(),
      savedRepository: savedRepository,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    controller.addProduct(controller.products.first);
    controller.applyLocationSelection(_manualSelection());
    controller.configureSavedLocation(enabled: true, name: 'Sessão anterior');

    expect(await controller.submitOrder(), isNull);
    final Future<void> oldSave = controller.pendingSavedLocationSave!;
    await controller.logout();
    savedRepository.complete();
    await oldSave;
    await Future<void>.delayed(Duration.zero);

    expect(controller.savedLocations.locations, isEmpty);
    expect(controller.pendingSavedLocationSave, isNull);
    expect(controller.isSavingLocationAfterOrder, isFalse);
    expect(controller.savedLocationWarning, isNull);
  });

  test('ajuste de local salvo usa ponto manual e não muta o atalho', () async {
    final DemoSavedLocationRepository savedRepository =
        DemoSavedLocationRepository(
          initialLocations: <SavedLocation>[_saved()],
        );
    final _CapturingCheckoutRepository checkout =
        _CapturingCheckoutRepository();
    final AppController controller = _controller(
      checkout: checkout,
      savedRepository: savedRepository,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    controller.addProduct(controller.products.first);
    controller.applyLocationSelection(
      _savedSelection(
        coordinate: const GeoCoordinate(latitude: -23.2, longitude: -46.2),
        adjusted: true,
      ),
    );

    expect(await controller.submitOrder(), isNull);

    expect(checkout.lastRequest?.savedLocationId, isNull);
    expect(
      (await savedRepository.listSavedLocations()).single.coordinate.formatted,
      '-23.100000, -46.100000',
    );
  });

  test(
    'local salvo apenas revisado mantém id e confirmações no pedido',
    () async {
      final _CapturingCheckoutRepository checkout =
          _CapturingCheckoutRepository();
      final AppController controller = _controller(
        checkout: checkout,
        savedRepository: DemoSavedLocationRepository(
          initialLocations: <SavedLocation>[_saved()],
        ),
      );
      addTearDown(controller.dispose);
      await controller.initialize();
      controller.addProduct(controller.products.first);
      controller.applyLocationSelection(
        _savedSelection(coordinate: _saved().coordinate, adjusted: false),
      );

      expect(await controller.submitOrder(), isNull);

      expect(checkout.lastRequest?.savedLocationId, 'saved-1');
      expect(checkout.lastRequest?.savedLocationReviewConfirmed, isTrue);
      expect(checkout.lastRequest?.savedLocationSafeAreaConfirmed, isTrue);
    },
  );
}

AppController _controller({
  required CheckoutRepository checkout,
  required SavedLocationRepository savedRepository,
}) {
  return AppController(
    authRepository: DemoAuthRepository(),
    productRepository: DemoProductRepository(),
    checkoutRepository: checkout,
    savedLocationRepository: savedRepository,
    mapProvider: const DevelopmentMapProvider(),
    locationService: const DevelopmentLocationService(),
    isDemoMode: true,
  );
}

LocationSelectionResult _manualSelection() {
  return const LocationSelectionResult(
    approximatePlace: PlaceSuggestion(
      label: 'Ponto manual',
      referenceAddress: 'Sem endereço',
      coordinate: GeoCoordinate(latitude: -23.1, longitude: -46.1),
    ),
    finalCoordinate: GeoCoordinate(latitude: -23.1001, longitude: -46.1001),
    instructions: 'Portão',
    safeAreaConfirmed: true,
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    wasAdjusted: true,
  );
}

LocationSelectionResult _savedSelection({
  required GeoCoordinate coordinate,
  required bool adjusted,
}) {
  return LocationSelectionResult(
    approximatePlace: _saved().asPlaceSuggestion,
    finalCoordinate: coordinate,
    instructions: 'Portão',
    safeAreaConfirmed: true,
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    wasAdjusted: adjusted,
    savedLocationId: 'saved-1',
  );
}

SavedLocation _saved() {
  return const SavedLocation(
    id: 'saved-1',
    name: 'Casa',
    coordinate: GeoCoordinate(latitude: -23.1, longitude: -46.1),
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    userConfirmedSafeArea: true,
  );
}

class _CapturingCheckoutRepository implements CheckoutRepository {
  final DemoCheckoutRepository _delegate = const DemoCheckoutRepository(
    statusInterval: Duration(days: 1),
  );
  CheckoutRequest? lastRequest;
  int calls = 0;

  @override
  Future<OrderSnapshot> submit(CheckoutRequest request) {
    calls++;
    lastRequest = request;
    return _delegate.submit(request);
  }
}

class _FailingCreateRepository implements SavedLocationRepository {
  int createCalls = 0;

  @override
  Future<SavedLocation> createSavedLocation(SavedLocationDraft draft) {
    createCalls++;
    throw const ApiException(
      'Limite concorrente atingido.',
      statusCode: 409,
      code: 'SAVED_LOCATION_LIMIT_REACHED',
    );
  }

  @override
  Future<void> deleteSavedLocation(String locationId) async {}

  @override
  Future<List<SavedLocation>> listSavedLocations() async {
    if (createCalls == 0) return <SavedLocation>[];
    return List<SavedLocation>.generate(3, (int index) {
      return SavedLocation(
        id: 'server-${index + 1}',
        name: 'Servidor ${index + 1}',
        coordinate: GeoCoordinate(
          latitude: -23.1 - index / 1000,
          longitude: -46.1,
        ),
        mapProvider: 'maptiler',
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        userConfirmedSafeArea: true,
      );
    });
  }

  @override
  Future<SavedLocation> updateSavedLocation(
    String locationId,
    SavedLocationDraft draft,
  ) async => throw UnimplementedError();
}

class _PendingCreateRepository implements SavedLocationRepository {
  final Completer<SavedLocation> _create = Completer<SavedLocation>();
  SavedLocationDraft? _draft;

  void complete() {
    final SavedLocationDraft draft = _draft!;
    _create.complete(
      SavedLocation(
        id: 'saved-pending',
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
