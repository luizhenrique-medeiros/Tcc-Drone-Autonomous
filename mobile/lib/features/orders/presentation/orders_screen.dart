import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/order.dart';
import '../../../core/repositories/order_repository.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../application/orders_controller.dart';
import 'order_details_screen.dart';
import 'widgets/order_list_components.dart';

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({required this.onBrowseProducts, super.key});

  final VoidCallback onBrowseProducts;

  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  bool _started = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_started) return;
    _started = true;
    unawaited(AppScope.of(context).orders.loadInitial());
  }

  @override
  Widget build(BuildContext context) {
    final AppController appController = AppScope.of(context);
    final OrdersController controller = appController.orders;
    return AnimatedBuilder(
      animation: controller,
      builder: (BuildContext context, _) {
        return Material(
          color: Colors.transparent,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 960),
              child: RefreshIndicator(
                onRefresh: controller.refresh,
                child: ListView(
                  key: const Key('orders-list'),
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.all(AppSpacing.screen),
                  children: <Widget>[
                    Row(
                      children: <Widget>[
                        const Expanded(
                          child: SectionHeader(
                            title: 'Meus pedidos',
                            subtitle: 'Acompanhe entregas atuais e anteriores.',
                          ),
                        ),
                        IconButton(
                          key: const Key('refresh-orders'),
                          tooltip: 'Atualizar pedidos',
                          onPressed: controller.isRefreshing
                              ? null
                              : controller.refresh,
                          icon: controller.isRefreshing
                              ? const SizedBox(
                                  width: AppIconSizes.medium,
                                  height: AppIconSizes.medium,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.refresh),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.md),
                    OrdersFilterBar(
                      selected: controller.group,
                      onSelected: (OrdersGroup group) {
                        unawaited(controller.selectGroup(group));
                      },
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    if (controller.realtimeState !=
                            OrderRealtimeState.connected &&
                        controller.activeOrders.isNotEmpty) ...<Widget>[
                      AppBanner(
                        title:
                            controller.realtimeState ==
                                OrderRealtimeState.reconnecting
                            ? 'Reconectando atualizações'
                            : 'Tempo real temporariamente indisponível',
                        message:
                            'O último estado conhecido foi mantido. Você pode atualizar manualmente.',
                        tone: AppBannerTone.warning,
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      AppButton(
                        label: 'Atualizar agora',
                        variant: AppButtonVariant.secondary,
                        icon: Icons.sync,
                        onPressed: controller.refresh,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],
                    if (controller.refreshError
                        case final String error) ...<Widget>[
                      AppBanner(
                        title: controller.isOffline
                            ? 'Sem conexão'
                            : 'Não foi possível atualizar',
                        message: error,
                        tone: controller.isOffline
                            ? AppBannerTone.warning
                            : AppBannerTone.danger,
                      ),
                      const SizedBox(height: AppSpacing.lg),
                    ],
                    if (controller.isInitialLoading && !controller.hasLoaded)
                      const _OrdersLoadingState()
                    else if (controller.isOffline && !controller.hasLoaded)
                      _OrdersOfflineState(
                        message:
                            controller.loadError ??
                            'Verifique sua conexão e tente novamente.',
                        onRetry: () => controller.loadInitial(force: true),
                      )
                    else if (controller.loadError != null &&
                        !controller.hasLoaded)
                      _OrdersErrorState(
                        message: controller.loadError!,
                        onRetry: () => controller.loadInitial(force: true),
                      )
                    else if (controller.isEmpty)
                      controller.group == OrdersGroup.all
                          ? EmptyOrdersState(
                              onBrowseProducts: widget.onBrowseProducts,
                            )
                          : FilteredOrdersEmptyState(group: controller.group)
                    else ...<Widget>[
                      ..._orderSections(context, controller, appController),
                      if (controller.hasMore) ...<Widget>[
                        const SizedBox(height: AppSpacing.md),
                        AppButton(
                          key: const Key('load-more-orders'),
                          label: 'Carregar mais',
                          variant: AppButtonVariant.secondary,
                          loading: controller.isLoadingMore,
                          onPressed: controller.loadMore,
                        ),
                      ],
                    ],
                  ],
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  List<Widget> _orderSections(
    BuildContext context,
    OrdersController controller,
    AppController appController,
  ) {
    final List<Widget> result = <Widget>[];
    void addOrders(String title, List<OrderSnapshot> orders) {
      if (orders.isEmpty) return;
      result.add(SectionHeader(title: title));
      result.add(const SizedBox(height: AppSpacing.sm));
      for (final OrderSnapshot order in orders) {
        result.add(
          OrderCard(
            key: Key('order-card-${order.id}'),
            order: order,
            onTap: () async {
              await Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (_) => OrderDetailsScreen(
                    orderId: order.id,
                    controller: controller,
                    mapProvider: appController.mapProvider,
                  ),
                ),
              );
            },
          ),
        );
        result.add(const SizedBox(height: AppSpacing.sm));
      }
      result.add(const SizedBox(height: AppSpacing.md));
    }

    switch (controller.group) {
      case OrdersGroup.all:
        addOrders('Em andamento', controller.activeOrders);
        addOrders('Histórico de pedidos', controller.historyOrders);
      case OrdersGroup.active:
        addOrders('Pedidos em andamento', controller.orders);
      case OrdersGroup.history:
        addOrders('Histórico de pedidos', controller.orders);
    }
    return result;
  }
}

class _OrdersLoadingState extends StatelessWidget {
  const _OrdersLoadingState();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: AppSpacing.xl),
      child: Column(
        children: <Widget>[
          CircularProgressIndicator(color: AppColors.brandBlue),
          SizedBox(height: AppSpacing.md),
          Text('Carregando seus pedidos…', style: AppTypography.body),
        ],
      ),
    );
  }
}

class _OrdersOfflineState extends StatelessWidget {
  const _OrdersOfflineState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      key: const Key('orders-offline-state'),
      children: <Widget>[
        AppBanner(
          title: 'Sem conexão',
          message: message,
          tone: AppBannerTone.warning,
        ),
        const SizedBox(height: AppSpacing.md),
        AppButton(
          label: 'Tentar novamente',
          icon: Icons.wifi_find,
          onPressed: onRetry,
        ),
      ],
    );
  }
}

class _OrdersErrorState extends StatelessWidget {
  const _OrdersErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: <Widget>[
        AppBanner(
          title: 'Pedidos indisponíveis',
          message: message,
          tone: AppBannerTone.danger,
        ),
        const SizedBox(height: AppSpacing.md),
        AppButton(label: 'Tentar novamente', onPressed: onRetry),
      ],
    );
  }
}
