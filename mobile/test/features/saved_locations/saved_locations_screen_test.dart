import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/app/app_scope.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/saved_location.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/saved_location_repository.dart';
import 'package:drone_delivery_mobile/design_system/components/app_button.dart';
import 'package:drone_delivery_mobile/design_system/theme/app_theme.dart';
import 'package:drone_delivery_mobile/features/products/presentation/home_screen.dart';
import 'package:drone_delivery_mobile/features/saved_locations/presentation/saved_location_form_screen.dart';
import 'package:drone_delivery_mobile/features/saved_locations/presentation/saved_locations_screen.dart';
import 'package:drone_delivery_mobile/features/saved_locations/presentation/widgets/saved_location_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('Conta mostra e abre Minhas localizações', (
    WidgetTester tester,
  ) async {
    _setViewport(tester, const Size(320, 1000));
    final AppController controller = _controller();
    addTearDown(controller.dispose);
    await controller.initialize();
    await tester.pumpWidget(
      _TestHost(controller: controller, child: const HomeScreen()),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Conta'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('open-saved-locations')), findsOneWidget);

    await tester.tap(find.byKey(const Key('open-saved-locations')));
    await tester.pumpAndSettle();
    expect(find.byType(SavedLocationsScreen), findsOneWidget);
    expect(find.text('0 de 3 localizações salvas'), findsOneWidget);
  });

  for (int count = 0; count <= 3; count++) {
    testWidgets(
      'renderiza exatamente $count localizações e contador dinâmico',
      (WidgetTester tester) async {
        _setViewport(tester);
        final AppController controller = _controller(
          initialLocations: List<SavedLocation>.generate(
            count,
            (int index) => _location(index + 1),
          ),
        );
        addTearDown(controller.dispose);
        await controller.savedLocations.load();
        await tester.pumpWidget(
          _TestHost(
            controller: controller,
            child: const SavedLocationsScreen(),
          ),
        );
        await tester.pumpAndSettle();

        expect(find.byType(SavedLocationCard), findsNWidgets(count));
        expect(find.text('$count de 3 localizações salvas'), findsOneWidget);
        final AppButton add = tester.widget<AppButton>(
          find.byKey(const Key('add-saved-location')),
        );
        expect(add.onPressed, count == 3 ? isNull : isNotNull);
      },
    );
  }

  testWidgets('exclui após diálogo sem afetar cards inexistentes', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    final AppController controller = _controller(
      initialLocations: <SavedLocation>[_location(1)],
    );
    addTearDown(controller.dispose);
    await controller.savedLocations.load();
    await tester.pumpWidget(
      _TestHost(controller: controller, child: const SavedLocationsScreen()),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Excluir'));
    await tester.pumpAndSettle();
    expect(find.text('Excluir localização?'), findsOneWidget);
    await tester.tap(find.byKey(const Key('confirm-delete-saved-location')));
    await tester.pumpAndSettle();

    expect(find.byType(SavedLocationCard), findsNothing);
    expect(find.text('0 de 3 localizações salvas'), findsOneWidget);
  });

  testWidgets('formulário cria localização nomeada com até 40 caracteres', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    final AppController controller = _controller();
    addTearDown(controller.dispose);
    await controller.savedLocations.load();
    const LocationSelectionResult selection = LocationSelectionResult(
      approximatePlace: PlaceSuggestion(
        label: 'Ponto manual',
        referenceAddress: 'Local sem endereço identificado',
        coordinate: GeoCoordinate(latitude: -23.1, longitude: -46.1),
      ),
      finalCoordinate: GeoCoordinate(latitude: -23.1001, longitude: -46.1001),
      instructions: 'Portão lateral',
      safeAreaConfirmed: true,
      mapProvider: 'development_fallback',
      mapType: 'hybrid',
      regionConfirmed: true,
      exactPointSelected: true,
      userConfirmed: true,
      wasAdjusted: true,
    );
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: const SavedLocationFormScreen(initialSelection: selection),
      ),
    );

    await tester.enterText(
      find.byKey(const Key('saved-location-name-field')),
      'Casa da vó',
    );
    await tester.ensureVisible(find.byKey(const Key('save-saved-location')));
    await tester.tap(find.byKey(const Key('save-saved-location')));
    await tester.pumpAndSettle();

    expect(controller.savedLocations.locations.single.name, 'Casa da vó');
    expect(
      controller.savedLocations.locations.single.coordinate.formatted,
      '-23.100100, -46.100100',
    );
  });

  testWidgets('editar nome preserva a precisão quando ponto não muda', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    final SavedLocation location = _location(1).copyWith(accuracyMeters: 6.5);
    final AppController controller = _controller(
      initialLocations: <SavedLocation>[location],
    );
    addTearDown(controller.dispose);
    await controller.savedLocations.load();
    final LocationSelectionResult selection = LocationSelectionResult(
      approximatePlace: location.asPlaceSuggestion,
      finalCoordinate: location.coordinate,
      instructions: location.instructions ?? '',
      safeAreaConfirmed: true,
      mapProvider: location.mapProvider,
      mapType: location.mapType,
      regionConfirmed: true,
      exactPointSelected: true,
      userConfirmed: true,
      wasAdjusted: false,
      addressReference: location.addressReference,
    );
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: SavedLocationFormScreen(
          location: location,
          initialSelection: selection,
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const Key('saved-location-name-field')),
      'Casa atualizada',
    );
    await tester.ensureVisible(find.byKey(const Key('save-saved-location')));
    await tester.tap(find.byKey(const Key('save-saved-location')));
    await tester.pumpAndSettle();

    expect(controller.savedLocations.locations.single.name, 'Casa atualizada');
    expect(controller.savedLocations.locations.single.accuracyMeters, 6.5);
  });
}

void _setViewport(WidgetTester tester, [Size size = const Size(600, 1400)]) {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
}

AppController _controller({
  Iterable<SavedLocation> initialLocations = const <SavedLocation>[],
}) {
  return AppController(
    authRepository: DemoAuthRepository(),
    productRepository: DemoProductRepository(),
    checkoutRepository: const DemoCheckoutRepository(),
    savedLocationRepository: DemoSavedLocationRepository(
      initialLocations: initialLocations,
    ),
    mapProvider: const DevelopmentMapProvider(),
    locationService: const DevelopmentLocationService(),
    isDemoMode: true,
  );
}

SavedLocation _location(int index) {
  return SavedLocation(
    id: 'local-$index',
    name: 'Local $index',
    coordinate: GeoCoordinate(latitude: -23 + index / 1000, longitude: -46),
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    userConfirmedSafeArea: true,
    createdAt: DateTime.utc(2026, 8, index),
    updatedAt: DateTime.utc(2026, 8, index),
  );
}

class _TestHost extends StatelessWidget {
  const _TestHost({required this.controller, required this.child});

  final AppController controller;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controller: controller,
      child: MaterialApp(theme: AppTheme.light, home: child),
    );
  }
}
