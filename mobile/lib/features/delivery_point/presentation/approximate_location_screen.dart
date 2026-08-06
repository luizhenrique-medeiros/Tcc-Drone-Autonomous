import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/location/location_service.dart';
import '../../../core/models/delivery_point.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import 'exact_location_screen.dart';

class ApproximateLocationScreen extends StatefulWidget {
  const ApproximateLocationScreen({super.key});

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialized) return;
    _initialized = true;
    if (AppScope.of(context).mapProvider.isDevelopmentFallback) {
      unawaited(_search(''));
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
    final String normalized = query.trim();
    if (normalized.length < 3) {
      setState(() {
        _suggestions = <PlaceSuggestion>[];
        _hasSearched = false;
        _searchError = null;
      });
      return;
    }
    _searchDebounce = Timer(
      const Duration(milliseconds: 400),
      () => unawaited(_search(normalized)),
    );
  }

  Future<void> _search(String query) async {
    setState(() {
      _loading = true;
      _searchError = null;
    });
    try {
      final List<PlaceSuggestion> results = await AppScope.of(
        context,
      ).mapProvider.search(query);
      if (!mounted) return;
      setState(() {
        _suggestions = results;
        _hasSearched = true;
      });
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _suggestions = <PlaceSuggestion>[];
        _hasSearched = true;
        _searchError = error.toString();
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _selectSuggestion(PlaceSuggestion suggestion) async {
    setState(() {
      _loading = true;
      _searchError = null;
    });
    try {
      final PlaceSuggestion resolved = await AppScope.of(
        context,
      ).mapProvider.resolve(suggestion);
      if (!mounted) return;
      setState(() => _selected = resolved);
    } on Object catch (error) {
      if (!mounted) return;
      setState(() => _searchError = error.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _useApproximateLocation() async {
    final AppController controller = AppScope.of(context);
    final ApproximateLocationResult result = await controller.locationService
        .requestApproximateLocation();
    if (!mounted) return;
    setState(() {
      final GeoCoordinate? coordinate = result.coordinate;
      _selected = coordinate == null
          ? null
          : PlaceSuggestion(
              label:
                  result.permissionState == LocationPermissionState.unavailable
                  ? 'Região acadêmica demonstrativa'
                  : 'Minha região aproximada',
              referenceAddress:
                  'Localização aproximada — ajuste obrigatório na etapa 2',
              coordinate: coordinate,
            );
      _locationMessage = result.message;
    });
  }

  Future<void> _continue() async {
    final PlaceSuggestion? selected = _selected;
    if (selected == null || !selected.isResolved) return;
    AppScope.of(context).selectApproximatePlace(selected);
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(builder: (_) => const ExactLocationScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Região de entrega · 1 de 2')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          const AppBanner(
            title: 'Endereço é apenas referência',
            message:
                'A busca centraliza a região. As coordenadas finais só serão definidas depois que você mover o marcador manualmente no mapa da etapa 2.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.lg),
          SectionHeader(
            title: 'Encontre uma região aproximada',
            subtitle: 'Provedor ativo: ${controller.mapProvider.displayName}',
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
                  ? 'Comportamento de desenvolvimento'
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
          for (final PlaceSuggestion suggestion in _suggestions) ...<Widget>[
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
                'Nenhuma região encontrada. Revise rua, número, bairro, cidade ou CEP.',
                style: AppTypography.body,
              ),
            ),
          if (_selected != null &&
              !_suggestions.any(
                (PlaceSuggestion item) =>
                    item.providerId != null &&
                    item.providerId == _selected?.providerId,
              )) ...<Widget>[
            _PlaceTile(suggestion: _selected!, selected: true, onTap: () {}),
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
