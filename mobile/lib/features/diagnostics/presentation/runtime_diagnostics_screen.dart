import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/config/app_config.dart';
import '../../../core/diagnostics/runtime_diagnostics_service.dart';
import '../../../core/location/location_service.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_breakpoints.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';

class RuntimeDiagnosticsScreen extends StatefulWidget {
  const RuntimeDiagnosticsScreen({super.key});

  @override
  State<RuntimeDiagnosticsScreen> createState() =>
      _RuntimeDiagnosticsScreenState();
}

class _RuntimeDiagnosticsScreenState extends State<RuntimeDiagnosticsScreen> {
  late final RuntimeDiagnosticsService _service =
      const RuntimeDiagnosticsService(apiBaseUrl: AppConfig.apiBaseUrl);
  DiagnosticProbe _backend = const DiagnosticProbe.notTested();
  DiagnosticProbe _webSocket = const DiagnosticProbe.notTested();
  DiagnosticProbe _mapSearch = const DiagnosticProbe.notTested();
  ApproximateLocationResult? _location;
  bool _testingConnectivity = false;
  bool _testingMapSearch = false;
  bool _testingLocation = false;

  @override
  void initState() {
    super.initState();
    scheduleMicrotask(_testConnectivity);
  }

  Future<void> _testConnectivity() async {
    if (_testingConnectivity) return;
    setState(() => _testingConnectivity = true);
    final List<DiagnosticProbe> probes = await Future.wait<DiagnosticProbe>(
      <Future<DiagnosticProbe>>[
        _service.probeBackend(),
        _service.probeWebSocket(),
      ],
    );
    if (!mounted) return;
    setState(() {
      _backend = probes[0];
      _webSocket = probes[1];
      _testingConnectivity = false;
    });
  }

  Future<void> _testMapSearch(AppController controller) async {
    if (_testingMapSearch) return;
    setState(() => _testingMapSearch = true);
    final DiagnosticProbe result = controller.isAuthenticated
        ? await _service.probeMapSearch(controller.mapProvider)
        : const DiagnosticProbe(
            ok: false,
            message: 'Faça login para testar a pesquisa protegida de mapas',
          );
    if (!mounted) return;
    setState(() {
      _mapSearch = result;
      _testingMapSearch = false;
    });
  }

