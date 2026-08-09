import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
import '../../../core/models/delivery_point.dart';
import '../../../core/models/saved_location.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../delivery_point/presentation/approximate_location_screen.dart';
import '../application/saved_locations_controller.dart';
import 'saved_location_form_screen.dart';
import 'widgets/saved_location_widgets.dart';

class SavedLocationsScreen extends StatefulWidget {
  const SavedLocationsScreen({super.key});

  @override
  State<SavedLocationsScreen> createState() => _SavedLocationsScreenState();
}

class _SavedLocationsScreenState extends State<SavedLocationsScreen> {
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    unawaited(AppScope.of(context).savedLocations.load());
  }

  Future<void> _addLocation() async {
    final LocationSelectionResult? selection = await Navigator.of(context)
        .push<LocationSelectionResult>(
          MaterialPageRoute<LocationSelectionResult>(
            builder: (_) => const ApproximateLocationScreen(),
          ),
        );
    if (!mounted || selection == null) return;
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => SavedLocationFormScreen(initialSelection: selection),
      ),
    );
  }

  Future<void> _editLocation(SavedLocation location) async {
    final LocationSelectionResult selection = LocationSelectionResult(
      approximatePlace: location.asPlaceSuggestion,
      finalCoordinate: location.coordinate,
      instructions: location.instructions ?? '',
      safeAreaConfirmed: location.userConfirmedSafeArea,
      mapProvider: location.mapProvider,
      mapType: location.mapType,
      regionConfirmed: location.regionConfirmed,
      exactPointSelected: location.exactPointSelected,
      userConfirmed: location.userConfirmed,
      wasAdjusted: false,
      addressReference: location.addressReference,
    );
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => SavedLocationFormScreen(
          location: location,
          initialSelection: selection,
        ),
      ),
    );
  }

  Future<void> _deleteLocation(SavedLocation location) async {
    final bool confirmed =
        await showDialog<bool>(
          context: context,
          builder: (BuildContext dialogContext) {
            return AlertDialog(
              title: const Text('Excluir localização?'),
              content: Text(
                '“${location.name}” será removida das suas localizações salvas.',
              ),
              actions: <Widget>[
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(false),
                  child: const Text('Cancelar'),
                ),
                FilledButton(
                  key: const Key('confirm-delete-saved-location'),
                  style: FilledButton.styleFrom(
                    backgroundColor: AppColors.danger,
                  ),
                  onPressed: () => Navigator.of(dialogContext).pop(true),
                  child: const Text('Excluir'),
                ),
              ],
            );
          },
        ) ??
        false;
    if (!confirmed || !mounted) return;
    try {
      await AppScope.of(context).savedLocations.delete(location.id);
    } on Object catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString()),
          backgroundColor: AppColors.danger,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final SavedLocationsController controller = AppScope.of(
      context,
    ).savedLocations;
    return Scaffold(
      appBar: AppBar(title: const Text('Minhas localizações')),
      body: AnimatedBuilder(
        animation: controller,
        builder: (BuildContext context, _) {
          return Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 960),
              child: RefreshIndicator(
                onRefresh: controller.refresh,
                child: ListView(
                  key: const Key('saved-locations-list'),
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(AppSpacing.screen),
                  children: <Widget>[
                    const SectionHeader(
                      title: 'Minhas localizações',
                      subtitle:
                          'Salve até três atalhos. Você ainda pode pedir para qualquer outro ponto no mapa.',
                    ),
                    if (controller.viewState == SavedLocationsViewState.loading)
                      const Center(
                        child: Padding(
                          padding: EdgeInsets.all(AppSpacing.xl),
                          child: CircularProgressIndicator(),
                        ),
                      )
                    else if (controller.viewState ==
                            SavedLocationsViewState.error ||
                        controller.viewState ==
                            SavedLocationsViewState.offline) ...<Widget>[
                      AppBanner(
                        title:
                            controller.viewState ==
                                SavedLocationsViewState.offline
                            ? 'Você está offline'
                            : 'Não foi possível carregar',
                        message: controller.loadError ?? 'Tente novamente.',
                        tone: AppBannerTone.danger,
                      ),
                      const SizedBox(height: AppSpacing.md),
                      AppButton(
                        label: 'Tentar novamente',
                        icon: Icons.refresh,
                        onPressed: controller.refresh,
                      ),
                    ] else ...<Widget>[
                      if (controller.locations.isEmpty)
                        const AppBanner(
                          title: 'Nenhuma localização salva',
                          message:
                              'Adicione um atalho quando quiser. Nenhum card vazio será criado.',
                        )
                      else
                        for (final SavedLocation location
                            in controller.locations) ...<Widget>[
                          SavedLocationCard(
                            location: location,
                            busy: controller.isMutating(location.id),
                            onEdit: () => _editLocation(location),
                            onDelete: () => _deleteLocation(location),
                          ),
                          const SizedBox(height: AppSpacing.sm),
                        ],
                      if (controller.limitReached) ...<Widget>[
                        const SizedBox(height: AppSpacing.sm),
                        const AppBanner(
                          title: 'Limite de 3 localizações atingido',
                          message:
                              'Exclua ou edite uma localização para liberar espaço.',
                          tone: AppBannerTone.warning,
                        ),
                      ],
                      const SizedBox(height: AppSpacing.md),
                      LocationUsageCounter(count: controller.locations.length),
                      const SizedBox(height: AppSpacing.md),
                      AppButton(
                        key: const Key('add-saved-location'),
                        label: 'Adicionar localização',
                        icon: Icons.add_location_alt_outlined,
                        onPressed:
                            controller.limitReached || controller.isCreating
                            ? null
                            : _addLocation,
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}
