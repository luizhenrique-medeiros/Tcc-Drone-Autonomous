import 'package:drone_delivery_mobile/design_system/components/runtime_profile_banner.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('perfil demo fica visível e nega uso de hardware real', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: RuntimeProfileBanner(
          isDemoMode: true,
          profile: 'demo',
          child: Scaffold(body: Text('Conteúdo')),
        ),
      ),
    );

    expect(find.byKey(const Key('runtime-demo-banner')), findsOneWidget);
    expect(
      find.text('PERFIL DEMO • dados simulados • sem hardware real'),
      findsOneWidget,
    );
    expect(find.text('Conteúdo'), findsOneWidget);
  });

  testWidgets('perfil integrado não recebe rótulo de demonstração', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: RuntimeProfileBanner(
          isDemoMode: false,
          profile: 'local_web',
          child: Scaffold(body: Text('Integrado')),
        ),
      ),
    );

    expect(find.byKey(const Key('runtime-demo-banner')), findsNothing);
    expect(find.textContaining('dados simulados'), findsNothing);
    expect(find.text('Integrado'), findsOneWidget);
  });
}
