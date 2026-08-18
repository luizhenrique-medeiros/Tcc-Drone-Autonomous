enum MissionStatus {
  draft,
  pendingValidation,
  generated,
  exportedToMissionPlanner,
  underReview,
  readyForAuthorization,
  authorized,
  uploading,
  uploaded,
  verified,
  executing,
  paused,
  destinationReached,
  deliveryConfirmed,
  returning,
  completed,
  aborted,
  failed,
  unknown,
}

extension MissionStatusX on MissionStatus {
  String get apiValue => switch (this) {
    MissionStatus.draft => 'DRAFT',
    MissionStatus.pendingValidation => 'PENDING_VALIDATION',
    MissionStatus.generated => 'GENERATED',
    MissionStatus.exportedToMissionPlanner => 'EXPORTED_TO_MISSION_PLANNER',
    MissionStatus.underReview => 'UNDER_REVIEW',
    MissionStatus.readyForAuthorization => 'READY_FOR_AUTHORIZATION',
    MissionStatus.authorized => 'AUTHORIZED',
    MissionStatus.uploading => 'UPLOADING',
    MissionStatus.uploaded => 'UPLOADED',
    MissionStatus.verified => 'VERIFIED',
    MissionStatus.executing => 'EXECUTING',
    MissionStatus.paused => 'PAUSED',
    MissionStatus.destinationReached => 'DESTINATION_REACHED',
    MissionStatus.deliveryConfirmed => 'DELIVERY_CONFIRMED',
    MissionStatus.returning => 'RETURNING',
    MissionStatus.completed => 'COMPLETED',
    MissionStatus.aborted => 'ABORTED',
    MissionStatus.failed => 'FAILED',
    MissionStatus.unknown => 'UNKNOWN',
  };

  String get title => switch (this) {
    MissionStatus.draft => 'Missão em rascunho',
    MissionStatus.pendingValidation => 'Missão em validação',
    MissionStatus.generated => 'Missão gerada',
    MissionStatus.exportedToMissionPlanner => 'Exportada para revisão',
    MissionStatus.underReview => 'Missão em revisão',
    MissionStatus.readyForAuthorization => 'Pronta para autorização',
    MissionStatus.authorized => 'Voo autorizado',
    MissionStatus.uploading => 'Upload em andamento',
    MissionStatus.uploaded => 'Upload concluído',
    MissionStatus.verified => 'Missão verificada',
    MissionStatus.executing => 'Missão em execução',
    MissionStatus.paused => 'Missão pausada',
    MissionStatus.destinationReached => 'Destino alcançado',
    MissionStatus.deliveryConfirmed => 'Etapa de entrega registrada',
    MissionStatus.returning => 'Retorno em andamento',
    MissionStatus.completed => 'Missão concluída',
    MissionStatus.aborted => 'Missão interrompida',
    MissionStatus.failed => 'Falha na missão',
    MissionStatus.unknown => 'Estado de missão incompatível',
  };

  String get description => switch (this) {
    MissionStatus.verified =>
      'O conteúdo enviado foi relido e conferido; esta etapa não inicia o voo.',
    MissionStatus.paused =>
      'O ArduPilot confirmou a pausa; o veículo permanece sob supervisão do operador.',
    MissionStatus.unknown =>
      'O backend enviou um estado de missão que esta versão não reconhece.',
    _ => 'Estado informado pelo backend para a missão deste pedido.',
  };

  static MissionStatus fromApi(Object? value) {
    final String normalized = value?.toString().trim().toUpperCase() ?? '';
    for (final MissionStatus status in MissionStatus.values) {
      if (status.apiValue == normalized) return status;
    }
    return MissionStatus.unknown;
  }
}

class MissionStatusSnapshot {
  const MissionStatusSnapshot({
    required this.status,
    this.id,
    this.orderId,
    this.updatedAt,
  });

  final String? id;
  final String? orderId;
  final MissionStatus status;
  final DateTime? updatedAt;

  factory MissionStatusSnapshot.fromJson(Map<String, Object?> json) {
    return MissionStatusSnapshot(
      id: _cleanText(json['id'] ?? json['mission_id']),
      orderId: _cleanText(json['order_id']),
      status: MissionStatusX.fromApi(json['status']),
      updatedAt: _toDateTime(json['updated_at']),
    );
  }
}

