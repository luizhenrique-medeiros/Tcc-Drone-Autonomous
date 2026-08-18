import 'package:flutter/material.dart';

import '../../../../core/models/mission_telemetry.dart';
import '../../../../core/models/order.dart';
import '../../../../core/models/product.dart';
import '../../../../design_system/components/app_banner.dart';
import '../../../../design_system/components/app_button.dart';
import '../../../../design_system/components/product_artwork.dart';
import '../../../../design_system/components/product_card.dart';
import '../../../../design_system/tokens/app_colors.dart';
import '../../../../design_system/tokens/app_spacing.dart';
import '../../../../design_system/tokens/app_typography.dart';
import 'order_list_components.dart';

class MissionTelemetryPanel extends StatelessWidget {
  const MissionTelemetryPanel({
    required this.telemetry,
    required this.missionStatus,
    super.key,
  });

  final MissionTelemetrySnapshot? telemetry;
  final MissionStatusSnapshot? missionStatus;

  @override
  Widget build(BuildContext context) {
    final MissionTelemetrySnapshot? snapshot = telemetry;
    final String position =
        snapshot?.latitude != null && snapshot?.longitude != null
        ? '${snapshot!.latitude!.toStringAsFixed(6)}, '
              '${snapshot.longitude!.toStringAsFixed(6)}'
        : _unavailable;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        _TelemetryValue(
          key: const Key('mission-status-value'),
          label: 'Estado da missão',
          value: missionStatus?.status.title ?? _unavailable,
        ),
        if (missionStatus?.status == MissionStatus.verified) ...<Widget>[
          const SizedBox(height: AppSpacing.xs),
          Text(
            MissionStatus.verified.description,
            style: AppTypography.caption,
          ),
        ],
        const Divider(height: AppSpacing.lg),
        if (snapshot == null) ...<Widget>[
          const AppBanner(
            title: 'Telemetria indisponível',
            message:
                'Nenhuma amostra foi recebida neste acompanhamento. O aplicativo não simula dados da aeronave.',
          ),
          const SizedBox(height: AppSpacing.md),
        ] else if (snapshot.isStale == true) ...<Widget>[
          const AppBanner(
            title: 'Última telemetria vencida',
            message:
                'Os valores abaixo são o último registro recebido e não representam o estado atual da aeronave.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.md),
        ],
        _TelemetryValue(
          key: const Key('telemetry-position'),
          label: 'Posição',
          value: position,
        ),
        _TelemetryValue(
          key: const Key('telemetry-altitude'),
          label: 'Altitude relativa',
          value: _formatMeasurement(snapshot?.relativeAltitudeM, 'm'),
        ),
        _TelemetryValue(
          key: const Key('telemetry-battery'),
          label: 'Bateria',
          value: _formatMeasurement(snapshot?.batteryPercent, '%'),
        ),
        _TelemetryValue(
          key: const Key('telemetry-satellites'),
          label: 'Satélites',
          value: snapshot?.satellites?.toString() ?? _unavailable,
        ),
        _TelemetryValue(
          key: const Key('telemetry-flight-mode'),
          label: 'Modo de voo',
          value: snapshot?.flightMode ?? _unavailable,
        ),
        _TelemetryValue(
          key: const Key('telemetry-armed'),
          label: 'Armado',
          value: switch (snapshot?.armed) {
            true => 'Sim',
            false => 'Não',
            null => _unavailable,
          },
        ),
        _TelemetryValue(
          key: const Key('telemetry-source'),
          label: 'Origem',
          value: snapshot?.source?.label ?? _unavailable,
        ),
        _TelemetryValue(
          key: const Key('telemetry-recorded-at'),
          label: 'Registrado em',
          value: snapshot?.recordedAt == null
              ? _unavailable
              : formatOrderDateTime(snapshot!.recordedAt!),
        ),
        _TelemetryValue(
          key: const Key('telemetry-received-at'),
          label: 'Recebido pela API em',
          value: snapshot?.receivedAt == null
              ? _unavailable
              : formatOrderDateTime(snapshot!.receivedAt!),
        ),
        _TelemetryValue(
          key: const Key('telemetry-stale'),
          label: 'Dado vencido',
          value: switch (snapshot?.isStale) {
            true => 'Sim',
            false => 'Não',
            null => _unavailable,
          },
          showDivider: false,
        ),
        const SizedBox(height: AppSpacing.sm),
        const Text(
          'Fonte: evento mission.telemetry recebido do backend. Valores ausentes permanecem indisponíveis.',
          style: AppTypography.caption,
        ),
      ],
    );
  }
}

class _TelemetryValue extends StatelessWidget {
  const _TelemetryValue({
    required this.label,
    required this.value,
    this.showDivider = true,
    super.key,
  });

  final String label;
  final String value;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        Padding(
          padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Expanded(child: Text(label, style: AppTypography.body)),
              const SizedBox(width: AppSpacing.md),
              Flexible(
                child: Text(
                  value,
                  textAlign: TextAlign.end,
                  style: AppTypography.bodyStrong,
                ),
              ),
            ],
          ),
        ),
        if (showDivider) const Divider(height: 1),
      ],
    );
  }
}

const String _unavailable = 'Indisponível';

