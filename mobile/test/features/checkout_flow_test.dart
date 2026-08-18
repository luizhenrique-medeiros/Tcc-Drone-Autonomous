import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/app/app_scope.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/saved_location.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:drone_delivery_mobile/design_system/components/app_button.dart';
import 'package:drone_delivery_mobile/design_system/theme/app_theme.dart';
import 'package:drone_delivery_mobile/features/delivery_point/presentation/approximate_location_screen.dart';
import 'package:drone_delivery_mobile/features/delivery_point/presentation/exact_location_screen.dart';
import 'package:drone_delivery_mobile/features/payment/presentation/payment_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late AppController controller;

  setUp(() async {
    controller = AppController(
      authRepository: DemoAuthRepository(),
      productRepository: DemoProductRepository(),
      checkoutRepository: const DemoCheckoutRepository(
        statusInterval: Duration(days: 1),
      ),
      mapProvider: const DevelopmentMapProvider(),
      locationService: const DevelopmentLocationService(),
      isDemoMode: true,
    );
    await controller.initialize();
    controller.addProduct(controller.products.first);
    controller.selectApproximatePlace(
      const PlaceSuggestion(
        label: 'Campus',
        referenceAddress: 'Região aproximada',
        coordinate: GeoCoordinate(latitude: -23.1175, longitude: -46.5502),
      ),
    );
  });

  tearDown(() => controller.dispose());

  testWidgets('ponto exato exige mover marcador e confirmar área', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      _TestHost(controller: controller, child: const ExactLocationScreen()),
    );

    expect(controller.exactCoordinate, isNull);

    final Finder map = find.byKey(const Key('development-satellite-map'));
    await tester.ensureVisible(map);
    await tester.pumpAndSettle();
    final GestureDetector mapGesture = tester.widget<GestureDetector>(map);
    mapGesture.onPanUpdate!(
      DragUpdateDetails(
        delta: const Offset(140, 0),
        globalPosition: Offset.zero,
      ),
    );
    await tester.pump();
    expect(find.text('Mova o mapa para continuar'), findsNothing);
    final Finder safeArea = find.byKey(const Key('safe-area-confirmation'));
    await tester.scrollUntilVisible(
      safeArea,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    final Finder confirm = find.byKey(const Key('confirm-exact-point'));
    await tester.ensureVisible(confirm);
    await tester.pumpAndSettle();

    AppButton button = tester.widget<AppButton>(confirm);
    expect(button.onPressed, isNull);

    await tester.tap(safeArea);
    await tester.pump();

    button = tester.widget<AppButton>(confirm);
    expect(button.onPressed, isNotNull);

    await tester.tap(confirm);
    await tester.pumpAndSettle();
    expect(find.text('Confirme o ponto final'), findsOneWidget);
    expect(find.textContaining('-23.'), findsWidgets);
  });

  testWidgets('controle acessível move o pino sem gesto no mapa', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    await tester.pumpWidget(
      _TestHost(controller: controller, child: const ExactLocationScreen()),
    );
    await tester.pumpAndSettle();

    final Finder nudge = find.byKey(const Key('nudge-map-north'));
    await tester.scrollUntilVisible(
      nudge,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(nudge);
    await tester.pump();

    expect(find.text('Mova o mapa para continuar'), findsNothing);
    final Finder safeArea = find.byKey(const Key('safe-area-confirmation'));
    await tester.scrollUntilVisible(
      safeArea,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(safeArea);
    await tester.pump();
    final AppButton confirm = tester.widget<AppButton>(
      find.byKey(const Key('confirm-exact-point')),
    );
    expect(confirm.onPressed, isNotNull);
  });

  testWidgets('instrução alterada em local salvo vira ajuste do pedido', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    LocationSelectionResult? result;
    const PlaceSuggestion savedPlace = PlaceSuggestion(
      label: 'Casa',
      referenceAddress: 'Rua salva',
      coordinate: GeoCoordinate(latitude: -23.1175, longitude: -46.5502),
    );
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: Builder(
          builder: (BuildContext context) {
            return Scaffold(
              body: FilledButton(
                key: const Key('open-saved-review-test'),
                onPressed: () async {
                  result = await Navigator.of(context)
                      .push<LocationSelectionResult>(
                        MaterialPageRoute<LocationSelectionResult>(
                          builder: (_) => const ExactLocationScreen(
                            approximatePlace: savedPlace,
                            initialCoordinate: GeoCoordinate(
                              latitude: -23.1175,
                              longitude: -46.5502,
                            ),
                            initialInstructions: 'Portão antigo',
                            savedLocationId: 'saved-1',
                            requireManualMovement: false,
                          ),
                        ),
                      );
                },
                child: const Text('Abrir revisão'),
              ),
            );
          },
        ),
      ),
    );

    await tester.tap(find.byKey(const Key('open-saved-review-test')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField), 'Entregar na garagem');
    final Finder safeArea = find.byKey(const Key('safe-area-confirmation'));
    await tester.scrollUntilVisible(
      safeArea,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(safeArea);
    await tester.pump();
    final Finder confirm = find.byKey(const Key('confirm-exact-point'));
    await tester.scrollUntilVisible(
      confirm,
      250,
      scrollable: find.byType(Scrollable).first,
    );
    expect(tester.widget<AppButton>(confirm).onPressed, isNotNull);
    await tester.tap(confirm);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Confirmar este ponto'));
    await tester.pumpAndSettle();

    expect(result, isNotNull);
    expect(result!.instructions, 'Entregar na garagem');
    expect(result!.wasAdjusted, isTrue);
    expect(result!.savedLocationId, 'saved-1');
  });

  testWidgets('abre o mapa diretamente sem endereço nem GPS', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: const ApproximateLocationScreen(),
      ),
    );
    await tester.pump();

    await tester.tap(find.byKey(const Key('open-map-directly')));
    await tester.pumpAndSettle();

    expect(find.byType(ExactLocationScreen), findsOneWidget);
    final ExactLocationScreen exact = tester.widget<ExactLocationScreen>(
      find.byType(ExactLocationScreen),
    );
    expect(
      exact.approximatePlace!.referenceAddress,
      'Local sem endereço identificado',
    );
  });

  testWidgets('pagamento não possui campos bancários', (
    WidgetTester tester,
  ) async {
    controller.updateExactCoordinate(
      const GeoCoordinate(latitude: -23.1176, longitude: -46.5503),
    );
    controller.updateDeliveryDetails(instructions: '', safeArea: true);

    await tester.pumpWidget(
      _TestHost(controller: controller, child: const PaymentScreen()),
    );

    expect(find.text('Escolha a forma de pagamento'), findsOneWidget);
    expect(
      find.textContaining('sem solicitar dados bancários'),
      findsOneWidget,
    );
    expect(find.textContaining('Número do cartão'), findsNothing);
    expect(find.text('CVV'), findsNothing);
    expect(find.byType(TextFormField), findsNothing);
    expect(find.byKey(const Key('save-current-location-toggle')), findsNothing);
  });

  testWidgets('oferece salvar seleção manual confirmada', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    controller.applyLocationSelection(
      const LocationSelectionResult(
        approximatePlace: PlaceSuggestion(
          label: 'Campus',
          referenceAddress: 'Região aproximada',
          coordinate: GeoCoordinate(latitude: -23.1175, longitude: -46.5502),
        ),
        finalCoordinate: GeoCoordinate(latitude: -23.1176, longitude: -46.5503),
        instructions: '',
        safeAreaConfirmed: true,
        mapProvider: 'development_fallback',
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        wasAdjusted: true,
      ),
    );

    await tester.pumpWidget(
      _TestHost(controller: controller, child: const PaymentScreen()),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('save-current-location-toggle')));
    await tester.pump();
    expect(find.text('Nome da localização'), findsOneWidget);
  });

  testWidgets('não oferece salvar durante pedido quando limite é três', (
    WidgetTester tester,
  ) async {
    controller.applyLocationSelection(
      const LocationSelectionResult(
        approximatePlace: PlaceSuggestion(
          label: 'Campus',
          referenceAddress: 'Região aproximada',
          coordinate: GeoCoordinate(latitude: -23.1175, longitude: -46.5502),
        ),
        finalCoordinate: GeoCoordinate(latitude: -23.1176, longitude: -46.5503),
        instructions: '',
        safeAreaConfirmed: true,
        mapProvider: 'development_fallback',
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        wasAdjusted: true,
      ),
    );
    await controller.savedLocations.load();
    for (int index = 1; index <= 3; index++) {
      await controller.savedLocations.create(
        SavedLocationDraft(
          name: 'Local $index',
          coordinate: GeoCoordinate(
            latitude: -23 + index / 1000,
            longitude: -46,
          ),
          mapProvider: 'maptiler',
          mapType: 'hybrid',
          regionConfirmed: true,
          exactPointSelected: true,
          userConfirmed: true,
          userConfirmedSafeArea: true,
        ),
      );
    }

    await tester.pumpWidget(
      _TestHost(controller: controller, child: const PaymentScreen()),
    );

    expect(find.byKey(const Key('save-current-location-toggle')), findsNothing);
  });

  testWidgets('picker mostra somente salvos e abre revisão centralizada', (
    WidgetTester tester,
  ) async {
    _setViewport(tester);
    await controller.savedLocations.load();
    await controller.savedLocations.create(
      const SavedLocationDraft(
        name: 'Casa',
        coordinate: GeoCoordinate(latitude: -23.2, longitude: -46.2),
        mapProvider: 'maptiler',
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        userConfirmedSafeArea: true,
      ),
    );
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: const ApproximateLocationScreen(showSavedLocations: true),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Casa'), findsOneWidget);
    expect(find.text('Trabalho'), findsNothing);
    await tester.tap(find.text('Casa'));
    await tester.pumpAndSettle();

    final ExactLocationScreen exact = tester.widget<ExactLocationScreen>(
      find.byType(ExactLocationScreen),
    );
    expect(exact.initialCoordinate?.formatted, '-23.200000, -46.200000');
    expect(exact.savedLocationId, isNotNull);
    expect(exact.requireManualMovement, isFalse);

    final Finder safeArea = find.byKey(const Key('safe-area-confirmation'));
    await tester.scrollUntilVisible(
      safeArea,
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(safeArea);
    await tester.pump();
    final AppButton confirm = tester.widget<AppButton>(
      find.byKey(const Key('confirm-exact-point')),
    );
    expect(confirm.onPressed, isNotNull);
  });

  testWidgets('picker mantém dois atalhos lado a lado em 360 dp', (
    WidgetTester tester,
  ) async {
    _setViewport(tester, const Size(360, 1200));
    await controller.savedLocations.load();
    for (final String name in <String>['Casa', 'Trabalho']) {
      await controller.savedLocations.create(
        SavedLocationDraft(
          name: name,
          coordinate: const GeoCoordinate(latitude: -23.2, longitude: -46.2),
          mapProvider: 'maptiler',
          mapType: 'hybrid',
          regionConfirmed: true,
          exactPointSelected: true,
          userConfirmed: true,
          userConfirmedSafeArea: true,
        ),
      );
    }
    await tester.pumpWidget(
      _TestHost(
        controller: controller,
        child: const ApproximateLocationScreen(showSavedLocations: true),
      ),
    );
    await tester.pumpAndSettle();

    final Rect casa = tester.getRect(
      find.byKey(const Key('saved-location-picker-demo-saved-location-1')),
    );
    final Rect trabalho = tester.getRect(
      find.byKey(const Key('saved-location-picker-demo-saved-location-2')),
    );
    expect((casa.center.dy - trabalho.center.dy).abs(), lessThan(1));
    expect(casa.overlaps(trabalho), isFalse);
    expect(casa.width, greaterThan(100));
    expect(trabalho.width, greaterThan(100));
    expect(tester.takeException(), isNull);
  });
}

void _setViewport(WidgetTester tester, [Size size = const Size(600, 1400)]) {
  tester.view.devicePixelRatio = 1;
  tester.view.physicalSize = size;
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.resetPhysicalSize);
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
