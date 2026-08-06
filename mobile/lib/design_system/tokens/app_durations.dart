import 'package:flutter/animation.dart';

abstract final class AppDurations {
  static const Duration fast = Duration(milliseconds: 150);
  static const Duration normal = Duration(milliseconds: 280);
  static const Duration slow = Duration(milliseconds: 500);
  static const Duration splash = Duration(milliseconds: 900);
  static const Duration demoStatus = Duration(seconds: 3);

  static const Curve standardCurve = Curves.easeOutCubic;
}
