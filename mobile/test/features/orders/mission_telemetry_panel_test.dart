import 'package:drone_delivery_mobile/core/models/mission_telemetry.dart';
import 'package:drone_delivery_mobile/features/orders/presentation/widgets/order_detail_components.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('exibe apenas valores recebidos e sinaliza telemetria vencida', (
    WidgetTester tester,
  ) async {
    final MissionTelemetrySnapshot telemetry =
        MissionTelemetrySnapshot.fromJson(<String, Object?>{
          'latitude': -23.11872,
          'longitude': -46.58131,
          'relative_altitude_m': 12.4,
          'battery_percent': 86,
          'satellites': 14,
          'flight_mode': 'ALT_HOLD',
          'armed': false,
          'source': 'HARDWARE_REAL',
          'recorded_at': '2026-08-17T10:00:00Z',
          'received_at': '2026-08-17T10:00:01Z',
          'is_stale': true,
        });
    final MissionStatusSnapshot mission = MissionStatusSnapshot.fromJson(
      <String, Object?>{'status': 'VERIFIED'},
    );

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: MissionTelemetryPanel(
              telemetry: telemetry,
              missionStatus: mission,
            ),
          ),
        ),
      ),
    );

    expect(find.text('Missão verificada'), findsOneWidget);
    expect(find.textContaining('não inicia o voo'), findsOneWidget);
    expect(find.text('Última telemetria vencida'), findsOneWidget);
    expect(find.text('-23.118720, -46.581310'), findsOneWidget);
    expect(find.text('12.4 m'), findsOneWidget);
    expect(find.text('86%'), findsOneWidget);
    expect(find.text('14'), findsOneWidget);
    expect(find.text('ALT_HOLD'), findsOneWidget);
    expect(find.text('Hardware real'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('telemetry-armed')),
        matching: find.text('Não'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('telemetry-stale')),
        matching: find.text('Sim'),
      ),
      findsOneWidget,
    );
  });

  testWidgets('campos não recebidos permanecem indisponíveis', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: MissionTelemetryPanel(telemetry: null, missionStatus: null),
          ),
        ),
      ),
    );

    expect(find.text('Telemetria indisponível'), findsOneWidget);
    expect(
      find.descendant(
        of: find.byKey(const Key('telemetry-position')),
        matching: find.text('Indisponível'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('telemetry-source')),
        matching: find.text('Indisponível'),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: find.byKey(const Key('telemetry-stale')),
        matching: find.text('Indisponível'),
      ),
      findsOneWidget,
    );
  });
}
