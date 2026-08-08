import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import 'app/drone_delivery_app.dart';
import 'core/config/app_config.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    AppConfig.validate();
    if (kDebugMode) debugPrint('DEVcore: ${AppConfig.diagnosticSummary}');
    runApp(const DroneDeliveryApp());
  } on AppConfigurationException catch (error) {
    runApp(_ConfigurationErrorApp(message: error.message));
  }
}

class _ConfigurationErrorApp extends StatelessWidget {
  const _ConfigurationErrorApp({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    const Icon(Icons.warning_amber_rounded, size: 48),
                    const SizedBox(height: 16),
                    const Text(
                      'Configuração do aplicativo inválida',
                      style: TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(message, textAlign: TextAlign.center),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
