import 'package:flutter/material.dart';

import '../../../../core/models/order.dart';
import '../../../../design_system/components/app_button.dart';
import '../../../../design_system/components/product_card.dart';
import '../../../../design_system/components/status_pill.dart';
import '../../../../design_system/components/surface_card.dart';
import '../../../../design_system/tokens/app_breakpoints.dart';
import '../../../../design_system/tokens/app_colors.dart';
import '../../../../design_system/tokens/app_icon_sizes.dart';
import '../../../../design_system/tokens/app_spacing.dart';
import '../../../../design_system/tokens/app_typography.dart';

class OrderProgressTimeline extends StatelessWidget {
  const OrderProgressTimeline({
    required this.status,
    this.compact = false,
    super.key,
  });

  final OrderStatus status;
  final bool compact;

  static const List<String> _steps = <String>[
    'Pedido realizado',
    'Pedido aprovado',
    'Preparando drone',
    'Em rota',
    'Entrega',
    'Retorno',
    'Concluído',
  ];

  @override
  Widget build(BuildContext context) {
    final int currentIndex = _stageFor(status);
    if (compact) {
      final String currentLabel = currentIndex >= 0
          ? _steps[currentIndex]
          : status.title;
      return Semantics(
        label: 'Andamento do pedido: $currentLabel',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text('Andamento: $currentLabel', style: AppTypography.caption),
            const SizedBox(height: AppSpacing.xs),
            Row(
              children: <Widget>[
                for (int index = 0; index < _steps.length; index++)
                  Expanded(
                    child: Icon(
                      index < currentIndex
                          ? Icons.check_circle
                          : index == currentIndex
                          ? Icons.radio_button_checked
                          : Icons.radio_button_unchecked,
                      size: AppIconSizes.small,
                      color: index <= currentIndex
                          ? AppColors.success
                          : AppColors.border,
                    ),
                  ),
              ],
            ),
          ],
        ),
      );
    }
    return Column(
      children: <Widget>[
        for (int index = 0; index < _steps.length; index++)
          _ProgressStep(
            label: _steps[index],
            completed: currentIndex >= 0 && index < currentIndex,
            current: index == currentIndex,
            last: index == _steps.length - 1,
          ),
      ],
    );
  }

  static int _stageFor(OrderStatus status) => switch (status) {
    OrderStatus.draft || OrderStatus.pendingAdminApproval => 0,
    OrderStatus.approved => 1,
    OrderStatus.missionPreparing ||
    OrderStatus.missionReady ||
    OrderStatus.waitingFlightAuthorization ||
    OrderStatus.missionUploading => 2,
    OrderStatus.inTransit => 3,
    OrderStatus.atDestination || OrderStatus.delivered => 4,
    OrderStatus.returning => 5,
    OrderStatus.completed => 6,
    OrderStatus.rejected ||
    OrderStatus.cancelled ||
    OrderStatus.failed ||
    OrderStatus.unknown => -1,
  };
}

class _ProgressStep extends StatelessWidget {
  const _ProgressStep({
    required this.label,
    required this.completed,
    required this.current,
    required this.last,
  });

  final String label;
  final bool completed;
  final bool current;
  final bool last;

  @override
  Widget build(BuildContext context) {
    final bool reached = completed || current;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          width: 32,
          child: Column(
            children: <Widget>[
              Icon(
                completed
                    ? Icons.check_circle
                    : current
                    ? Icons.radio_button_checked
                    : Icons.radio_button_unchecked,
                color: reached ? AppColors.success : AppColors.border,
              ),
              if (!last)
                Container(
                  width: 2,
                  height: 34,
                  color: completed ? AppColors.success : AppColors.border,
                ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Text(
              label,
              style: current ? AppTypography.bodyStrong : AppTypography.body,
            ),
          ),
        ),
      ],
    );
  }
}

class OrderCard extends StatelessWidget {
  const OrderCard({required this.order, required this.onTap, super.key});

