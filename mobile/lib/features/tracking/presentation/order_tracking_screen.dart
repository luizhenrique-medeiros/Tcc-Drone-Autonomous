import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/order.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/status_pill.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_radii.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../products/presentation/home_screen.dart';

class OrderTrackingScreen extends StatelessWidget {
  const OrderTrackingScreen({super.key});

  static const List<OrderStatus> _milestones = <OrderStatus>[
    OrderStatus.pendingAdminApproval,
    OrderStatus.approved,
    OrderStatus.missionPreparing,
    OrderStatus.missionReady,
    OrderStatus.waitingFlightAuthorization,
    OrderStatus.missionUploading,
    OrderStatus.inTransit,
    OrderStatus.atDestination,
    OrderStatus.returning,
    OrderStatus.completed,
  ];

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final OrderSnapshot? order = controller.order;
    if (order == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Acompanhamento')),
        body: const Center(child: Text('Nenhum pedido em acompanhamento.')),
      );
    }

    final bool exceptional = <OrderStatus>{
      OrderStatus.rejected,
      OrderStatus.failed,
      OrderStatus.cancelled,
      OrderStatus.unknown,
    }.contains(order.status);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Acompanhar pedido'),
        automaticallyImplyLeading: false,
      ),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          if (controller.isDemoMode) ...<Widget>[
            const AppBanner(
              title: 'Progressão simulada no aplicativo',
              message:
                  'Neste modo, os estados avançam automaticamente para demonstrar a interface. Isso não representa telemetria, aprovação ou voo real.',
              tone: AppBannerTone.warning,
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          _StatusHero(order: order),
          if (controller.checkoutError != null) ...<Widget>[
            const SizedBox(height: AppSpacing.md),
            AppBanner(
              title: 'Atualização interrompida',
              message: controller.checkoutError!,
              tone: AppBannerTone.danger,
            ),
          ],
          if (order.rejectionReason != null) ...<Widget>[
            const SizedBox(height: AppSpacing.md),
            AppBanner(
              title: 'Motivo informado pela administração',
              message: order.rejectionReason!,
              tone: AppBannerTone.danger,
            ),
          ],
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(
            title: 'Etapas da operação',
            subtitle:
                'Aprovação do pedido e autorização do voo são controles distintos.',
          ),
          SurfaceCard(
            child: Column(
              children: <Widget>[
                for (int index = 0; index < _milestones.length; index++)
                  _TimelineItem(
                    status: _milestones[index],
                    currentStatus: order.status,
                    isLast: index == _milestones.length - 1,
                    exceptional: exceptional,
                  ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          SurfaceCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('Pedido ${order.id}', style: AppTypography.label),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Ponto final: ${controller.exactCoordinate?.formatted ?? 'indisponível'}',
                  style: AppTypography.body,
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Pagamento: ${controller.paymentMethod.label}',
                  style: AppTypography.body,
                ),
                const SizedBox(height: AppSpacing.xs),
                const Text(
                  'O aplicativo apenas acompanha. Ele não aprova, autoriza voo, envia MAVLink ou controla o drone.',
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          if (order.status.isTerminal)
            AppButton(
              label: 'Voltar ao início',
              onPressed: () async {
                await Navigator.of(context).pushAndRemoveUntil<void>(
                  MaterialPageRoute<void>(builder: (_) => const HomeScreen()),
                  (Route<Object?> route) => false,
                );
              },
            )
          else
            const AppBanner(
              title: 'Atualizações automáticas',
              message:
                  'Mantenha esta tela aberta. Em integração real, o backend continua sendo a fonte de verdade.',
            ),
        ],
      ),
    );
  }
}

class _StatusHero extends StatelessWidget {
  const _StatusHero({required this.order});

  final OrderSnapshot order;

  @override
  Widget build(BuildContext context) {
    final bool danger = <OrderStatus>{
      OrderStatus.rejected,
      OrderStatus.failed,
      OrderStatus.cancelled,
      OrderStatus.unknown,
    }.contains(order.status);
    return Container(
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: danger ? AppColors.dangerSoft : AppColors.brandBlueSoft,
        borderRadius: AppRadii.large,
      ),
      child: Column(
        children: <Widget>[
          Icon(
            danger ? Icons.error_outline : _iconFor(order.status),
            size: AppIconSizes.hero,
            color: danger ? AppColors.danger : AppColors.brandBlue,
          ),
          const SizedBox(height: AppSpacing.md),
          StatusPill(status: order.status),
          const SizedBox(height: AppSpacing.md),
          Text(
            order.status.description,
            style: AppTypography.body,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  static IconData _iconFor(OrderStatus status) => switch (status) {
    OrderStatus.inTransit || OrderStatus.returning => Icons.flight,
    OrderStatus.atDestination || OrderStatus.delivered => Icons.location_on,
    OrderStatus.completed => Icons.task_alt,
    OrderStatus.waitingFlightAuthorization =>
      Icons.admin_panel_settings_outlined,
    _ => Icons.inventory_2_outlined,
  };
}

class _TimelineItem extends StatelessWidget {
  const _TimelineItem({
    required this.status,
    required this.currentStatus,
    required this.isLast,
    required this.exceptional,
  });

  final OrderStatus status;
  final OrderStatus currentStatus;
  final bool isLast;
  final bool exceptional;

  @override
  Widget build(BuildContext context) {
    final int currentIndex = OrderTrackingScreen._milestones.indexOf(
      _normalized(currentStatus),
    );
    final int itemIndex = OrderTrackingScreen._milestones.indexOf(status);
    final bool reached = !exceptional && currentIndex >= itemIndex;
    final bool current = !exceptional && currentIndex == itemIndex;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: <Widget>[
        SizedBox(
          width: 32,
          child: Column(
            children: <Widget>[
              Icon(
                reached ? Icons.check_circle : Icons.radio_button_unchecked,
                color: reached ? AppColors.success : AppColors.border,
              ),
              if (!isLast)
                Container(
                  width: 2,
                  height: 42,
                  color: reached ? AppColors.success : AppColors.border,
                ),
            ],
          ),
        ),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(
                  status.title,
                  style: current
                      ? AppTypography.bodyStrong
                      : AppTypography.body,
                ),
                if (current)
                  Text(status.description, style: AppTypography.caption),
              ],
            ),
          ),
        ),
      ],
    );
  }

  OrderStatus _normalized(OrderStatus value) => switch (value) {
    OrderStatus.delivered => OrderStatus.atDestination,
    _ => value,
  };
}
