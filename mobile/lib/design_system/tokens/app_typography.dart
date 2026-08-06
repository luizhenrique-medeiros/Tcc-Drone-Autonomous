import 'package:flutter/material.dart';

import 'app_colors.dart';

abstract final class AppTypography {
  static const String? fontFamily = null;

  static const TextStyle display = TextStyle(
    fontSize: 32,
    height: 1.15,
    fontWeight: FontWeight.w800,
    color: AppColors.navy,
  );

  static const TextStyle headline = TextStyle(
    fontSize: 24,
    height: 1.2,
    fontWeight: FontWeight.w800,
    color: AppColors.navy,
  );

  static const TextStyle title = TextStyle(
    fontSize: 18,
    height: 1.25,
    fontWeight: FontWeight.w700,
    color: AppColors.navy,
  );

  static const TextStyle body = TextStyle(
    fontSize: 16,
    height: 1.45,
    fontWeight: FontWeight.w400,
    color: AppColors.slate,
  );

  static const TextStyle bodyStrong = TextStyle(
    fontSize: 16,
    height: 1.4,
    fontWeight: FontWeight.w700,
    color: AppColors.navy,
  );

  static const TextStyle label = TextStyle(
    fontSize: 14,
    height: 1.3,
    fontWeight: FontWeight.w600,
    color: AppColors.navy,
  );

  static const TextStyle caption = TextStyle(
    fontSize: 12,
    height: 1.35,
    fontWeight: FontWeight.w500,
    color: AppColors.slate,
  );
}
