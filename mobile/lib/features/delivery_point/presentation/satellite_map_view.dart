import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../../../core/maps/map_provider.dart';
import '../../../core/models/delivery_point.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_radii.dart';
import 'development_satellite_map.dart';

class SatelliteMapView extends StatelessWidget {
  const SatelliteMapView({
    required this.center,
    required this.provider,
    required this.onCoordinateChanged,
    this.interactive = true,
    super.key,
  });

  final GeoCoordinate center;
  final MapProvider provider;
  final ValueChanged<GeoCoordinate> onCoordinateChanged;
  final bool interactive;

  @override
  Widget build(BuildContext context) {
    if (provider is GoogleMapsProvider) {
      return _GoogleSatelliteMap(
        center: center,
        onCoordinateChanged: onCoordinateChanged,
        interactive: interactive,
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

class _GoogleSatelliteMap extends StatefulWidget {
  const _GoogleSatelliteMap({
    required this.center,
    required this.onCoordinateChanged,
    required this.interactive,
  });

  final GeoCoordinate center;
  final ValueChanged<GeoCoordinate> onCoordinateChanged;
  final bool interactive;

  @override
  State<_GoogleSatelliteMap> createState() => _GoogleSatelliteMapState();
}

class _GoogleSatelliteMapState extends State<_GoogleSatelliteMap> {
  late LatLng _marker = LatLng(widget.center.latitude, widget.center.longitude);

  void _select(LatLng value) {
    if (!widget.interactive) return;
    setState(() => _marker = value);
    widget.onCoordinateChanged(
      GeoCoordinate(latitude: value.latitude, longitude: value.longitude),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label:
          'Google Maps em visão de satélite. Arraste o marcador para escolher o ponto exato.',
      child: ClipRRect(
        borderRadius: AppRadii.large,
        child: SizedBox(
          height: widget.interactive ? 360 : 220,
          child: GoogleMap(
            key: const Key('google-satellite-map'),
            mapType: MapType.satellite,
            initialCameraPosition: CameraPosition(target: _marker, zoom: 19),
            onTap: widget.interactive ? _select : null,
            markers: <Marker>{
              Marker(
                markerId: const MarkerId('delivery-point'),
                position: _marker,
                draggable: widget.interactive,
                onDragEnd: _select,
                infoWindow: const InfoWindow(title: 'Ponto exato da entrega'),
              ),
            },
            circles: <Circle>{
              Circle(
                circleId: const CircleId('delivery-accuracy'),
                center: _marker,
                radius: 8,
                fillColor: AppColors.brandBlue.withValues(alpha: 0.16),
                strokeColor: AppColors.brandBlue,
                strokeWidth: 2,
              ),
            },
            compassEnabled: true,
            mapToolbarEnabled: false,
            myLocationButtonEnabled: false,
            zoomControlsEnabled: widget.interactive,
            scrollGesturesEnabled: widget.interactive,
            zoomGesturesEnabled: widget.interactive,
            rotateGesturesEnabled: widget.interactive,
            tiltGesturesEnabled: widget.interactive,
          ),
        ),
      ),
    );
  }
}
