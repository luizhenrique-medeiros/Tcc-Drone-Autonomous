import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/delivery_point.dart';
import '../../../core/network/api_client.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../payment/presentation/payment_screen.dart';
import 'satellite_map_view.dart';

class ExactLocationScreen extends StatefulWidget {
  const ExactLocationScreen({super.key});

  @override
  State<ExactLocationScreen> createState() => _ExactLocationScreenState();
}

class _ExactLocationScreenState extends State<ExactLocationScreen> {
  final TextEditingController _instructions = TextEditingController();
  GeoCoordinate? _coordinate;
  bool _markerMoved = false;
  bool _safeArea = false;
  String? _addressReference;
  String? _reverseGeocodeError;
  bool _addressUnavailable = false;
  int _reverseGeocodeGeneration = 0;
  Timer? _reverseGeocodeDebounce;
  String? _mapsRuntimeError;
  bool _mapReady = false;

  @override
  void dispose() {
    _reverseGeocodeDebounce?.cancel();
    _instructions.dispose();
    super.dispose();
  }

  void _coordinateChanged(GeoCoordinate value) {
    final int generation = ++_reverseGeocodeGeneration;
    setState(() {
      _coordinate = value;
      _markerMoved = true;
      _addressReference = null;
      _addressUnavailable = false;
      _reverseGeocodeError = null;
    });
    _reverseGeocodeDebounce?.cancel();
    _reverseGeocodeDebounce = Timer(const Duration(milliseconds: 450), () async {
      try {
        final String reference = await AppScope.of(
          context,
        ).mapProvider.reverseGeocode(value);
        if (mounted &&
            generation == _reverseGeocodeGeneration &&
            identical(_coordinate, value)) {
          setState(() {
            _addressReference = reference;
            _addressUnavailable = false;
          });
        }
      } on ApiException catch (error) {
        if (mounted &&
            generation == _reverseGeocodeGeneration &&
            identical(_coordinate, value)) {
          setState(() {
            if (error.statusCode == 404) {
              _addressUnavailable = true;
            } else {
              _reverseGeocodeError =
                  'Não foi possível consultar a referência textual. As coordenadas continuam válidas.';
            }
          });
        }
      } on Object {
        if (mounted &&
            generation == _reverseGeocodeGeneration &&
            identical(_coordinate, value)) {
          setState(() {
            _reverseGeocodeError =
                'Não foi possível consultar a referência textual. As coordenadas continuam válidas.';
          });
        }
      }
    });
  }

  void _mapStyleReady(AppController controller) {
    if (mounted) {
      setState(() {
        _mapReady = true;
        _mapsRuntimeError = null;
      });
    }
    controller.markMapViewReady();
  }

  void _mapFailed(AppController controller, String message) {
    if (mounted) {
      setState(() {
        _mapReady = false;
        _mapsRuntimeError = message;
      });
    }
    controller.markMapViewFailed(message);
  }

