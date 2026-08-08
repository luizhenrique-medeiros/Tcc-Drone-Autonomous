import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_durations.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_radii.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

enum AppButtonVariant { primary, accent, secondary, text }

class AppButton extends StatelessWidget {
  const AppButton({
    required this.label,
    required this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.icon,
    this.loading = false,
    this.expand = true,
    super.key,
  });

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final IconData? icon;
  final bool loading;
  final bool expand;

  @override
  Widget build(BuildContext context) {
    final Color background = switch (variant) {
      AppButtonVariant.primary => AppColors.brandBlue,
      AppButtonVariant.accent => AppColors.accentOrange,
      AppButtonVariant.secondary => AppColors.brandBlueSoft,
      AppButtonVariant.text => Colors.transparent,
    };
    final Color foreground = switch (variant) {
      AppButtonVariant.primary || AppButtonVariant.accent => AppColors.surface,
      AppButtonVariant.secondary => AppColors.brandBlueDark,
      AppButtonVariant.text => AppColors.brandBlue,
    };
    final Widget content = AnimatedSwitcher(
      duration: AppDurations.fast,
      child: loading
          ? SizedBox(
              key: const ValueKey<String>('loading'),
              width: AppIconSizes.medium,
              height: AppIconSizes.medium,
              child: CircularProgressIndicator(
                strokeWidth: 2.5,
                color: foreground,
              ),
            )
          : Row(
              key: const ValueKey<String>('label'),
              mainAxisSize: MainAxisSize.min,
              mainAxisAlignment: MainAxisAlignment.center,
              children: <Widget>[
                if (icon != null) ...<Widget>[
                  Icon(icon, size: AppIconSizes.small),
                  const SizedBox(width: AppSpacing.xs),
                ],
                Flexible(
                  child: Text(
                    label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    textAlign: TextAlign.center,
                  ),
                ),
              ],
            ),
    );

    final Widget button = Semantics(
      button: true,
      label: loading ? '$label, carregando' : label,
      child: FilledButton(
        onPressed: loading ? null : onPressed,
        style: FilledButton.styleFrom(
          minimumSize: const Size(0, 52),
          backgroundColor: background,
          foregroundColor: foreground,
          disabledBackgroundColor: AppColors.border,
          disabledForegroundColor: AppColors.slateLight,
          textStyle: AppTypography.bodyStrong,
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.sm,
          ),
          shape: const RoundedRectangleBorder(borderRadius: AppRadii.medium),
          elevation: 0,
        ),
        child: content,
      ),
    );
    return expand ? SizedBox(width: double.infinity, child: button) : button;
  }
}