  final OrderSnapshot order;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final Widget identity = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        Text(
          order.displayTitle,
          style: AppTypography.bodyStrong,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
        const SizedBox(height: AppSpacing.xxs),
        Text('Pedido #${order.shortId}', style: AppTypography.caption),
        if (order.displayDate case final DateTime date) ...<Widget>[
          const SizedBox(height: AppSpacing.xxs),
          Text(formatOrderDateTime(date), style: AppTypography.caption),
        ],
      ],
    );
    final Widget summary = Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        StatusPill(status: order.status),
        const SizedBox(height: AppSpacing.sm),
        Text(formatCurrency(order.total), style: AppTypography.bodyStrong),
      ],
    );
    return Semantics(
      button: true,
      label:
          '${order.displayTitle}, pedido ${order.shortId}, ${order.status.title}',
      child: SurfaceCard(
        onTap: onTap,
        elevated: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            LayoutBuilder(
              builder: (BuildContext context, BoxConstraints constraints) {
                if (constraints.maxWidth < AppBreakpoints.compact) {
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      identity,
                      const SizedBox(height: AppSpacing.md),
                      Align(alignment: Alignment.centerLeft, child: summary),
                    ],
                  );
                }
                return Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    Expanded(child: identity),
                    const SizedBox(width: AppSpacing.md),
                    summary,
                    const SizedBox(width: AppSpacing.xs),
                    const Padding(
                      padding: EdgeInsets.only(top: AppSpacing.sm),
                      child: Icon(
                        Icons.chevron_right,
                        color: AppColors.slateLight,
                      ),
                    ),
                  ],
                );
              },
            ),
            if (order.status.isActive) ...<Widget>[
              const SizedBox(height: AppSpacing.md),
              OrderProgressTimeline(
                key: Key('order-progress-${order.id}'),
                status: order.status,
                compact: true,
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class OrdersFilterBar extends StatelessWidget {
  const OrdersFilterBar({
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final OrdersGroup selected;
  final ValueChanged<OrdersGroup> onSelected;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: AppSpacing.xs,
      runSpacing: AppSpacing.xs,
      children: <Widget>[
        _FilterChip(
          label: 'Todos',
          value: OrdersGroup.all,
          selected: selected,
          onSelected: onSelected,
        ),
        _FilterChip(
          label: 'Em andamento',
          value: OrdersGroup.active,
          selected: selected,
          onSelected: onSelected,
        ),
        _FilterChip(
          label: 'Concluídos',
          value: OrdersGroup.history,
          selected: selected,
          onSelected: onSelected,
        ),
      ],
    );
  }
}

class _FilterChip extends StatelessWidget {
  const _FilterChip({
    required this.label,
    required this.value,
    required this.selected,
    required this.onSelected,
  });

  final String label;
  final OrdersGroup value;
  final OrdersGroup selected;
  final ValueChanged<OrdersGroup> onSelected;

  @override
  Widget build(BuildContext context) {
    return ChoiceChip(
      label: Text(label),
      selected: selected == value,
      selectedColor: AppColors.brandBlueSoft,
      checkmarkColor: AppColors.brandBlue,
      side: const BorderSide(color: AppColors.border),
      onSelected: (_) => onSelected(value),
    );
  }
}

class EmptyOrdersState extends StatelessWidget {
  const EmptyOrdersState({required this.onBrowseProducts, super.key});

  final VoidCallback onBrowseProducts;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(
              Icons.receipt_long_outlined,
              size: AppIconSizes.hero,
              color: AppColors.slateLight,
            ),
            const SizedBox(height: AppSpacing.md),
            const Text(
              'Você ainda não realizou nenhum pedido',
              style: AppTypography.title,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Quando fizer sua primeira compra, ela aparecerá aqui.',
              style: AppTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            AppButton(
              label: 'Ver produtos',
              expand: false,
              icon: Icons.storefront_outlined,
              onPressed: onBrowseProducts,
            ),
          ],
        ),
      ),
    );
  }
}

class FilteredOrdersEmptyState extends StatelessWidget {
  const FilteredOrdersEmptyState({required this.group, super.key});

  final OrdersGroup group;

  @override
  Widget build(BuildContext context) {
    final (String title, String message) = switch (group) {
      OrdersGroup.active => (
        'Nenhum pedido em andamento',
        'Seus próximos pedidos ativos aparecerão neste filtro.',
      ),
      OrdersGroup.history => (
        'Nenhum pedido concluído',
        'Pedidos finalizados, cancelados ou recusados aparecerão aqui.',
      ),
      OrdersGroup.all => (
        'Nenhum pedido encontrado',
        'Altere o filtro para consultar seus pedidos.',
      ),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.xl),
      child: Column(
        children: <Widget>[
          const Icon(
            Icons.filter_alt_off_outlined,
            size: AppIconSizes.hero,
            color: AppColors.slateLight,
          ),
          const SizedBox(height: AppSpacing.md),
          Text(title, style: AppTypography.title, textAlign: TextAlign.center),
          const SizedBox(height: AppSpacing.xs),
          Text(message, style: AppTypography.body, textAlign: TextAlign.center),
        ],
      ),
    );
  }
}

String formatOrderDateTime(DateTime value) {
  final DateTime local = value.toLocal();
  String two(int number) => number.toString().padLeft(2, '0');
  return '${two(local.day)}/${two(local.month)}/${local.year} - '
      '${two(local.hour)}:${two(local.minute)}';
}
