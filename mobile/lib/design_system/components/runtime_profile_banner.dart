import 'package:flutter/material.dart';

import '../tokens/app_colors.dart';
import '../tokens/app_spacing.dart';

class RuntimeProfileBanner extends StatelessWidget {
  const RuntimeProfileBanner({
    required this.isDemoMode,
    required this.profile,
    required this.child,
    super.key,
  });

  final bool isDemoMode;
  final String profile;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (!isDemoMode) return child;
    return Column(
      children: <Widget>[
        Semantics(
          container: true,
          label:
              'Perfil demonstrativo. Dados simulados, sem conexão com hardware real.',
          child: Material(
            key: const Key('runtime-demo-banner'),
            color: AppColors.warningSoft,
            child: SafeArea(
              bottom: false,
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.xs,
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: <Widget>[
                    const Icon(
                      Icons.science_outlined,
                      color: AppColors.warningText,
                      size: 18,
                    ),
                    const SizedBox(width: AppSpacing.xs),
                    Flexible(
                      child: Text(
                        'PERFIL ${profile.toUpperCase()} • dados simulados • sem hardware real',
                        textAlign: TextAlign.center,
                        style: Theme.of(context).textTheme.labelLarge?.copyWith(
                          color: AppColors.warningText,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Expanded(child: child),
      ],
    );
  }
}
