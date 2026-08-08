/// Coordinates the two independent MapLibre callbacks required before the
/// initial camera can be applied safely.
class MapCameraReadiness {
  bool _controllerCreated = false;
  bool _styleLoaded = false;
  bool _cameraUpdateStarted = false;
  bool _cameraApplied = false;

  bool get cameraApplied => _cameraApplied;

  void markControllerCreated() => _controllerCreated = true;

  void markStyleLoaded() => _styleLoaded = true;

  bool beginCameraUpdate() {
    if (!_controllerCreated ||
        !_styleLoaded ||
        _cameraUpdateStarted ||
        _cameraApplied) {
      return false;
    }
    _cameraUpdateStarted = true;
    return true;
  }

  void markCameraApplied() {
    _cameraApplied = true;
    _cameraUpdateStarted = false;
  }

  void markCameraUpdateFailed() => _cameraUpdateStarted = false;
}
