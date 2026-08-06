import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../core/maps/map_provider.dart';
import '../../../core/models/delivery_point.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_radii.dart';
import '../../../design_system/tokens/app_shadows.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';

class DevelopmentSatelliteMap extends StatefulWidget {
  const DevelopmentSatelliteMap({
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
  State<DevelopmentSatelliteMap> createState() =>
      _DevelopmentSatelliteMapState();
}

class _DevelopmentSatelliteMapState extends State<DevelopmentSatelliteMap> {
  Offset _normalized = Offset.zero;

  void _move(Offset localPosition, Size size) {
    final double dx = (localPosition.dx / size.width - 0.5).clamp(-0.46, 0.46);
    final double dy = (localPosition.dy / size.height - 0.5).clamp(-0.46, 0.46);
    setState(() => _normalized = Offset(dx, dy));
    widget.onCoordinateChanged(
      widget.provider.moveMarker(
        center: widget.center,
        normalizedDx: dx,
        normalizedDy: dy,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label:
          'Mapa em visão de satélite demonstrativa. Toque ou arraste o marcador para escolher o ponto exato.',
      child: ClipRRect(
        borderRadius: AppRadii.large,
        child: SizedBox(
          height: 360,
          child: LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final Size size = Size(
                constraints.maxWidth,
                constraints.maxHeight,
              );
              return GestureDetector(
                key: const Key('development-satellite-map'),
                onTapDown: widget.interactive
                    ? (TapDownDetails details) =>
                          _move(details.localPosition, size)
                    : null,
                onPanUpdate: widget.interactive
                    ? (DragUpdateDetails details) =>
                          _move(details.localPosition, size)
                    : null,
                child: Stack(
                  children: <Widget>[
                    const Positioned.fill(
                      child: CustomPaint(painter: _SatellitePreviewPainter()),
                    ),
                    Positioned(
                      top: AppSpacing.sm,
                      left: AppSpacing.sm,
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
                          'SATÉLITE · FALLBACK DEV',
                          style: AppTypography.caption.copyWith(
                            color: AppColors.surface,
                          ),
                        ),
                      ),
                    ),
                    Positioned(
                      left: (size.width * (0.5 + _normalized.dx)) - 24,
                      top: (size.height * (0.5 + _normalized.dy)) - 48,
                      child: const _DraggableMarker(),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}

class _DraggableMarker extends StatelessWidget {
  const _DraggableMarker();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(AppSpacing.xs),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        shape: BoxShape.circle,
        boxShadow: AppShadows.floating,
      ),
      child: const Icon(
        Icons.location_on,
        size: AppIconSizes.large,
        color: AppColors.accentOrange,
      ),
    );
  }
}

class _SatellitePreviewPainter extends CustomPainter {
  const _SatellitePreviewPainter();

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = AppColors.mapVegetation,
    );
    final Paint fieldPaint = Paint()..color = AppColors.mapField;
    canvas.drawRect(
      Rect.fromLTWH(0, 0, size.width * 0.42, size.height * 0.46),
      fieldPaint,
    );
    canvas.drawRect(
      Rect.fromLTWH(
        size.width * 0.58,
        size.height * 0.54,
        size.width * 0.42,
        size.height * 0.46,
      ),
      fieldPaint,
    );

    final Paint roadPaint = Paint()
      ..color = AppColors.mapRoad
      ..strokeWidth = 24
      ..strokeCap = StrokeCap.round;
    final Path road = Path()
      ..moveTo(-20, size.height * 0.78)
      ..quadraticBezierTo(
        size.width * 0.45,
        size.height * 0.44,
        size.width + 20,
        size.height * 0.18,
      );
    canvas.drawPath(road, roadPaint);
    canvas.drawLine(
      Offset(size.width * 0.58, -20),
      Offset(size.width * 0.42, size.height + 20),
      roadPaint..strokeWidth = 14,
    );

    final Paint buildingPaint = Paint()..color = AppColors.mapBuilding;
    for (int index = 0; index < 9; index++) {
      final double x = 24 + ((index * 73) % math.max(80, size.width - 70));
      final double y = 30 + ((index * 47) % math.max(90, size.height - 80));
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, y, 36, 22),
          const Radius.circular(3),
        ),
        buildingPaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}
