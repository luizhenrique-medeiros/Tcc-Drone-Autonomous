import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_radii.dart';
import '../tokens/app_shadows.dart';
import '../tokens/app_spacing.dart';

class SurfaceCard extends StatelessWidget {
  const SurfaceCard({
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.md),
    this.onTap,
    this.borderColor = AppColors.border,
    this.elevated = false,
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;
  final Color borderColor;
  final bool elevated;

  @override
  Widget build(BuildContext context) {
    final ShapeBorder shape = RoundedRectangleBorder(
      borderRadius: AppRadii.medium,
      side: BorderSide(color: borderColor),
    );
    final Widget paddedChild = Padding(padding: padding, child: child);
    final Widget interactiveChild = onTap == null
        ? paddedChild
        : Semantics(
            button: true,
            child: InkWell(
              onTap: onTap,
              borderRadius: AppRadii.medium,
              child: paddedChild,
            ),
          );
    return Container(
      decoration: BoxDecoration(
        borderRadius: AppRadii.medium,
        boxShadow: elevated ? AppShadows.card : null,
      ),
      child: Material(
        color: AppColors.surface,
        shape: shape,
        clipBehavior: Clip.antiAlias,
        child: interactiveChild,
      ),
    );
  }
}
