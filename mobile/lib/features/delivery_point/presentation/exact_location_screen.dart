import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/delivery_point.dart';
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
  Timer? _reverseGeocodeDebounce;

  @override
  void dispose() {
    _reverseGeocodeDebounce?.cancel();
    _instructions.dispose();
    super.dispose();
  }

  void _coordinateChanged(GeoCoordinate value) {
    setState(() {
      _coordinate = value;
      _markerMoved = true;
    });
    _reverseGeocodeDebounce?.cancel();
    _reverseGeocodeDebounce = Timer(
      const Duration(milliseconds: 450),
      () async {
        try {
          final String reference = await AppScope.of(
            context,
          ).mapProvider.reverseGeocode(value);
          if (mounted && identical(_coordinate, value)) {
            setState(() => _addressReference = reference);
          }
        } on Object {
          if (mounted && identical(_coordinate, value)) {
            setState(
              () => _addressReference = 'Referência textual indisponível',
            );
          }
        }
      },
    );
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
                          _addressReference ?? place.referenceAddress,
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
    final GeoCoordinate? coordinate = _coordinate;
    if (coordinate == null || !_markerMoved || !_safeArea) return;
    final AppController controller = AppScope.of(context);
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
    return Scaffold(
      appBar: AppBar(title: const Text('Ponto exato · 2 de 2')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          const AppBanner(
            title: 'Confirmação manual obrigatória',
            message:
                'Na visão de satélite, toque ou arraste o marcador para uma área aberta e adequada. O endereço anterior não define o destino final.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(
            title: 'Posicione o marcador',
            subtitle: 'O app não seleciona o ponto exato automaticamente.',
          ),
          SatelliteMapView(
            center: approximateCoordinate,
            provider: controller.mapProvider,
            onCoordinateChanged: _coordinateChanged,
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
                        'Coordenadas do marcador',
                        style: AppTypography.label,
                      ),
                      Text(
                        shownCoordinate.formatted,
                        key: const Key('exact-coordinate-value'),
                        style: AppTypography.body,
                      ),
                      if (_addressReference != null)
                        Text(_addressReference!, style: AppTypography.caption),
                    ],
                  ),
                ),
              ],
            ),
          ),
          if (!_markerMoved) ...<Widget>[
            const SizedBox(height: AppSpacing.sm),
            const AppBanner(
              title: 'Mova o marcador para continuar',
              message:
                  'Mesmo que a posição pareça correta, um ajuste manual é exigido para registrar a escolha exata.',
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
                'Posicionei manualmente o marcador em uma área aberta e adequada.',
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
            onPressed: _markerMoved && _safeArea ? _confirm : null,
          ),
        ],
      ),
    );
  }
}
