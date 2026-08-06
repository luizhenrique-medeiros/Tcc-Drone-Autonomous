import 'dart:async';

import 'package:geolocator/geolocator.dart' as geolocator;

import '../models/delivery_point.dart';

enum LocationPermissionState { approximate, precise, denied, unavailable }

class ApproximateLocationResult {
  const ApproximateLocationResult({
    required this.coordinate,
    required this.permissionState,
    required this.message,
  });

  final GeoCoordinate? coordinate;
  final LocationPermissionState permissionState;
  final String message;
}

abstract interface class LocationService {
  Future<ApproximateLocationResult> requestApproximateLocation();
}

abstract interface class DeviceLocationBridge {
  Future<ApproximateLocationResult> requestApproximateLocation();
}

class PlatformLocationService implements LocationService {
  PlatformLocationService(this._bridge);

  final DeviceLocationBridge _bridge;

  @override
  Future<ApproximateLocationResult> requestApproximateLocation() {
    return _bridge.requestApproximateLocation();
  }
}

class DevelopmentLocationService implements LocationService {
  const DevelopmentLocationService();

  @override
  Future<ApproximateLocationResult> requestApproximateLocation() async {
    return const ApproximateLocationResult(
      coordinate: GeoCoordinate(latitude: -23.117500, longitude: -46.550200),
      permissionState: LocationPermissionState.unavailable,
      message:
          'GPS não é acessado no fallback. Foi usada apenas uma região acadêmica demonstrativa.',
    );
  }
}

class GeolocatorDeviceLocationBridge implements DeviceLocationBridge {
  const GeolocatorDeviceLocationBridge({
    this.timeout = const Duration(seconds: 10),
  });

  final Duration timeout;

  @override
  Future<ApproximateLocationResult> requestApproximateLocation() async {
    final bool serviceEnabled =
        await geolocator.Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.unavailable,
        message:
            'A localização do dispositivo está desativada. Pesquise uma região para continuar.',
      );
    }

    geolocator.LocationPermission permission =
        await geolocator.Geolocator.checkPermission();
    if (permission == geolocator.LocationPermission.denied) {
      permission = await geolocator.Geolocator.requestPermission();
    }
    if (permission == geolocator.LocationPermission.denied ||
        permission == geolocator.LocationPermission.deniedForever) {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.denied,
        message:
            'Permissão negada. Você ainda pode pesquisar qualquer endereço manualmente.',
      );
    }

    try {
      final geolocator.Position position =
          await geolocator.Geolocator.getCurrentPosition(
            locationSettings: geolocator.LocationSettings(
              accuracy: geolocator.LocationAccuracy.medium,
              timeLimit: timeout,
            ),
          );
      final geolocator.LocationAccuracyStatus accuracy =
          await geolocator.Geolocator.getLocationAccuracy();
      final bool precise =
          accuracy == geolocator.LocationAccuracyStatus.precise;
      return ApproximateLocationResult(
        coordinate: GeoCoordinate(
          latitude: position.latitude,
          longitude: position.longitude,
        ),
        permissionState: precise
            ? LocationPermissionState.precise
            : LocationPermissionState.approximate,
        message:
            'A posição do aparelho é apenas aproximada. Ajuste o marcador manualmente na etapa 2.',
      );
    } on TimeoutException {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.unavailable,
        message:
            'O GPS não respondeu a tempo. Pesquise uma região ou tente novamente.',
      );
    } on geolocator.LocationServiceDisabledException {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.unavailable,
        message:
            'A localização foi desativada. A pesquisa manual continua disponível.',
      );
    }
  }
}
