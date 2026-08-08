import 'dart:async';

import 'package:flutter/foundation.dart';
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
          'O mapa foi aberto na região inicial. Você pode navegar livremente ou pesquisar outra referência.',
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
    try {
      final bool serviceEnabled =
          await geolocator.Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        return const ApproximateLocationResult(
          coordinate: null,
          permissionState: LocationPermissionState.unavailable,
          message:
              'A localização do dispositivo está desativada. Pesquise uma região ou navegue manualmente.',
        );
      }

      geolocator.LocationPermission permission =
          await geolocator.Geolocator.checkPermission();
      if (permission == geolocator.LocationPermission.denied) {
        permission = await geolocator.Geolocator.requestPermission();
      }
      if (permission == geolocator.LocationPermission.deniedForever) {
        return const ApproximateLocationResult(
          coordinate: null,
          permissionState: LocationPermissionState.denied,
          message:
              'A localização está bloqueada nas configurações. A pesquisa e a navegação manual continuam disponíveis.',
        );
      }
      if (permission == geolocator.LocationPermission.denied) {
        return const ApproximateLocationResult(
          coordinate: null,
          permissionState: LocationPermissionState.denied,
          message:
              'Permissão negada. Você ainda pode pesquisar qualquer endereço ou navegar manualmente.',
        );
      }

      final geolocator.Position position =
          await geolocator.Geolocator.getCurrentPosition(
            locationSettings: geolocator.LocationSettings(
              accuracy: geolocator.LocationAccuracy.medium,
              timeLimit: timeout,
            ),
          );
      final bool precise;
      if (kIsWeb) {
        // Browsers do not expose Android/iOS's precise-versus-approximate
        // permission status through geolocator_web.
        precise = false;
      } else {
        final geolocator.LocationAccuracyStatus accuracy =
            await geolocator.Geolocator.getLocationAccuracy();
        precise = accuracy == geolocator.LocationAccuracyStatus.precise;
      }
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
    } on geolocator.PermissionDeniedException {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.denied,
        message:
            'O navegador ou sistema recusou a localização. A pesquisa e a navegação manual continuam disponíveis.',
      );
    } on UnsupportedError {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.unavailable,
        message:
            'Este navegador não oferece geolocalização. Pesquise uma região ou navegue manualmente.',
      );
    } on Exception {
      return const ApproximateLocationResult(
        coordinate: null,
        permissionState: LocationPermissionState.unavailable,
        message:
            'A localização está indisponível neste momento. A pesquisa e a navegação manual continuam disponíveis.',
      );
    }
  }
}
