import 'dart:async';

import 'package:flutter/material.dart';

import '../../../core/maps/map_provider.dart';
import '../../../core/models/order.dart';
import '../../../core/repositories/order_repository.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/status_pill.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_breakpoints.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../delivery_point/presentation/satellite_map_view.dart';
import '../application/orders_controller.dart';
import 'widgets/order_detail_components.dart';
import 'widgets/order_list_components.dart';

class OrderDetailsScreen extends StatefulWidget {
  const OrderDetailsScreen({
    required this.orderId,
    required this.controller,
    required this.mapProvider,
    super.key,
  });

  final String orderId;
  final OrdersController controller;
  final MapProvider mapProvider;

  @override
  State<OrderDetailsScreen> createState() => _OrderDetailsScreenState();
}

class _OrderDetailsScreenState extends State<OrderDetailsScreen> {
  bool _showMap = false;
  String? _mapError;

  @override
  void initState() {
    super.initState();
    unawaited(widget.controller.loadDetails(widget.orderId));
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (BuildContext context, _) {
        final OrderSnapshot? order = widget.controller.orderById(
          widget.orderId,
        );
        final bool loading = widget.controller.isDetailLoading(widget.orderId);
        final String? error = widget.controller.detailError(widget.orderId);
        return Scaffold(
          appBar: AppBar(
            title: const Text('Detalhes do pedido'),
            actions: <Widget>[
              IconButton(
                key: const Key('refresh-order-details'),
                tooltip: 'Atualizar pedido',
                onPressed: loading
                    ? null
                    : () => widget.controller.loadDetails(
                        widget.orderId,
                        force: true,
                      ),
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          body: order == null
              ? _InitialDetailState(
                  loading: loading,
                  error: error,
                  onRetry: () => widget.controller.loadDetails(
                    widget.orderId,
                    force: true,
                  ),
                )
              : RefreshIndicator(
                  onRefresh: () => widget.controller.loadDetails(
                    widget.orderId,
                    force: true,
                  ),
                  child: Center(
                    child: ConstrainedBox(
                      constraints: const BoxConstraints(maxWidth: 1120),
                      child: ListView(
                        key: const Key('order-details-list'),
                        physics: const AlwaysScrollableScrollPhysics(),
                        padding: const EdgeInsets.all(AppSpacing.screen),
                        children: <Widget>[
                          if (loading) const LinearProgressIndicator(),
                          if (loading) const SizedBox(height: AppSpacing.md),
                          if (error != null) ...<Widget>[
                            AppBanner(
                              title: 'Não foi possível atualizar o pedido',
                              message: error,
                              tone: AppBannerTone.danger,
                            ),
                            const SizedBox(height: AppSpacing.md),
                          ],
                          if (widget.controller.realtimeStateFor(
                                    widget.orderId,
                                  ) !=
                                  OrderRealtimeState.connected &&
                              order.status.isActive) ...<Widget>[
                            const AppBanner(
                              title: 'Atualização temporariamente indisponível',
                              message:
                                  'Exibindo o último estado conhecido. Use atualizar para consultar novamente.',
                              tone: AppBannerTone.warning,
                            ),
                            const SizedBox(height: AppSpacing.md),
                          ],
                          if (order.rejectionReason != null) ...<Widget>[
                            AppBanner(
                              title: 'Motivo informado pela administração',
                              message: order.rejectionReason!,
                              tone: AppBannerTone.danger,
                            ),
                            const SizedBox(height: AppSpacing.md),
                          ],
                          LayoutBuilder(
                            builder:
                                (
                                  BuildContext context,
                                  BoxConstraints constraints,
                                ) {
                                  final bool expanded =
                                      constraints.maxWidth >=
                                      AppBreakpoints.expanded;
                                  final List<Widget> primary = _primarySections(
                                    order,
                                  );
                                  final List<Widget> secondary =
                                      _secondarySections(order);
                                  if (!expanded) {
                                    return Column(
                                      children: <Widget>[
                                        ...primary,
                                        ...secondary,
                                      ],
                                    );
                                  }
                                  return Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: <Widget>[
                                      Expanded(
                                        child: Column(children: primary),
                                      ),
                                      const SizedBox(width: AppSpacing.lg),
                                      Expanded(
                                        child: Column(children: secondary),
                                      ),
                                    ],
                                  );
                                },
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
        );
      },
    );
  }

  List<Widget> _primarySections(OrderSnapshot order) {
    return <Widget>[
      _DetailSection(
        title: 'Identificação',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Pedido #${order.shortId}',
                    style: AppTypography.title,
                  ),
                ),
                StatusPill(status: order.status),
              ],
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(order.displayTitle, style: AppTypography.bodyStrong),
            if (order.displayDate case final DateTime date) ...<Widget>[
              const SizedBox(height: AppSpacing.xs),
              Text(formatOrderDateTime(date), style: AppTypography.body),
            ],
            const SizedBox(height: AppSpacing.xs),
            Text(order.status.description, style: AppTypography.caption),
          ],
        ),
      ),
      const SizedBox(height: AppSpacing.md),
      _DetailSection(
        title: 'Produtos',
        child: order.items.isEmpty
            ? const AppBanner(
                title: 'Produtos indisponíveis',
                message: 'A API não retornou os itens deste pedido.',
                tone: AppBannerTone.warning,
              )
            : Column(
                children: <Widget>[
                  for (
                    int index = 0;
                    index < order.items.length;
                    index++
                  ) ...<Widget>[
                    OrderItemTile(item: order.items[index]),
                    if (index != order.items.length - 1)
                      const Divider(height: AppSpacing.lg),
                  ],
                ],
              ),
      ),
      const SizedBox(height: AppSpacing.md),
      _DetailSection(
        title: 'Valores',
        child: OrderPriceSummary(order: order),
      ),
      const SizedBox(height: AppSpacing.md),
    ];
  }

  List<Widget> _secondarySections(OrderSnapshot order) {
    return <Widget>[
      _DetailSection(
        title: 'Andamento',
        child: OrderProgressTimeline(status: order.status),
      ),
      const SizedBox(height: AppSpacing.md),
      _DetailSection(
        title: 'Telemetria da missão',
        child: MissionTelemetryPanel(
          telemetry: widget.controller.telemetryFor(order.id),
          missionStatus: widget.controller.missionStatusFor(order.id),
        ),
      ),
      const SizedBox(height: AppSpacing.md),
      _DetailSection(
        title: 'Local de entrega',
        child: order.deliveryPoint == null
            ? const AppBanner(
                title: 'Local indisponível',
                message: 'A API não retornou o ponto deste pedido.',
                tone: AppBannerTone.warning,
              )
            : Column(
                children: <Widget>[
                  OrderDeliverySummary(
                    order: order,
                    onShowMap: () => setState(() {
                      _showMap = true;
                      _mapError = null;
                    }),
                  ),
                  if (_showMap) ...<Widget>[
                    const SizedBox(height: AppSpacing.md),
                    SatelliteMapView(
                      key: const Key('order-delivery-map'),
                      center: order.deliveryPoint!.coordinate,
                      provider: widget.mapProvider,
                      interactive: false,
                      onMapError: (String message) {
                        if (mounted) setState(() => _mapError = message);
                      },
                    ),
                  ],
                  if (_mapError != null) ...<Widget>[
                    const SizedBox(height: AppSpacing.sm),
                    AppBanner(
                      title: 'Mapa indisponível',
                      message: _mapError!,
                      tone: AppBannerTone.danger,
                    ),
                  ],
                ],
              ),
      ),
      const SizedBox(height: AppSpacing.md),
      _DetailSection(
        title: 'Datas importantes',
        child: OrderDateTimeline(milestones: order.milestones),
      ),
      const SizedBox(height: AppSpacing.md),
    ];
  }
}

class _DetailSection extends StatelessWidget {
  const _DetailSection({required this.title, required this.child});

  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(title, style: AppTypography.title),
          const SizedBox(height: AppSpacing.md),
          child,
        ],
      ),
    );
  }
}

class _InitialDetailState extends StatelessWidget {
  const _InitialDetailState({
    required this.loading,
    required this.error,
    required this.onRetry,
  });

  final bool loading;
  final String? error;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.screen),
          child: loading
              ? const Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    CircularProgressIndicator(color: AppColors.brandBlue),
                    SizedBox(height: AppSpacing.md),
                    Text('Carregando detalhes…'),
                  ],
                )
              : Column(
                  mainAxisSize: MainAxisSize.min,
                  children: <Widget>[
                    AppBanner(
                      title: 'Pedido indisponível',
                      message: error ?? 'Não foi possível localizar o pedido.',
                      tone: AppBannerTone.danger,
                    ),
                    const SizedBox(height: AppSpacing.md),
                    AppButton(label: 'Tentar novamente', onPressed: onRetry),
                  ],
                ),
        ),
      ),
    );
  }
}
