import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
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
import '../../delivery_point/presentation/exact_location_screen.dart';

class SavedLocationFormScreen extends StatefulWidget {
  const SavedLocationFormScreen({
    required this.initialSelection,
    this.location,
    super.key,
  });

  final LocationSelectionResult initialSelection;
  final SavedLocation? location;

  @override
  State<SavedLocationFormScreen> createState() =>
      _SavedLocationFormScreenState();
}

class _SavedLocationFormScreenState extends State<SavedLocationFormScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  late final TextEditingController _name;
  late final TextEditingController _instructions;
  late LocationSelectionResult _selection;
  bool _submitting = false;

  bool get _editing => widget.location != null;

  @override
  void initState() {
    super.initState();
    _selection = widget.initialSelection;
    _name = TextEditingController(text: widget.location?.name ?? '');
    _instructions = TextEditingController(
      text: widget.location?.instructions ?? _selection.instructions,
    );
  }

  @override
  void dispose() {
    _name.dispose();
    _instructions.dispose();
    super.dispose();
  }

  Future<void> _adjustPoint() async {
    final PlaceSuggestion place = PlaceSuggestion(
      label: _name.text.trim().isEmpty
          ? 'Localização salva'
          : _name.text.trim(),
      referenceAddress:
          _selection.addressReference ?? 'Local sem endereço identificado',
      coordinate: _selection.finalCoordinate,
    );
    final LocationSelectionResult? result = await Navigator.of(context)
        .push<LocationSelectionResult>(
          MaterialPageRoute<LocationSelectionResult>(
            builder: (_) => ExactLocationScreen(
              approximatePlace: place,
              initialCoordinate: _selection.finalCoordinate,
              initialInstructions: _instructions.text,
              requireManualMovement: false,
              requireSafeAreaConfirmation: true,
            ),
          ),
        );
    if (!mounted || result == null) return;
    setState(() {
      _selection = result;
      _instructions.text = result.instructions;
    });
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false) || _submitting) return;
    setState(() => _submitting = true);
    final SavedLocation? existing = widget.location;
    final bool coordinateChanged =
        existing != null &&
        ((existing.coordinate.latitude - _selection.finalCoordinate.latitude)
                    .abs() >
                0.0000001 ||
            (existing.coordinate.longitude -
                        _selection.finalCoordinate.longitude)
                    .abs() >
                0.0000001);
    final SavedLocationDraft draft = SavedLocationDraft(
      name: _name.text.trim(),
      coordinate: _selection.finalCoordinate,
      mapProvider: _selection.mapProvider,
      mapType: _selection.mapType,
      regionConfirmed: _selection.regionConfirmed,
      exactPointSelected: _selection.exactPointSelected,
      userConfirmed: _selection.userConfirmed,
      userConfirmedSafeArea: _selection.safeAreaConfirmed,
      addressReference: _selection.addressReference,
      instructions: _instructions.text,
      accuracyMeters: coordinateChanged ? null : existing?.accuracyMeters,
    );
    try {
      final controller = AppScope.of(context).savedLocations;
      if (widget.location case final SavedLocation location) {
        await controller.update(location.id, draft);
      } else {
        await controller.create(draft);
      }
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on Object catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.toString()),
          backgroundColor: AppColors.danger,
        ),
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_editing ? 'Editar localização' : 'Nomear localização'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 760),
          child: Form(
            key: _formKey,
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.screen),
              children: <Widget>[
                SectionHeader(
                  title: _editing
                      ? 'Atualize os dados salvos'
                      : 'Como deseja chamar este local?',
                  subtitle:
                      'O nome é apenas um atalho. As coordenadas continuam sendo a referência principal.',
                ),
                if (_editing) ...<Widget>[
                  const AppBanner(
                    title: 'Pedidos antigos permanecem iguais',
                    message:
                        'Estas alterações não modificam pontos já copiados para pedidos anteriores.',
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],
                AppTextField(
                  key: const Key('saved-location-name-field'),
                  controller: _name,
                  label: 'Nome da localização',
                  hint: 'Casa, Trabalho, Sítio…',
                  icon: Icons.bookmark_outline,
                  maxLength: SavedLocationDraft.maxNameLength,
                  validator: (String? value) {
                    final String name = value?.trim() ?? '';
                    if (name.isEmpty)
                      return 'Informe um nome para a localização.';
                    if (name.length > SavedLocationDraft.maxNameLength) {
                      return 'Use no máximo 40 caracteres.';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.md),
                AppTextField(
                  controller: _instructions,
                  label: 'Instruções',
                  hint: 'Ex.: portão ao lado do gramado',
                  icon: Icons.edit_location_alt_outlined,
                  maxLines: 3,
                ),
                const SizedBox(height: AppSpacing.lg),
                const SectionHeader(title: 'Ponto no mapa'),
                SurfaceCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        _selection.addressReference ??
                            'Local sem endereço identificado',
                        style: AppTypography.bodyStrong,
                      ),
                      const SizedBox(height: AppSpacing.xs),
                      Text(
                        _selection.finalCoordinate.formatted,
                        key: const Key('saved-location-form-coordinate'),
                        style: AppTypography.body,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: AppSpacing.sm),
                AppButton(
                  key: const Key('adjust-saved-location-map'),
                  label: 'Ajustar ponto no mapa',
                  variant: AppButtonVariant.secondary,
                  icon: Icons.map_outlined,
                  onPressed: _submitting ? null : _adjustPoint,
                ),
                const SizedBox(height: AppSpacing.lg),
                AppButton(
                  key: const Key('save-saved-location'),
                  label: _editing ? 'Salvar alterações' : 'Salvar localização',
                  icon: Icons.check_circle_outline,
                  loading: _submitting,
                  onPressed: _submitting ? null : _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
