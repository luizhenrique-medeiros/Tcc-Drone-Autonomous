import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import 'package:maplibre_gl/maplibre_gl.dart';
import 'package:url_launcher/link.dart';

import '../../../core/config/app_config.dart';
import '../../../core/maps/map_camera_readiness.dart';
import '../../../core/maps/map_provider.dart';
import '../../../core/models/delivery_point.dart';
import '../../../design_system/tokens/app_breakpoints.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_radii.dart';
import '../../../design_system/tokens/app_shadows.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import 'development_satellite_map.dart';

class SatelliteMapView extends StatelessWidget {
  const SatelliteMapView({
    required this.center,
    required this.provider,
    required this.onCoordinateChanged,
    this.interactive = true,
    this.onMapReady,
    this.onMapError,
    super.key,
  });

  final GeoCoordinate center;
  final MapProvider provider;
  final ValueChanged<GeoCoordinate> onCoordinateChanged;
  final bool interactive;
  final VoidCallback? onMapReady;
  final ValueChanged<String>? onMapError;

  @override
  Widget build(BuildContext context) {
    if (provider is MapTilerMapProvider) {
      return _MapTilerSatelliteMap(
        center: center,
        onCoordinateChanged: onCoordinateChanged,
        interactive: interactive,
        onMapReady: onMapReady,
        onMapError: onMapError,
      );
    }
    return DevelopmentSatelliteMap(
      center: center,
      provider: provider,
      onCoordinateChanged: onCoordinateChanged,
      interactive: interactive,
    );
  }
}

class _MapTilerSatelliteMap extends StatefulWidget {
  const _MapTilerSatelliteMap({
    required this.center,
    required this.onCoordinateChanged,
    required this.interactive,
    required this.onMapReady,
    required this.onMapError,
  });

  final GeoCoordinate center;
  final ValueChanged<GeoCoordinate> onCoordinateChanged;
  final bool interactive;
  final VoidCallback? onMapReady;
  final ValueChanged<String>? onMapError;

  @override
  State<_MapTilerSatelliteMap> createState() => _MapTilerSatelliteMapState();
}

class _MapTilerSatelliteMapState extends State<_MapTilerSatelliteMap> {
  static const Duration _styleLoadTimeout = Duration(seconds: 20);
  static const double _coordinateTolerance = 0.0000001;

  late LatLng _cameraTarget = LatLng(
    widget.center.latitude,
    widget.center.longitude,
  );
  LatLng? _lastReportedTarget;
  Timer? _styleLoadTimer;
  final MapCameraReadiness _cameraReadiness = MapCameraReadiness();
  MapLibreMapController? _mapController;
  bool _styleReady = false;
  bool _failureReported = false;

  @override
  void initState() {
    super.initState();
    _styleLoadTimer = Timer(_styleLoadTimeout, _reportStyleLoadTimeout);
  }

  @override
  void dispose() {
    _styleLoadTimer?.cancel();
    super.dispose();
  }

  void _onMapCreated(MapLibreMapController controller) {
    _mapController = controller;
    _cameraReadiness.markControllerCreated();
    unawaited(_applyInitialCameraAfterStyle());
  }

  void _onStyleLoaded() {
    _cameraReadiness.markStyleLoaded();
    unawaited(_applyInitialCameraAfterStyle());
  }

  Future<void> _applyInitialCameraAfterStyle() async {
    final MapLibreMapController? controller = _mapController;
    if (controller == null || !_cameraReadiness.beginCameraUpdate()) return;
    try {
      await controller.moveCamera(
        CameraUpdate.newCameraPosition(
          CameraPosition(
            target: LatLng(widget.center.latitude, widget.center.longitude),
            zoom: widget.interactive ? 18 : 19,
          ),
        ),
      );
      _cameraReadiness.markCameraApplied();
      if (!mounted || _styleReady) return;
      _styleReady = true;
      _cameraTarget = LatLng(widget.center.latitude, widget.center.longitude);
      _styleLoadTimer?.cancel();
      widget.onMapReady?.call();
    } on Object {
      _cameraReadiness.markCameraUpdateFailed();
      _reportFailure(
        'O estilo MapTiler carregou, mas a câmera não pôde ser centralizada. '
        'Tente novamente e verifique a compatibilidade do navegador.',
      );
    }
  }

  void _reportStyleLoadTimeout() {
    if (_styleReady || _failureReported) return;
    _reportFailure(
      'O estilo híbrido do MapTiler não carregou em 20 segundos. Verifique '
      'a chave da plataforma, MAPTILER_STYLE_URL, restrições, cota e rede.',
    );
  }

  void _reportFailure(String message) {
    if (!mounted || _styleReady || _failureReported) return;
    _failureReported = true;
    widget.onMapError?.call(message);
  }

  bool _sameTarget(LatLng first, LatLng second) {
    return (first.latitude - second.latitude).abs() < _coordinateTolerance &&
        (first.longitude - second.longitude).abs() < _coordinateTolerance;
  }

