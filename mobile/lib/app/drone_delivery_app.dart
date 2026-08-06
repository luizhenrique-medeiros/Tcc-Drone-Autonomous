import 'dart:async';

import 'package:flutter/material.dart';

import '../design_system/theme/app_theme.dart';
import '../features/auth/presentation/splash_screen.dart';
import 'app_bootstrap.dart';
import 'app_controller.dart';
import 'app_scope.dart';

class DroneDeliveryApp extends StatefulWidget {
  const DroneDeliveryApp({super.key});

  @override
  State<DroneDeliveryApp> createState() => _DroneDeliveryAppState();
}

class _DroneDeliveryAppState extends State<DroneDeliveryApp> {
  late final AppController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AppBootstrap.createController();
    unawaited(_controller.initialize());
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controller: _controller,
      child: MaterialApp(
        title: 'Devcore Entregas',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.light,
        home: const SplashScreen(),
      ),
    );
  }
}