String _formatMeasurement(double? value, String unit) {
  if (value == null) return _unavailable;
  final String formatted = value == value.roundToDouble()
      ? value.toStringAsFixed(0)
      : value.toStringAsFixed(1);
  return unit == '%' ? '$formatted$unit' : '$formatted $unit';
}

class OrderItemTile extends StatelessWidget {
  const OrderItemTile({required this.item, super.key});

  final OrderLineSnapshot item;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          width: 72,
          child: ProductArtwork(
            key: Key('order-item-artwork-${item.id}'),
            kind: Product.inferKind(item.productName, item.category),
            imageUrl: item.imageUrl,
            semanticLabel: item.productName,
            height: 72,
          ),
        ),
        const SizedBox(width: AppSpacing.md),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Text(item.productName, style: AppTypography.bodyStrong),
              const SizedBox(height: AppSpacing.xxs),
              Text(
                '${item.quantity} × ${formatCurrency(item.unitPrice)}',
                style: AppTypography.caption,
              ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Text(formatCurrency(item.lineTotal), style: AppTypography.bodyStrong),
      ],
    );
  }
}

class OrderPriceSummary extends StatelessWidget {
  const OrderPriceSummary({required this.order, super.key});

  final OrderSnapshot order;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        _PriceLine(label: 'Subtotal', value: formatCurrency(order.subtotal)),
        const SizedBox(height: AppSpacing.sm),
        _PriceLine(
          label: 'Taxa de entrega',
          value: formatCurrency(order.deliveryFee),
        ),
        const SizedBox(height: AppSpacing.sm),
        _PriceLine(
          label: 'Desconto',
          value: '- ${formatCurrency(order.discount)}',
        ),
        const Divider(height: AppSpacing.lg),
        _PriceLine(
          label: 'Total',
          value: formatCurrency(order.total),
          emphasized: true,
        ),
        const SizedBox(height: AppSpacing.md),
        Align(
          alignment: Alignment.centerLeft,
          child: Text(
            'Pagamento simulado: ${order.paymentMethod?.label ?? 'Não informado'}',
            style: AppTypography.body,
          ),
        ),
        const SizedBox(height: AppSpacing.xs),
        const Align(
          alignment: Alignment.centerLeft,
          child: Text(
            'Nenhuma transação bancária é realizada pelo aplicativo.',
            style: AppTypography.caption,
          ),
        ),
      ],
    );
  }
}

class _PriceLine extends StatelessWidget {
  const _PriceLine({
    required this.label,
    required this.value,
    this.emphasized = false,
  });

  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final TextStyle style = emphasized
        ? AppTypography.title
        : AppTypography.body;
    return Row(
      children: <Widget>[
        Expanded(child: Text(label, style: style)),
        Text(value, style: style),
      ],
    );
  }
}

class OrderDeliverySummary extends StatelessWidget {
  const OrderDeliverySummary({
    required this.order,
    required this.onShowMap,
    super.key,
  });

  final OrderSnapshot order;
  final VoidCallback onShowMap;

  @override
  Widget build(BuildContext context) {
    final point = order.deliveryPoint!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(point.displayAddress, style: AppTypography.bodyStrong),
        if (point.label != null &&
            point.label != point.displayAddress) ...<Widget>[
          const SizedBox(height: AppSpacing.xxs),
          Text(point.label!, style: AppTypography.caption),
        ],
        const SizedBox(height: AppSpacing.sm),
        Text(
          'Latitude: ${point.coordinate.latitude.toStringAsFixed(6)}',
          style: AppTypography.body,
        ),
        Text(
          'Longitude: ${point.coordinate.longitude.toStringAsFixed(6)}',
          style: AppTypography.body,
        ),
        const SizedBox(height: AppSpacing.sm),
        Text(
          point.instructions ?? 'Sem instruções adicionais.',
          style: AppTypography.caption,
        ),
        const SizedBox(height: AppSpacing.md),
        AppButton(
          label: 'Ver local no mapa',
          variant: AppButtonVariant.secondary,
          icon: Icons.map_outlined,
          onPressed: onShowMap,
        ),
      ],
    );
  }
}

class OrderDateTimeline extends StatelessWidget {
  const OrderDateTimeline({required this.milestones, super.key});

  final List<OrderMilestone> milestones;

  @override
  Widget build(BuildContext context) {
    final List<OrderMilestone> ordered =
        milestones
            .where((OrderMilestone milestone) => milestone.label != null)
            .toList(growable: false)
          ..sort(
            (OrderMilestone first, OrderMilestone second) =>
                first.occurredAt.compareTo(second.occurredAt),
          );
    if (ordered.isEmpty) {
      return const AppBanner(
        title: 'Datas operacionais indisponíveis',
        message: 'Nenhum marco adicional foi registrado para este pedido.',
      );
    }
    return Column(
      children: <Widget>[
        for (int index = 0; index < ordered.length; index++) ...<Widget>[
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const Icon(
                Icons.event_available_outlined,
                color: AppColors.brandBlue,
              ),
              const SizedBox(width: AppSpacing.sm),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Text(
                      ordered[index].label!,
                      style: AppTypography.bodyStrong,
                    ),
                    Text(
                      formatOrderDateTime(ordered[index].occurredAt),
                      style: AppTypography.caption,
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (index != ordered.length - 1) const Divider(height: AppSpacing.lg),
        ],
      ],
    );
  }
}
