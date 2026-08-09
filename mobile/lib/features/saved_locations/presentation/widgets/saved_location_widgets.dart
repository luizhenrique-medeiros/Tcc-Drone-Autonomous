import 'package:flutter/material.dart';

import '../../../../core/models/saved_location.dart';
import '../../../../design_system/components/app_banner.dart';
import '../../../../design_system/components/app_button.dart';
import '../../../../design_system/components/section_header.dart';
import '../../../../design_system/components/surface_card.dart';
import '../../../../design_system/tokens/app_colors.dart';
import '../../../../design_system/tokens/app_icon_sizes.dart';
import '../../../../design_system/tokens/app_spacing.dart';
import '../../../../design_system/tokens/app_typography.dart';
import '../../application/saved_locations_controller.dart';

class SavedLocationPicker extends StatelessWidget {
  const SavedLocationPicker({
    required this.controller,
    required this.onSelected,
    super.key,
  });

  final SavedLocationsController controller;
  final ValueChanged<SavedLocation> onSelected;

  @override
  Widget build(BuildContext context) {
    final SavedLocationsViewState state = controller.viewState;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        const SectionHeader(
          title: 'Minhas localizações',
          subtitle: 'Escolha um atalho salvo ou use o mapa livremente.',
        ),
        if (state == SavedLocationsViewState.loading)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.md),
              child: CircularProgressIndicator(),
            ),
          )
        else if (state == SavedLocationsViewState.error ||
            state == SavedLocationsViewState.offline) ...<Widget>[
          AppBanner(
            title: state == SavedLocationsViewState.offline
                ? 'Localizações indisponíveis offline'
                : 'Não foi possível carregar suas localizações',
            message:
                '${controller.loadError ?? 'Tente novamente.'} Você ainda pode escolher outro ponto no mapa.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.sm),
          AppButton(
            label: 'Tentar carregar novamente',
            variant: AppButtonVariant.secondary,
            icon: Icons.refresh,
            onPressed: controller.isLoading ? null : controller.refresh,
          ),
        ] else if (controller.locations.isEmpty)
          const AppBanner(
            title: 'Você ainda não possui localizações salvas',
            message: 'Escolha outro local no mapa para continuar.',
          )
        else
          LayoutBuilder(
            builder: (BuildContext context, BoxConstraints constraints) {
              final double cardWidth = constraints.maxWidth < 280
                  ? constraints.maxWidth
                  : constraints.maxWidth < 352
                  ? (constraints.maxWidth - AppSpacing.sm) / 2
                  : 164;
              return Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: controller.locations
                    .map((SavedLocation location) {
                      return SizedBox(
                        width: cardWidth,
                        child: SurfaceCard(
                          key: Key('saved-location-picker-${location.id}'),
                          onTap: () => onSelected(location),
                          padding: const EdgeInsets.all(AppSpacing.sm),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: <Widget>[
                              Icon(
                                savedLocationIcon(location.name),
                                color: AppColors.brandBlue,
                                size: AppIconSizes.large,
                              ),
                              const SizedBox(height: AppSpacing.xs),
                              Text(
                                location.name,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: AppTypography.bodyStrong,
                              ),
                            ],
                          ),
                        ),
                      );
                    })
                    .toList(growable: false),
              );
            },
          ),
      ],
    );
  }
}

class SavedLocationCard extends StatelessWidget {
  const SavedLocationCard({
    required this.location,
    required this.onEdit,
    required this.onDelete,
    this.busy = false,
    super.key,
  });

  final SavedLocation location;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      key: Key('saved-location-card-${location.id}'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Row(
            children: <Widget>[
              CircleAvatar(
                backgroundColor: AppColors.brandBlueSoft,
                foregroundColor: AppColors.brandBlue,
                child: Icon(savedLocationIcon(location.name)),
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Text(location.name, style: AppTypography.bodyStrong),
              ),
              if (busy)
                const SizedBox(
                  width: AppIconSizes.medium,
                  height: AppIconSizes.medium,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            location.addressReference ?? 'Local sem endereço identificado',
            style: AppTypography.body,
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(location.coordinate.formatted, style: AppTypography.caption),
          if ((location.instructions ?? '').isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpacing.xs),
            Text(location.instructions!, style: AppTypography.caption),
          ],
          const SizedBox(height: AppSpacing.sm),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: <Widget>[
              TextButton.icon(
                onPressed: busy ? null : onEdit,
                icon: const Icon(Icons.edit_outlined),
                label: const Text('Editar'),
              ),
              const SizedBox(width: AppSpacing.xs),
              TextButton.icon(
                onPressed: busy ? null : onDelete,
                icon: const Icon(Icons.delete_outline),
                label: const Text('Excluir'),
                style: TextButton.styleFrom(foregroundColor: AppColors.danger),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class LocationUsageCounter extends StatelessWidget {
  const LocationUsageCounter({required this.count, super.key});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label:
          '$count de ${SavedLocationsController.maximumLocations} localizações salvas',
      child: Text(
        '$count de ${SavedLocationsController.maximumLocations} localizações salvas',
        key: const Key('saved-locations-counter'),
        style: AppTypography.caption,
        textAlign: TextAlign.center,
      ),
    );
  }
}

IconData savedLocationIcon(String name) {
  final String normalized = name.trim().toLowerCase();
  if (normalized.contains('trabalho') || normalized.contains('empresa')) {
    return Icons.work_outline;
  }
  if (normalized.contains('escola') || normalized.contains('faculdade')) {
    return Icons.school_outlined;
  }
  if (normalized.contains('sítio') || normalized.contains('sitio')) {
    return Icons.park_outlined;
  }
  if (normalized.contains('casa') || normalized.contains('lar')) {
    return Icons.home_outlined;
  }
  return Icons.place_outlined;
}
