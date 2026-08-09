import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/config/app_config.dart';
import '../../../core/location/location_service.dart';
import '../../../core/models/delivery_point.dart';
import '../../../core/models/saved_location.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../saved_locations/presentation/widgets/saved_location_widgets.dart';
import 'exact_location_screen.dart';

class ApproximateLocationScreen extends StatefulWidget {
  const ApproximateLocationScreen({
    this.showSavedLocations = false,
    this.initialPlace,
    this.initialInstructions = '',
    super.key,
  });

  final bool showSavedLocations;
  final PlaceSuggestion? initialPlace;
  final String initialInstructions;

  @override
  State<ApproximateLocationScreen> createState() =>
      _ApproximateLocationScreenState();
}

class _ApproximateLocationScreenState extends State<ApproximateLocationScreen> {
  final TextEditingController _searchController = TextEditingController();
  List<PlaceSuggestion> _suggestions = <PlaceSuggestion>[];
  PlaceSuggestion? _selected;
  bool _loading = false;
  bool _hasSearched = false;
  String? _locationMessage;
  String? _searchError;
  bool _initialized = false;
  Timer? _searchDebounce;
  int _searchGeneration = 0;
  int _resolutionGeneration = 0;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialized) return;
    _initialized = true;
    _selected = widget.initialPlace;
    if (widget.showSavedLocations) {
      unawaited(AppScope.of(context).savedLocations.load());
    }
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _scheduleSearch(String query) {
    _searchDebounce?.cancel();
    _resolutionGeneration++;
    final String normalized = query.trim();
    if (normalized.length < 3) {
      _searchGeneration++;
      setState(() {
        _suggestions = <PlaceSuggestion>[];
        _selected = null;
        _hasSearched = false;
        _searchError = null;
      });
      return;
    }
    _searchGeneration++;
    setState(() {
      _suggestions = <PlaceSuggestion>[];
      _selected = null;
      _hasSearched = false;
      _searchError = null;
    });
    _searchDebounce = Timer(
      const Duration(milliseconds: 400),
      () => unawaited(_search(normalized)),
    );
  }

  Future<void> _search(String query) async {
    _resolutionGeneration++;
    final int generation = ++_searchGeneration;
    setState(() {
      _loading = true;
      _suggestions = <PlaceSuggestion>[];
      _selected = null;
      _hasSearched = false;
      _searchError = null;
    });
    try {
      final List<PlaceSuggestion> results = await AppScope.of(
        context,
      ).mapProvider.search(query);
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _suggestions = results;
        _hasSearched = true;
      });
    } on Object catch (error) {
      if (!mounted || generation != _searchGeneration) return;
      setState(() {
        _suggestions = <PlaceSuggestion>[];
        _hasSearched = true;
        _searchError = error.toString();
      });
    } finally {
      if (mounted && generation == _searchGeneration) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _selectSuggestion(PlaceSuggestion suggestion) async {
    final int generation = ++_resolutionGeneration;
    setState(() {
      _loading = true;
      _searchError = null;
    });
    try {
      final PlaceSuggestion resolved = await AppScope.of(
        context,
      ).mapProvider.resolve(suggestion);
      if (!mounted || generation != _resolutionGeneration) return;
      setState(() => _selected = resolved);
    } on Object catch (error) {
      if (!mounted || generation != _resolutionGeneration) return;
      setState(() => _searchError = error.toString());
    } finally {
      if (mounted && generation == _resolutionGeneration) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _useApproximateLocation() async {
    final int generation = ++_resolutionGeneration;
    final AppController controller = AppScope.of(context);
    final ApproximateLocationResult result = await controller.locationService
        .requestApproximateLocation();
    if (!mounted || generation != _resolutionGeneration) return;
    setState(() {
      final GeoCoordinate coordinate =
          result.coordinate ??
          GeoCoordinate(
            latitude: AppConfig.defaultMapLatitude,
            longitude: AppConfig.defaultMapLongitude,
          );
      _selected = PlaceSuggestion(
        label: result.coordinate == null
            ? 'Região inicial do mapa'
            : 'Minha região aproximada',
        referenceAddress: result.coordinate == null
            ? 'Localização indisponível — ajuste obrigatório na etapa 2'
            : 'Localização aproximada — ajuste obrigatório na etapa 2',
        coordinate: coordinate,
      );
      _locationMessage = result.message;
    });
  }

  Future<void> _continue() async {
    final PlaceSuggestion? selected = _selected;
    if (selected == null || !selected.isResolved) return;
    await _openExactLocation(
      place: selected,
      initialInstructions: widget.initialInstructions,
    );
  }

  Future<void> _openMapDirectly() async {
    _resolutionGeneration++;
    final PlaceSuggestion manual = PlaceSuggestion(
      label: 'Seleção manual por coordenadas',
      referenceAddress: 'Local sem endereço identificado',
      coordinate: GeoCoordinate(
        latitude: AppConfig.defaultMapLatitude,
        longitude: AppConfig.defaultMapLongitude,
      ),
    );
    await _openExactLocation(
      place: manual,
      initialInstructions: widget.initialInstructions,
    );
  }

  Future<void> _useSavedLocation(SavedLocation location) async {
    await _openExactLocation(
      place: location.asPlaceSuggestion,
      initialInstructions: location.instructions ?? '',
      savedLocationId: location.id,
      requireManualMovement: false,
    );
  }

  Future<void> _openExactLocation({
    required PlaceSuggestion place,
    required String initialInstructions,
    String? savedLocationId,
    bool requireManualMovement = true,
  }) async {
    final LocationSelectionResult? result = await Navigator.of(context)
        .push<LocationSelectionResult>(
          MaterialPageRoute<LocationSelectionResult>(
            builder: (_) => ExactLocationScreen(
              approximatePlace: place,
              initialCoordinate: place.coordinate,
              initialInstructions: initialInstructions,
              savedLocationId: savedLocationId,
              requireManualMovement: requireManualMovement,
            ),
          ),
        );
    if (!mounted || result == null) return;
    Navigator.of(context).pop(result);
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Região de entrega · 1 de 2')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 960),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screen),
            children: <Widget>[
              const AppBanner(
                title: 'Escolha livremente no mapa',
                message:
                    'Use uma referência para centralizar a região ou abra o mapa diretamente. O endereço é opcional; latitude e longitude finais definem o ponto.',
              ),
              if (controller.mapInitializationMessage != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                AppBanner(
                  title: 'Mapa online indisponível',
                  message: controller.mapInitializationMessage!,
                  tone: AppBannerTone.danger,
                ),
              ],
              if (widget.showSavedLocations) ...<Widget>[
                const SizedBox(height: AppSpacing.lg),
                AnimatedBuilder(
                  animation: controller.savedLocations,
                  builder: (BuildContext context, _) {
                    return SavedLocationPicker(
                      controller: controller.savedLocations,
                      onSelected: (SavedLocation location) {
                        unawaited(_useSavedLocation(location));
                      },
                    );
                  },
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              SectionHeader(
                title: 'Como deseja começar?',
                subtitle:
                    'Provedor ativo: ${controller.mapProvider.displayName}',
              ),
              AppButton(
                key: const Key('open-map-directly'),
                label: 'Abrir mapa sem informar endereço',
                icon: Icons.map_outlined,
                onPressed: _openMapDirectly,
              ),
              const SizedBox(height: AppSpacing.lg),
              const SectionHeader(
                title: 'Ou pesquise uma referência',
                subtitle:
                    'A pesquisa pode apontar para qualquer país ou área rural.',
              ),
              AppTextField(
                controller: _searchController,
                label: 'Pesquisar endereço ou referência',
                icon: Icons.search,
                textInputAction: TextInputAction.search,
                onChanged: _scheduleSearch,
                onSubmitted: (String value) => _search(value.trim()),
              ),
              const SizedBox(height: AppSpacing.sm),
              AppButton(
                label: 'Pesquisar região',
                variant: AppButtonVariant.secondary,
                icon: Icons.travel_explore,
                loading: _loading,
                onPressed: _searchController.text.trim().length < 3
                    ? null
                    : () => _search(_searchController.text.trim()),
              ),
              const SizedBox(height: AppSpacing.sm),
              AppButton(
                label: 'Usar localização aproximada',
                variant: AppButtonVariant.text,
                icon: Icons.my_location,
                onPressed: _useApproximateLocation,
              ),
              if (_locationMessage != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                AppBanner(
                  title: controller.mapProvider.isDevelopmentFallback
                      ? 'Região inicial'
                      : 'Localização aproximada',
                  message: _locationMessage!,
                ),
              ],
              if (_searchError != null) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                AppBanner(
                  title: 'Não foi possível pesquisar',
                  message: _searchError!,
                  tone: AppBannerTone.danger,
                ),
              ],
              const SizedBox(height: AppSpacing.lg),
              for (final PlaceSuggestion suggestion in _suggestions.take(
                5,
              )) ...<Widget>[
                _PlaceTile(
                  suggestion: suggestion,
                  selected: _selected?.providerId != null
                      ? _selected?.providerId == suggestion.providerId
                      : identical(_selected, suggestion),
                  onTap: () => unawaited(_selectSuggestion(suggestion)),
                ),
                const SizedBox(height: AppSpacing.sm),
              ],
              if (_hasSearched && _suggestions.isEmpty && _searchError == null)
                const SurfaceCard(
                  child: Text(
                    'Nenhuma região encontrada. Revise a referência ou abra o mapa diretamente.',
                    style: AppTypography.body,
                  ),
                ),
              if (_suggestions.isNotEmpty) ...<Widget>[
                const SizedBox(height: AppSpacing.sm),
                AppButton(
                  label: 'Fechar resultados',
                  variant: AppButtonVariant.text,
                  icon: Icons.close,
                  onPressed: () {
                    _searchGeneration++;
                    setState(() {
                      _suggestions = <PlaceSuggestion>[];
                      _hasSearched = false;
                      _loading = false;
                    });
                  },
                ),
              ],
              if (_selected != null &&
                  !_suggestions.any(
                    (PlaceSuggestion item) =>
                        item.providerId != null &&
                        item.providerId == _selected?.providerId,
                  )) ...<Widget>[
                _PlaceTile(
                  suggestion: _selected!,
                  selected: true,
                  onTap: () {},
                ),
                const SizedBox(height: AppSpacing.sm),
              ],
              const SizedBox(height: AppSpacing.md),
              AppButton(
                key: const Key('confirm-approximate-region'),
                label: 'Confirmar região e ajustar ponto',
                icon: Icons.arrow_forward,
                onPressed: _selected?.isResolved ?? false ? _continue : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PlaceTile extends StatelessWidget {
  const _PlaceTile({
    required this.suggestion,
    required this.selected,
    required this.onTap,
  });

  final PlaceSuggestion suggestion;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      borderColor: selected ? AppColors.brandBlue : AppColors.border,
      child: Row(
        children: <Widget>[
          Icon(
            selected ? Icons.radio_button_checked : Icons.radio_button_off,
            color: selected ? AppColors.brandBlue : AppColors.slateLight,
          ),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(suggestion.label, style: AppTypography.bodyStrong),
                Text(suggestion.referenceAddress, style: AppTypography.caption),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
