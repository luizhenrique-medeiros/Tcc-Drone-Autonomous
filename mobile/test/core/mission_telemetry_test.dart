import 'package:drone_delivery_mobile/core/models/mission_telemetry.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('converte telemetria recebida sem inventar valores', () {
    final MissionTelemetrySnapshot telemetry =
        MissionTelemetrySnapshot.fromJson(<String, Object?>{
          'mission_id': 'mission-1',
          'vehicle_id': 'vehicle-1',
          'latitude': '-23.11872',
          'longitude': -46.58131,
          'relative_altitude_m': 12.4,
          'battery_percent': 86,
          'satellites': 14,
          'flight_mode': 'AUTO',
          'armed': true,
          'source': 'HARDWARE_REAL',
          'recorded_at': '2026-08-17T10:00:00Z',
          'received_at': '2026-08-17T10:00:01Z',
          'is_stale': false,
        });

    expect(telemetry.missionId, 'mission-1');
    expect(telemetry.latitude, -23.11872);
    expect(telemetry.longitude, -46.58131);
    expect(telemetry.relativeAltitudeM, 12.4);
    expect(telemetry.batteryPercent, 86);
    expect(telemetry.satellites, 14);
    expect(telemetry.flightMode, 'AUTO');
    expect(telemetry.armed, isTrue);
    expect(telemetry.source, TelemetrySource.hardwareReal);
    expect(telemetry.recordedAt, DateTime.utc(2026, 8, 17, 10));
    expect(telemetry.isStale, isFalse);
  });

  test('campos ausentes ou inválidos permanecem indisponíveis', () {
    final MissionTelemetrySnapshot telemetry =
        MissionTelemetrySnapshot.fromJson(<String, Object?>{
          'latitude': 120,
          'longitude': 'não numérico',
          'battery_percent': -1,
          'satellites': 101,
          'armed': 'false',
          'source': '',
          'is_stale': 'false',
        });

    expect(telemetry.latitude, isNull);
    expect(telemetry.longitude, isNull);
    expect(telemetry.relativeAltitudeM, isNull);
    expect(telemetry.batteryPercent, isNull);
    expect(telemetry.satellites, isNull);
    expect(telemetry.flightMode, isNull);
    expect(telemetry.armed, isNull);
    expect(telemetry.source, isNull);
    expect(telemetry.recordedAt, isNull);
    expect(telemetry.receivedAt, isNull);
    expect(telemetry.isStale, isNull);
  });

  test(
    'ordenação usa recorded_at e não deixa amostra antiga substituir nova',
    () {
      final MissionTelemetrySnapshot current =
          MissionTelemetrySnapshot.fromJson(<String, Object?>{
            'recorded_at': '2026-08-17T10:00:05Z',
          });
      final MissionTelemetrySnapshot older = MissionTelemetrySnapshot.fromJson(
        <String, Object?>{'recorded_at': '2026-08-17T10:00:04Z'},
      );

      expect(older.isOlderThan(current), isTrue);
      expect(current.isOlderThan(older), isFalse);
    },
  );

  test('VERIFIED é reconhecido como estado próprio de missão', () {
    final MissionStatusSnapshot mission =
        MissionStatusSnapshot.fromJson(<String, Object?>{
          'id': 'mission-1',
          'order_id': 'order-1',
          'status': 'VERIFIED',
          'updated_at': '2026-08-17T10:00:00Z',
        });

    expect(mission.status, MissionStatus.verified);
    expect(mission.status.title, 'Missão verificada');
    expect(mission.status.description, contains('não inicia o voo'));
  });

  test('PAUSED é reconhecido sem alterar artificialmente o pedido', () {
    final MissionStatusSnapshot mission = MissionStatusSnapshot.fromJson(
      <String, Object?>{'status': 'PAUSED'},
    );

    expect(mission.status, MissionStatus.paused);
    expect(mission.status.title, 'Missão pausada');
  });
}