  Future<void> _testLocation(AppController controller) async {
    if (_testingLocation) return;
    setState(() => _testingLocation = true);
    final ApproximateLocationResult result = await controller.locationService
        .requestApproximateLocation();
    if (!mounted) return;
    setState(() {
      _location = result;
      _testingLocation = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (!AppConfig.diagnosticsEnabled) {
      return const Scaffold(
        body: Center(child: Text('Diagnóstico indisponível neste build.')),
      );
    }
    final AppController controller = AppScope.of(context);
    final bool mapsInitialized = controller.mapViewReady;
    return Scaffold(
      appBar: AppBar(title: const Text('Diagnóstico de desenvolvimento')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screen),
            children: <Widget>[
              const Text(
                'Somente estado técnico e presença de sessão são exibidos. Chaves e tokens nunca aparecem aqui.',
                style: AppTypography.body,
              ),
              const SizedBox(height: AppSpacing.md),
              SurfaceCard(
                child: Column(
                  children: <Widget>[
                    _DiagnosticRow(label: 'Platform', value: _platformName),
                    const _DiagnosticRow(
                      label: 'API URL',
                      value: AppConfig.apiBaseUrl,
                    ),
                    _DiagnosticRow(
                      label: 'Backend reachable',
                      value: _backend.message,
                      state: _backend.ok,
                    ),
                    _DiagnosticRow(
                      label: 'WebSocket reachable',
                      value: _webSocket.message,
                      state: _webSocket.ok,
                    ),
                    _DiagnosticRow(
                      label: 'MapTiler initialized',
                      value: mapsInitialized
                          ? 'MapLibre onStyleLoadedCallback confirmado'
                          : controller.mapProvider.isDevelopmentFallback
                          ? controller.mapInitializationMessage ??
                                controller.mapProvider.displayName
                          : 'Provider pronto; abra a etapa do mapa para validar a renderização',
                      state: mapsInitialized,
                    ),
                    _DiagnosticRow(
                      label: 'Map search initialized',
                      value: _mapSearch.message,
                      state: _mapSearch.ok,
                    ),
                    _DiagnosticRow(
                      label: 'Geolocation permission',
                      value: _location?.permissionState.name ?? 'Não testado',
                      state: _location == null
                          ? null
                          : _location!.coordinate != null,
                    ),
                    _DiagnosticRow(
                      label: 'Latitude',
                      value:
                          _location?.coordinate?.latitude.toStringAsFixed(6) ??
                          'Não disponível',
                    ),
                    _DiagnosticRow(
                      label: 'Longitude',
                      value:
                          _location?.coordinate?.longitude.toStringAsFixed(6) ??
                          'Não disponível',
                    ),
                    _DiagnosticRow(
                      label: 'Auth token present',
                      value: controller.isAuthenticated ? 'Sim' : 'Não',
                      state: controller.isAuthenticated,
                    ),
                    const _DiagnosticRow(
                      label: 'App version',
                      value: AppConfig.appVersion,
                    ),
                    _DiagnosticRow(
                      label: 'Build mode',
                      value: AppConfig.buildMode,
                      last: true,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.md),
              AppButton(
                label: 'Testar backend e WebSocket',
                icon: Icons.sync,
                loading: _testingConnectivity,
                onPressed: _testConnectivity,
              ),
              const SizedBox(height: AppSpacing.sm),
              AppButton(
                label: 'Testar pesquisa MapTiler',
                icon: Icons.travel_explore,
                variant: AppButtonVariant.secondary,
                loading: _testingMapSearch,
                onPressed: () => _testMapSearch(controller),
              ),
              const SizedBox(height: AppSpacing.sm),
              AppButton(
                label: 'Testar geolocalização',
                icon: Icons.my_location,
                variant: AppButtonVariant.secondary,
                loading: _testingLocation,
                onPressed: () => _testLocation(controller),
              ),
              if (_location != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                Text(_location!.message, style: AppTypography.caption),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String get _platformName => kIsWeb ? 'Web' : defaultTargetPlatform.name;
}

class _DiagnosticRow extends StatelessWidget {
  const _DiagnosticRow({
    required this.label,
    required this.value,
    this.state,
    this.last = false,
  });

  final String label;
  final String value;
  final bool? state;
  final bool last;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      decoration: BoxDecoration(
        border: last
            ? null
            : const Border(bottom: BorderSide(color: AppColors.border)),
      ),
      child: LayoutBuilder(
        builder: (BuildContext context, BoxConstraints constraints) {
          final bool compact = constraints.maxWidth < AppBreakpoints.medium;
          final Widget valueWidget = Row(
            mainAxisAlignment: compact
                ? MainAxisAlignment.start
                : MainAxisAlignment.end,
            children: <Widget>[
              if (state != null) ...<Widget>[
                Icon(
                  state! ? Icons.check_circle : Icons.error,
                  size: 18,
                  color: state! ? AppColors.success : AppColors.danger,
                ),
                const SizedBox(width: AppSpacing.xs),
              ],
              Flexible(
                child: Text(
                  value,
                  textAlign: compact ? TextAlign.start : TextAlign.end,
                  style: AppTypography.caption,
                ),
              ),
            ],
          );
          if (compact) {
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(label, style: AppTypography.label),
                const SizedBox(height: AppSpacing.xs),
                valueWidget,
              ],
            );
          }
          return Row(
            children: <Widget>[
              Expanded(child: Text(label, style: AppTypography.label)),
              const SizedBox(width: AppSpacing.sm),
              Expanded(flex: 2, child: valueWidget),
            ],
          );
        },
      ),
    );
  }
}
