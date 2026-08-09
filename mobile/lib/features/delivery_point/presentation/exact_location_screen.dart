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
import 'satellite_map_view.dart';

class ExactLocationScreen extends StatefulWidget {
  const ExactLocationScreen({
    this.approximatePlace,
    this.initialCoordinate,
    this.initialInstructions = '',
    this.savedLocationId,
    this.requireManualMovement = true,
    this.requireSafeAreaConfirmation = true,
    super.key,
  });

  final PlaceSuggestion? approximatePlace;
  final GeoCoordinate? initialCoordinate;
  final String initialInstructions;
  final String? savedLocationId;
  final bool requireManualMovement;
  final bool requireSafeAreaConfirmation;

  @override
  State<ExactLocationScreen> createState() => _ExactLocationScreenState();
}

class _ExactLocationScreenState extends State<ExactLocationScreen> {
  late final TextEditingController _instructions;
  GeoCoordinate? _coordinate;
  bool _markerMoved = false;
  late bool _safeArea;
  String? _addressReference;
  String? _reverseGeocodeError;
  bool _addressUnavailable = false;
  bool _reverseGeocodePending = false;
  int _reverseGeocodeGeneration = 0;
  Timer? _reverseGeocodeDebounce;
  String? _mapsRuntimeError;
  bool _mapReady = false;
  bool _hydratedFallbackInstructions = false;