enum TelemetrySource { simulation, sitl, hardwareReal, unknown }

extension TelemetrySourceX on TelemetrySource {
  String get apiValue => switch (this) {
    TelemetrySource.simulation => 'SIMULATION',
    TelemetrySource.sitl => 'SITL',
    TelemetrySource.hardwareReal => 'HARDWARE_REAL',
    TelemetrySource.unknown => 'UNKNOWN',
  };

  String get label => switch (this) {
    TelemetrySource.simulation => 'Simulação',
    TelemetrySource.sitl => 'ArduPilot SITL',
    TelemetrySource.hardwareReal => 'Hardware real',
    TelemetrySource.unknown => 'Origem desconhecida',
  };

  static TelemetrySource? fromApi(Object? value) {
    final String normalized = value?.toString().trim().toUpperCase() ?? '';
    if (normalized.isEmpty) return null;
    for (final TelemetrySource source in TelemetrySource.values) {
      if (source.apiValue == normalized) return source;
    }
    return TelemetrySource.unknown;
  }
}

class MissionTelemetrySnapshot {
  const MissionTelemetrySnapshot({
    this.missionId,
    this.vehicleId,
    this.latitude,
    this.longitude,
    this.relativeAltitudeM,
    this.batteryPercent,
    this.satellites,
    this.flightMode,
    this.armed,
    this.source,
    this.recordedAt,
    this.receivedAt,
    this.isStale,
  });

  final String? missionId;
  final String? vehicleId;
  final double? latitude;
  final double? longitude;
  final double? relativeAltitudeM;
  final double? batteryPercent;
  final int? satellites;
  final String? flightMode;
  final bool? armed;
  final TelemetrySource? source;
  final DateTime? recordedAt;
  final DateTime? receivedAt;
  final bool? isStale;

  DateTime? get orderingTimestamp => recordedAt ?? receivedAt;

  bool isOlderThan(MissionTelemetrySnapshot current) {
    final DateTime? incomingTimestamp = orderingTimestamp;
    final DateTime? currentTimestamp = current.orderingTimestamp;
    if (incomingTimestamp == null) return currentTimestamp != null;
    if (currentTimestamp == null) return false;
    return incomingTimestamp.isBefore(currentTimestamp);
  }

  factory MissionTelemetrySnapshot.fromJson(Map<String, Object?> json) {
    return MissionTelemetrySnapshot(
      missionId: _cleanText(json['mission_id']),
      vehicleId: _cleanText(json['vehicle_id']),
      latitude: _boundedDouble(json['latitude'], minimum: -90, maximum: 90),
      longitude: _boundedDouble(json['longitude'], minimum: -180, maximum: 180),
      relativeAltitudeM: _nullableDouble(json['relative_altitude_m']),
      batteryPercent: _boundedDouble(
        json['battery_percent'],
        minimum: 0,
        maximum: 100,
      ),
      satellites: _boundedInt(json['satellites'], minimum: 0, maximum: 100),
      flightMode: _cleanText(json['flight_mode']),
      armed: json['armed'] is bool ? json['armed'] as bool : null,
      source: TelemetrySourceX.fromApi(json['source']),
      recordedAt: _toDateTime(json['recorded_at']),
      receivedAt: _toDateTime(json['received_at']),
      isStale: json['is_stale'] is bool ? json['is_stale'] as bool : null,
    );
  }
}

double? _nullableDouble(Object? value) {
  if (value == null) return null;
  final double? parsed = value is num
      ? value.toDouble()
      : double.tryParse(value.toString());
  return parsed?.isFinite == true ? parsed : null;
}

double? _boundedDouble(
  Object? value, {
  required double minimum,
  required double maximum,
}) {
  final double? parsed = _nullableDouble(value);
  if (parsed == null || parsed < minimum || parsed > maximum) return null;
  return parsed;
}

int? _boundedInt(Object? value, {required int minimum, required int maximum}) {
  final int? parsed = value is int
      ? value
      : value is num
      ? value.toInt()
      : int.tryParse(value?.toString() ?? '');
  if (parsed == null || parsed < minimum || parsed > maximum) return null;
  return parsed;
}

DateTime? _toDateTime(Object? value) {
  if (value == null) return null;
  return DateTime.tryParse(value.toString());
}

String? _cleanText(Object? value) {
  final String text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}