  Future<bool> _showConfirmation(
    AppController controller,
    PlaceSuggestion place,
    GeoCoordinate coordinate,
  ) async {
    return await showModalBottomSheet<bool>(
          context: context,
          isScrollControlled: true,
          useSafeArea: true,
          builder: (BuildContext sheetContext) {
            return SizedBox(
              height: MediaQuery.sizeOf(sheetContext).height * 0.86,
              child: ListView(
                padding: const EdgeInsets.all(AppSpacing.screen),
                children: <Widget>[
                  const SectionHeader(
                    title: 'Confirme o ponto final',
                    subtitle:
                        'Revise o mapa, as coordenadas e a declaração de segurança antes de salvar.',
                  ),
                  SatelliteMapView(
                    center: coordinate,
                    provider: controller.mapProvider,
                    interactive: false,
                    onCoordinateChanged: (_) {},
                  ),
                  const SizedBox(height: AppSpacing.md),
                  SurfaceCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          _addressReference ??
                              (_addressUnavailable
                                  ? 'Local sem endereço identificado'
                                  : place.referenceAddress),
                          style: AppTypography.bodyStrong,
                        ),
                        const SizedBox(height: AppSpacing.xs),
                        Text(coordinate.formatted, style: AppTypography.body),
                        const SizedBox(height: AppSpacing.sm),
                        Text(
                          _instructions.text.trim().isEmpty
                              ? 'Sem instruções adicionais.'
                              : _instructions.text.trim(),
                          style: AppTypography.caption,
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: AppSpacing.md),
                  const AppBanner(
                    title: 'Área segura confirmada pelo cliente',
                    message:
                        'A análise administrativa e o checklist operacional continuam obrigatórios.',
                  ),
                  const SizedBox(height: AppSpacing.lg),
                  AppButton(
                    label: 'Salvar este ponto de entrega',
                    icon: Icons.check_circle,
                    onPressed: () => Navigator.of(sheetContext).pop(true),
                  ),
                  const SizedBox(height: AppSpacing.sm),
                  AppButton(
                    label: 'Voltar e ajustar',
                    variant: AppButtonVariant.text,
                    onPressed: () => Navigator.of(sheetContext).pop(false),
                  ),
                ],
              ),
            );
          },
        ) ??
        false;
  }

  Future<void> _confirm() async {
    final AppController controller = AppScope.of(context);
    final GeoCoordinate? coordinate = _coordinate;
    if (coordinate == null ||
        !_markerMoved ||
        !_safeArea ||
        _mapsRuntimeError != null ||
        (!controller.mapProvider.isDevelopmentFallback && !_mapReady)) {
      return;
    }
    final PlaceSuggestion? place = controller.approximatePlace;
    if (place == null) return;
    final bool accepted = await _showConfirmation(
      controller,
      place,
      coordinate,
    );
    if (!accepted || !mounted) return;
    controller.updateExactCoordinate(coordinate);
    controller.updateDeliveryDetails(
      instructions: _instructions.text,
      safeArea: _safeArea,
    );
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => const PaymentScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final PlaceSuggestion? place = controller.approximatePlace;
    final GeoCoordinate? approximateCoordinate = place?.coordinate;
    if (place == null || approximateCoordinate == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Selecione primeiro uma região.')),
      );
    }
    final GeoCoordinate shownCoordinate = _coordinate ?? approximateCoordinate;
    final bool mapOperational =
        controller.mapProvider.isDevelopmentFallback || _mapReady;
    return Scaffold(
      appBar: AppBar(title: const Text('Ponto exato · 2 de 2')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screen),
            children: <Widget>[
              const AppBanner(
                title: 'Ajuste o ponto final',
                message:
                    'Na visão híbrida, mova o mapa sob o pino central. Você pode navegar, aplicar zoom, rotação e inclinação sem limite por cidade ou país.',
              ),
              const SizedBox(height: AppSpacing.lg),
              const SectionHeader(
                title: 'Mova o mapa sob o pino',
                subtitle:
                    'As coordenadas são atualizadas quando a câmera para; o endereço é apenas uma referência opcional.',
              ),
              if (_mapsRuntimeError != null) ...<Widget>[
                AppBanner(
                  title: 'MapTiler indisponível',
                  message: _mapsRuntimeError!,
                  tone: AppBannerTone.danger,
                ),
                const SizedBox(height: AppSpacing.md),
              ] else if (!controller.mapProvider.isDevelopmentFallback &&
                  !_mapReady) ...<Widget>[
                const AppBanner(
                  title: 'Carregando mapa híbrido',
                  message:
                      'A confirmação será liberada quando o estilo MapTiler terminar de carregar.',
                ),
                const SizedBox(height: AppSpacing.md),
              ],
              SatelliteMapView(
                center: approximateCoordinate,
                provider: controller.mapProvider,
                onCoordinateChanged: _coordinateChanged,
                onMapReady: () => _mapStyleReady(controller),
                onMapError: (String message) => _mapFailed(controller, message),
              ),
              const SizedBox(height: AppSpacing.md),
              SurfaceCard(
                child: Row(
                  children: <Widget>[
                    const Icon(Icons.my_location, color: AppColors.brandBlue),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: <Widget>[
                          const Text(
                            'Coordenadas do centro do mapa',
                            style: AppTypography.label,
                          ),
                          Text(
                            shownCoordinate.formatted,
                            key: const Key('exact-coordinate-value'),
                            style: AppTypography.body,
                          ),
                          if (_addressReference != null)
                            Text(
                              _addressReference!,
                              style: AppTypography.caption,
                            ),
                          if (_addressUnavailable)
                            const Text(
                              'Local sem endereço identificado',
                              style: AppTypography.caption,
                            ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              if (_reverseGeocodeError != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                AppBanner(
                  title: 'Referência textual indisponível',
                  message: _reverseGeocodeError!,
                  tone: AppBannerTone.danger,
                ),
              ],
              if (!_markerMoved) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                const AppBanner(
                  title: 'Mova o mapa para continuar',
                  message:
                      'Mesmo que a posição pareça correta, faça um ajuste manual para registrar a escolha exata.',
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              AppTextField(
                controller: _instructions,
                label: 'Instruções para o ponto',
                hint: 'Ex.: gramado aberto ao lado do bloco A',
                icon: Icons.edit_location_alt_outlined,
                maxLines: 3,
              ),
              const SizedBox(height: AppSpacing.md),
              SurfaceCard(
                borderColor: _safeArea ? AppColors.success : AppColors.border,
                child: CheckboxListTile(
                  key: const Key('safe-area-confirmation'),
                  contentPadding: EdgeInsets.zero,
                  value: _safeArea,
                  activeColor: AppColors.success,
                  onChanged: (bool? value) =>
                      setState(() => _safeArea = value ?? false),
                  title: const Text(
                    'Posicionei manualmente o pino em uma área aberta e adequada.',
                  ),
                  subtitle: const Text(
                    'Esta confirmação não substitui a validação técnica e a aprovação administrativa.',
                  ),
                  controlAffinity: ListTileControlAffinity.leading,
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              AppButton(
                key: const Key('confirm-exact-point'),
                label: 'Confirmar ponto exato',
                icon: Icons.check_circle_outline,
                onPressed:
                    _markerMoved &&
                        _safeArea &&
                        _mapsRuntimeError == null &&
                        mapOperational
                    ? _confirm
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
