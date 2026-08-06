import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/app/app_scope.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:drone_delivery_mobile/design_system/theme/app_theme.dart';
import 'package:drone_delivery_mobile/features/auth/presentation/login_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('login valida e-mail e tamanho mínimo da senha', (
    WidgetTester tester,
  ) async {
    final AppController controller = AppController(
      authRepository: DemoAuthRepository(),
      productRepository: DemoProductRepository(),
      checkoutRepository: const DemoCheckoutRepository(),
      mapProvider: const DevelopmentMapProvider(),
      locationService: const DevelopmentLocationService(),
      isDemoMode: true,
    );
    addTearDown(controller.dispose);
    await tester.pumpWidget(
      AppScope(
        controller: controller,
        child: MaterialApp(theme: AppTheme.light, home: const LoginScreen()),
      ),
    );

    await tester.enterText(
      find.descendant(
        of: find.byKey(const Key('login-email')),
        matching: find.byType(TextFormField),
      ),
      'email-invalido',
    );
    await tester.enterText(
      find.descendant(
        of: find.byKey(const Key('login-password')),
        matching: find.byType(TextFormField),
      ),
      '123',
    );
    final Finder submit = find.byKey(const Key('login-submit'));
    await tester.ensureVisible(submit);
    await tester.tap(submit);
    await tester.pumpAndSettle();

    expect(find.text('Informe um e-mail válido.'), findsOneWidget);
    expect(
      find.text('A senha deve ter ao menos 6 caracteres.'),
      findsOneWidget,
    );
    expect(controller.isAuthenticated, isFalse);
  });
}
