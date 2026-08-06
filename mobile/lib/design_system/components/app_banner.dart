import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_radii.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

enum AppBannerTone { info, warning, success, danger }

class AppBanner extends StatelessWidget {
  const AppBanner({
    required this.title,
    required this.message,
    this.tone = AppBannerTone.info,
    super.key,
  });

  final String title;
  final String message;
  final AppBannerTone tone;

  @override
  Widget build(BuildContext context) {
    final (Color background, Color foreground, IconData icon) = switch (tone) {
      AppBannerTone.info => (
        AppColors.brandBlueSoft,
        AppColors.brandBlueDark,
        Icons.info_outline,
      ),
      AppBannerTone.warning => (
        AppColors.warningSoft,
        const Color(0xFF8A5A00),
        Icons.warning_amber_rounded,
      ),
      AppBannerTone.success => (
        AppColors.successSoft,
        AppColors.success,
        Icons.check_circle_outline,
      ),
      AppBannerTone.danger => (
        AppColors.dangerSoft,
        AppColors.danger,
        Icons.error_outline,
      ),
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(AppSpacing.md),
      decoration: BoxDecoration(
        color: background,
        borderRadius: AppRadii.medium,
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Icon(icon, size: AppIconSizes.medium, color: foreground),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  title,
                  style: AppTypography.label.copyWith(color: foreground),
                ),
                const SizedBox(height: AppSpacing.xxs),
                Text(
                  message,
                  style: AppTypography.caption.copyWith(color: foreground),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
