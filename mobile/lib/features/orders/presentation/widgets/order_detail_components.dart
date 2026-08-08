import 'package:flutter/material.dart';

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
