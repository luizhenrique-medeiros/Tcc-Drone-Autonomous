import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
import '../../../design_system/components/brand_mark.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_durations.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../products/presentation/home_screen.dart';
import 'login_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    unawaited(_openLogin());
  }

  Future<void> _openLogin() async {
    final controller = AppScope.of(context);
    await Future.wait<void>(<Future<void>>[
      Future<void>.delayed(AppDurations.splash),
      controller.initialize(),
    ]);
    if (!mounted) return;
    await Navigator.of(context).pushReplacement<void, void>(
      MaterialPageRoute<void>(
        builder: (_) => controller.isAuthenticated
            ? const HomeScreen()
            : const LoginScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: SafeArea(
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              BrandMark(),
              SizedBox(height: AppSpacing.xl),
              SizedBox(
                width: 28,
                height: 28,
                child: CircularProgressIndicator(
                  strokeWidth: 3,
                  color: AppColors.brandBlue,
                ),
              ),
              SizedBox(height: AppSpacing.md),
              Text('Preparando sua entrega', style: AppTypography.caption),
            ],
          ),
        ),
      ),
    );
  }
}
