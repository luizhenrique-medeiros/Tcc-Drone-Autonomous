import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/app/app_scope.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
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
    expect(controller.approximatePlace, isNotNull);
    expect(
      controller.approximatePlace!.referenceAddress,
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
  });
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
