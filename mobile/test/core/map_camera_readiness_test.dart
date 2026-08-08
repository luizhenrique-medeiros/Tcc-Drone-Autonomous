import 'package:drone_delivery_mobile/core/maps/map_camera_readiness.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('só libera câmera após controller e estilo, em qualquer ordem', () {
    final MapCameraReadiness controllerFirst = MapCameraReadiness()
      ..markControllerCreated();
    expect(controllerFirst.beginCameraUpdate(), isFalse);
    controllerFirst.markStyleLoaded();
    expect(controllerFirst.beginCameraUpdate(), isTrue);
    expect(controllerFirst.beginCameraUpdate(), isFalse);
    controllerFirst.markCameraApplied();
    expect(controllerFirst.cameraApplied, isTrue);
    expect(controllerFirst.beginCameraUpdate(), isFalse);

    final MapCameraReadiness styleFirst = MapCameraReadiness()
      ..markStyleLoaded();
    expect(styleFirst.beginCameraUpdate(), isFalse);
    styleFirst.markControllerCreated();
    expect(styleFirst.beginCameraUpdate(), isTrue);
  });

  test('permite repetir aplicação depois de falha', () {
    final MapCameraReadiness readiness = MapCameraReadiness()
      ..markControllerCreated()
      ..markStyleLoaded();
    expect(readiness.beginCameraUpdate(), isTrue);
    readiness.markCameraUpdateFailed();
    expect(readiness.beginCameraUpdate(), isTrue);
  });
}
