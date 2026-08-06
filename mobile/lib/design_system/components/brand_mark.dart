import 'package:flutter/material.dart';

/// Pixel-preserving crop of the logo supplied in the login reference.
///
/// The source screenshot is never used as a screen or background. Only the
/// exact logo rectangle is exposed here; the remainder of every screen is
/// composed from Flutter widgets.
class BrandMark extends StatelessWidget {
  const BrandMark({this.compact = false, super.key});

  final bool compact;

  static const String _sourceAsset = 'assets/images/devcore-logo-source.png';
  static const double _sourceWidth = 1024;
  static const double _sourceHeight = 1536;
  static const Rect _logoCrop = Rect.fromLTWH(250, 190, 524, 350);

  @override
  Widget build(BuildContext context) {
    final double width = compact ? 78 : 262;
    final double scale = width / _logoCrop.width;
    final double height = _logoCrop.height * scale;
    return Semantics(
      label: 'DEVcore Entregas por Drone',
      image: true,
      child: SizedBox(
        width: width,
        height: height,
        child: ClipRect(
          child: Stack(
            clipBehavior: Clip.hardEdge,
            children: <Widget>[
              Positioned(
                left: -_logoCrop.left * scale,
                top: -_logoCrop.top * scale,
                width: _sourceWidth * scale,
                height: _sourceHeight * scale,
                child: Image.asset(
                  _sourceAsset,
                  fit: BoxFit.fill,
                  filterQuality: FilterQuality.high,
                  excludeFromSemantics: true,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
