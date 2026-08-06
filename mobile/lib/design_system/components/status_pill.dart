import 'package:flutter/material.dart';

import '../../core/models/order.dart';
import '../tokens/app_colors.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_radii.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

class StatusPill extends StatelessWidget {
  const StatusPill({required this.status, super.key});

  final OrderStatus status;

  @override
  Widget build(BuildContext context) {
    final (
      Color background,
      Color foreground,
      IconData icon,
    ) = switch (status) {
      OrderStatus.completed || OrderStatus.delivered => (
        AppColors.successSoft,
        AppColors.successText,
        Icons.check_circle,
      ),
      OrderStatus.rejected || OrderStatus.failed || OrderStatus.cancelled => (
        AppColors.dangerSoft,
        AppColors.dangerText,
        Icons.error,
      ),
      OrderStatus.inTransit ||
      OrderStatus.atDestination ||
      OrderStatus.returning => (
        AppColors.brandBlueSoft,
        AppColors.infoText,
        Icons.flight,
      ),
      OrderStatus.unknown => (
        AppColors.dangerSoft,
        AppColors.dangerText,
        Icons.sync_problem,
      ),
      _ => (AppColors.warningSoft, AppColors.warningText, Icons.schedule),
    };
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(color: background, borderRadius: AppRadii.pill),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Icon(icon, size: AppIconSizes.small, color: foreground),
          const SizedBox(width: AppSpacing.xs),
          Flexible(
            child: Text(
              status.title,
              style: AppTypography.caption.copyWith(color: foreground),
            ),
          ),
        ],
      ),
    );
  }
}