  void _onCameraIdle() {
    if (!widget.interactive || !_styleReady) return;
    final LatLng initial = LatLng(
      widget.center.latitude,
      widget.center.longitude,
    );
    if (_sameTarget(_cameraTarget, initial) ||
        (_lastReportedTarget != null &&
            _sameTarget(_cameraTarget, _lastReportedTarget!))) {
      return;
    }
    _lastReportedTarget = _cameraTarget;
    widget.onCoordinateChanged(
      GeoCoordinate(
        latitude: _cameraTarget.latitude,
        longitude: _cameraTarget.longitude,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final double availableWidth = MediaQuery.sizeOf(context).width;
    final double mapHeight = widget.interactive
        ? availableWidth >= AppBreakpoints.expanded
              ? 520
              : 430
        : 240;
    return Semantics(
      label:
          'Mapa híbrido MapTiler. Mova o mapa sob o pino central para escolher o ponto exato.',
      child: ClipRRect(
        borderRadius: AppRadii.large,
        child: SizedBox(
          height: mapHeight,
          child: Stack(
            alignment: Alignment.center,
            children: <Widget>[
              Positioned.fill(
                child: MapLibreMap(
                  key: const Key('maptiler-hybrid-map'),
                  styleString: AppConfig.mapTilerStyleUrlWithKey,
                  initialCameraPosition: CameraPosition(
                    target: _cameraTarget,
                    zoom: widget.interactive ? 18 : 19,
                  ),
                  onMapCreated: _onMapCreated,
                  onStyleLoadedCallback: _onStyleLoaded,
                  onCameraMove: (CameraPosition position) {
                    _cameraTarget = position.target;
                  },
                  onCameraIdle: _onCameraIdle,
                  trackCameraPosition: true,
                  compassEnabled: true,
                  myLocationEnabled: false,
                  dragEnabled: widget.interactive,
                  scrollGesturesEnabled: widget.interactive,
                  zoomGesturesEnabled: widget.interactive,
                  doubleClickZoomEnabled: widget.interactive,
                  rotateGesturesEnabled: widget.interactive,
                  tiltGesturesEnabled: widget.interactive,
                  logoEnabled: false,
                  foregroundLoadColor: AppColors.surfaceMuted,
                ),
              ),
              IgnorePointer(
                child: Transform.translate(
                  offset: const Offset(0, -22),
                  child: Container(
                    padding: const EdgeInsets.all(AppSpacing.xs),
                    decoration: const BoxDecoration(
                      color: AppColors.surface,
                      shape: BoxShape.circle,
                      boxShadow: AppShadows.floating,
                    ),
                    child: const Icon(
                      Icons.location_on,
                      size: 42,
                      color: AppColors.accentOrange,
                    ),
                  ),
                ),
              ),
              Positioned(
                top: AppSpacing.sm,
                left: AppSpacing.sm,
                child: IgnorePointer(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: AppSpacing.xs,
                    ),
                    decoration: const BoxDecoration(
                      color: AppColors.overlay,
                      borderRadius: AppRadii.pill,
                    ),
                    child: Text(
                      'HÍBRIDO',
                      style: AppTypography.caption.copyWith(
                        color: AppColors.surface,
                      ),
                    ),
                  ),
                ),
              ),
              const Positioned(
                left: 6,
                right: 6,
                bottom: 6,
                child: _MapTilerAttribution(),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MapTilerAttribution extends StatelessWidget {
  const _MapTilerAttribution();

  static final Uri _mapTilerHome = Uri.parse('https://www.maptiler.com/');
  static final Uri _mapTilerCopyright = Uri.parse(
    'https://www.maptiler.com/copyright/',
  );
  static final Uri _openStreetMapCopyright = Uri.parse(
    'https://www.openstreetmap.org/copyright',
  );

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        Link(
          uri: _mapTilerHome,
          target: LinkTarget.blank,
          builder: (BuildContext context, FollowLink? followLink) {
            return Semantics(
              label: 'Abrir site do MapTiler',
              link: true,
              child: InkWell(
                onTap: followLink,
                borderRadius: AppRadii.small,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 6,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: Colors.black.withValues(alpha: 0.78),
                    borderRadius: AppRadii.small,
                  ),
                  child: SvgPicture.network(
                    'https://api.maptiler.com/resources/logo.svg',
                    width: 67,
                    height: 20,
                    placeholderBuilder: (_) => const SizedBox(
                      width: 67,
                      height: 20,
                      child: Center(
                        child: Text(
                          'MapTiler',
                          style: TextStyle(color: Colors.white, fontSize: 11),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
        const Spacer(),
        Flexible(
          flex: 3,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.88),
              borderRadius: AppRadii.small,
            ),
            child: Wrap(
              alignment: WrapAlignment.end,
              spacing: 4,
              children: <Widget>[
                _AttributionLink(uri: _mapTilerCopyright, label: '© MapTiler'),
                _AttributionLink(
                  uri: _openStreetMapCopyright,
                  label: '© OpenStreetMap contributors',
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

class _AttributionLink extends StatelessWidget {
  const _AttributionLink({required this.uri, required this.label});

  final Uri uri;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Link(
      uri: uri,
      target: LinkTarget.blank,
      builder: (BuildContext context, FollowLink? followLink) {
        return InkWell(
          onTap: followLink,
          child: Text(
            label,
            style: const TextStyle(
              color: Colors.black87,
              fontSize: 9,
              decoration: TextDecoration.underline,
            ),
          ),
        );
      },
    );
  }
}