  @override
  void initState() {
    super.initState();
    _instructions = TextEditingController(text: widget.initialInstructions);
    _coordinate = widget.initialCoordinate;
    _safeArea = !widget.requireSafeAreaConfirmation;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_hydratedFallbackInstructions) return;
    _hydratedFallbackInstructions = true;
    if (_instructions.text.isEmpty && widget.approximatePlace == null) {
      _instructions.text = AppScope.of(context).deliveryInstructions;
    }
  }

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
      _reverseGeocodePending = true;
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
            _reverseGeocodePending = false;
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
            _reverseGeocodePending = false;
          });
        }
      } on Object {
        if (mounted &&
            generation == _reverseGeocodeGeneration &&
            identical(_coordinate, value)) {
          setState(() {
            _reverseGeocodeError =
                'Não foi possível consultar a referência textual. As coordenadas continuam válidas.';
            _reverseGeocodePending = false;
          });
        }
      }
    });
  }

  void _nudgeCoordinate({required double latitude, required double longitude}) {
    final GeoCoordinate? current =
        _coordinate ??
        widget.initialCoordinate ??
        widget.approximatePlace?.coordinate ??
        AppScope.of(context).approximatePlace?.coordinate;
    if (current == null) return;
    final double nextLatitude = (current.latitude + latitude)
        .clamp(-90.0, 90.0)
        .toDouble();
    final double nextLongitude = (current.longitude + longitude)
        .clamp(-180.0, 180.0)
        .toDouble();
    if (nextLatitude == current.latitude &&
        nextLongitude == current.longitude) {
      return;
    }
    _coordinateChanged(
      GeoCoordinate(latitude: nextLatitude, longitude: nextLongitude),
    );
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
                        'Revise o mapa, as coordenadas e os detalhes antes de confirmar.',
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
                          _displayAddress(place),
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
                  if (widget.requireSafeAreaConfirmation) ...<Widget>[
                    const SizedBox(height: AppSpacing.md),
                    const AppBanner(
                      title: 'Área segura confirmada pelo cliente',
                      message:
                          'A análise administrativa e o checklist operacional continuam obrigatórios.',
                    ),
                  ],
                  const SizedBox(height: AppSpacing.lg),
                  AppButton(
                    label: 'Confirmar este ponto',
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

  Future<void> _confirm(PlaceSuggestion place) async {
    final AppController controller = AppScope.of(context);
    final GeoCoordinate? coordinate =
        _coordinate ?? widget.initialCoordinate ?? place.coordinate;
    final bool movementSatisfied =
        !widget.requireManualMovement || _markerMoved;
    if (coordinate == null ||
        !movementSatisfied ||
        !_safeArea ||
        _mapsRuntimeError != null ||
        (!controller.mapProvider.isDevelopmentFallback && !_mapReady)) {
      return;
    }
    final bool accepted = await _showConfirmation(
      controller,
      place,
      coordinate,
    );
    if (!accepted || !mounted) return;
    final String instructions = _instructions.text.trim();
    final bool savedContentAdjusted =
        widget.savedLocationId != null &&
        instructions != widget.initialInstructions.trim();
    Navigator.of(context).pop(
      LocationSelectionResult(
        approximatePlace: place,
        finalCoordinate: coordinate,
        instructions: instructions,
        safeAreaConfirmed: _safeArea,
        mapProvider: controller.mapProvider.id,
        mapType: 'hybrid',
        regionConfirmed: true,
        exactPointSelected: true,
        userConfirmed: true,
        wasAdjusted: _markerMoved || savedContentAdjusted,
        addressReference: _normalizedAddress(place),
        savedLocationId: widget.savedLocationId,
      ),
    );
  }

  String _displayAddress(PlaceSuggestion place) {
    if (_addressReference case final String reference) return reference;
    if (_markerMoved) {
      return _reverseGeocodePending
          ? 'Atualizando referência textual…'
          : 'Local sem endereço identificado';
    }
    return _addressUnavailable
        ? 'Local sem endereço identificado'
        : place.referenceAddress;
  }

  String? _normalizedAddress(PlaceSuggestion place) {
    if (_markerMoved && _addressReference == null) return null;
    final String value = _displayAddress(place).trim();
    if (value.isEmpty ||
        value == 'Local sem endereço identificado' ||
        value.startsWith('Localização indisponível')) {
      return null;
    }
    return value;
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final PlaceSuggestion? place =
        widget.approximatePlace ?? controller.approximatePlace;
    final GeoCoordinate? approximateCoordinate =
        widget.initialCoordinate ?? place?.coordinate;
    if (place == null || approximateCoordinate == null) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Selecione primeiro uma região.')),
      );
    }
    final GeoCoordinate shownCoordinate = _coordinate ?? approximateCoordinate;
    final bool mapOperational =
        controller.mapProvider.isDevelopmentFallback || _mapReady;
    final bool movementSatisfied =
        !widget.requireManualMovement || _markerMoved;
    return Scaffold(
      appBar: AppBar(title: const Text('Ponto exato · 2 de 2')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screen),
            children: <Widget>[
              AppBanner(
                title: widget.savedLocationId == null
                    ? 'Ajuste o ponto final'
                    : 'Revise a localização salva',
                message: widget.savedLocationId == null
                    ? 'Na visão híbrida, mova o mapa sob o pino central para definir o ponto exato.'
                    : 'Confira o ponto salvo. Você pode mover o mapa para ajustá-lo somente para este uso.',
              ),
              const SizedBox(height: AppSpacing.lg),
              SectionHeader(
                title: widget.requireManualMovement
                    ? 'Mova o mapa sob o pino'
                    : 'Confira ou ajuste o pino',
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
                center: shownCoordinate,
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
                          Text(
                            _displayAddress(place),
                            style: AppTypography.caption,
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              SurfaceCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    const Text(
                      'Ajuste acessível do pino',
                      style: AppTypography.label,
                    ),
                    const SizedBox(height: AppSpacing.xs),
                    const Text(
                      'Use estes controles pelo teclado ou leitor de tela quando não puder arrastar o mapa.',
                      style: AppTypography.caption,
                    ),
                    const SizedBox(height: AppSpacing.sm),
                    Wrap(
                      spacing: AppSpacing.sm,
                      runSpacing: AppSpacing.sm,
                      children: <Widget>[
                        OutlinedButton.icon(
                          key: const Key('nudge-map-north'),
                          onPressed: mapOperational
                              ? () => _nudgeCoordinate(
                                  latitude: 0.00001,
                                  longitude: 0,
                                )
                              : null,
                          icon: const Icon(Icons.arrow_upward),
                          label: const Text('Norte'),
                        ),
                        OutlinedButton.icon(
                          key: const Key('nudge-map-south'),
                          onPressed: mapOperational
                              ? () => _nudgeCoordinate(
                                  latitude: -0.00001,
                                  longitude: 0,
                                )
                              : null,
                          icon: const Icon(Icons.arrow_downward),
                          label: const Text('Sul'),
                        ),
                        OutlinedButton.icon(
                          key: const Key('nudge-map-west'),
                          onPressed: mapOperational
                              ? () => _nudgeCoordinate(
                                  latitude: 0,
                                  longitude: -0.00001,
                                )
                              : null,
                          icon: const Icon(Icons.arrow_back),
                          label: const Text('Oeste'),
                        ),
                        OutlinedButton.icon(
                          key: const Key('nudge-map-east'),
                          onPressed: mapOperational
                              ? () => _nudgeCoordinate(
                                  latitude: 0,
                                  longitude: 0.00001,
                                )
                              : null,
                          icon: const Icon(Icons.arrow_forward),
                          label: const Text('Leste'),
                        ),
                      ],
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
              if (!movementSatisfied) ...<Widget>[
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
              if (widget.requireSafeAreaConfirmation) ...<Widget>[
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
                      'Posicionei ou revisei o pino em uma área aberta e adequada.',
                    ),
                    subtitle: const Text(
                      'Esta confirmação não substitui a validação técnica e a aprovação administrativa.',
                    ),
                    controlAffinity: ListTileControlAffinity.leading,
                  ),
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              AppButton(
                key: const Key('confirm-exact-point'),
                label: 'Confirmar ponto exato',
                icon: Icons.check_circle_outline,
                onPressed:
                    movementSatisfied &&
                        _safeArea &&
                        _mapsRuntimeError == null &&
                        mapOperational
                    ? () => _confirm(place)
                    : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
