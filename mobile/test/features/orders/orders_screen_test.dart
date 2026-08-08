import 'dart:async';

import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/app/app_scope.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:drone_delivery_mobile/design_system/components/product_artwork.dart';
import 'package:drone_delivery_mobile/design_system/theme/app_theme.dart';
import 'package:drone_delivery_mobile/features/orders/presentation/order_details_screen.dart';
import 'package:drone_delivery_mobile/features/orders/presentation/orders_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('mostra estado vazio e leva ao catálogo', (
    WidgetTester tester,
  ) async {
    final _WidgetOrderRepository repository = _WidgetOrderRepository();
    final AppController app = _appController(repository);
    addTearDown(() async {
      app.dispose();
      await repository.close();
    });
    await app.initialize();
    bool browsed = false;

    await tester.pumpWidget(
      _TestHost(
        app: app,
        child: OrdersScreen(onBrowseProducts: () => browsed = true),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Você ainda não realizou nenhum pedido'), findsOneWidget);
    await tester.tap(find.text('Ver produtos'));
    expect(browsed, isTrue);

    await tester.tap(find.text('Em andamento'));
    await tester.pump();
    await app.orders.loadInitial(force: true);
    await tester.pumpAndSettle();
    expect(find.text('Nenhum pedido em andamento'), findsOneWidget);
    expect(find.text('Você ainda não realizou nenhum pedido'), findsNothing);
  });

  testWidgets('diferencia erro de API de lista vazia', (
    WidgetTester tester,
  ) async {
    final _WidgetOrderRepository repository = _WidgetOrderRepository(
      listError: const ApiException('Falha interna', statusCode: 500),
    );
    final AppController app = _appController(repository);
    addTearDown(() async {
      app.dispose();
      await repository.close();
    });
    await app.initialize();

    await tester.pumpWidget(
      _TestHost(
        app: app,
        child: OrdersScreen(onBrowseProducts: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Pedidos indisponíveis'), findsOneWidget);
    expect(find.text('Falha interna'), findsOneWidget);
    expect(find.text('Você ainda não realizou nenhum pedido'), findsNothing);
  });

  testWidgets('distingue estado offline no carregamento inicial', (
    WidgetTester tester,
  ) async {
    final _WidgetOrderRepository repository = _WidgetOrderRepository(
      listError: const ApiException(
        'API indisponível',
        isConnectivityFailure: true,
      ),
    );
    final AppController app = _appController(repository);
    addTearDown(() async {
      app.dispose();
      await repository.close();
    });
    await app.initialize();

    await tester.pumpWidget(
      _TestHost(
        app: app,
        child: OrdersScreen(onBrowseProducts: () {}),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('orders-offline-state')), findsOneWidget);
    expect(find.text('Sem conexão'), findsOneWidget);
    expect(find.text('API indisponível'), findsOneWidget);
    expect(find.text('Pedidos indisponíveis'), findsNothing);
  });

  testWidgets('lista, filtra e mantém card durante falha do tempo real', (
    WidgetTester tester,
  ) async {
    final _WidgetOrderRepository repository = _WidgetOrderRepository(
      orders: <OrderSnapshot>[
        _fullOrder('ativo', OrderStatus.inTransit),
        _fullOrder('concluido', OrderStatus.completed),
      ],
    );
    final AppController app = _appController(repository);
    addTearDown(() async {
      app.dispose();
      await repository.close();
    });
    await app.initialize();

    await tester.pumpWidget(
      _TestHost(
        app: app,
        child: OrdersScreen(onBrowseProducts: () {}),
      ),
    );
    await tester.pumpAndSettle();
    repository.emit(
      'ativo',
      const OrderConnectionEvent(OrderRealtimeState.unavailable),
    );
    await tester.pumpAndSettle();

    expect(app.orders.realtimeState, OrderRealtimeState.unavailable);
    expect(find.text('Em andamento'), findsWidgets);
    expect(find.text('Histórico de pedidos'), findsOneWidget);
    expect(
      find.text('Tempo real temporariamente indisponível'),
      findsOneWidget,
    );
    expect(find.byKey(const Key('order-card-ativo')), findsOneWidget);
    expect(find.byKey(const Key('order-progress-ativo')), findsOneWidget);
    expect(find.text('Andamento: Em rota'), findsOneWidget);
    expect(find.byKey(const Key('order-progress-concluido')), findsNothing);

    await tester.tap(find.text('Concluídos'));
    await tester.pump();
    await app.orders.loadInitial(force: true);
    await tester.pumpAndSettle();
    expect(app.orders.group, OrdersGroup.history);
    expect(app.orders.orders.map((OrderSnapshot order) => order.id), <String>[
      'concluido',
    ]);
    expect(find.byKey(const Key('order-card-concluido')), findsOneWidget);
    expect(find.byKey(const Key('order-card-ativo')), findsNothing);
  });

  testWidgets('detalhe mostra dados reais e abre mapa somente leitura', (
    WidgetTester tester,
  ) async {
    final OrderSnapshot order = _fullOrder(
      'pedido-detalhe',
      OrderStatus.approved,
    );
    final _WidgetOrderRepository repository = _WidgetOrderRepository(
      orders: <OrderSnapshot>[order],
    );
    final AppController app = _appController(repository);
    addTearDown(() async {
      app.dispose();
      await repository.close();
    });
    await app.initialize();

    await tester.pumpWidget(
      _TestHost(
        app: app,
        child: OrderDetailsScreen(
          orderId: order.id,
          controller: app.orders,
          mapProvider: const DevelopmentMapProvider(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('X-Burger'), findsWidgets);
    final ProductArtwork artwork = tester.widget<ProductArtwork>(
      find.byKey(const Key('order-item-artwork-item')),
    );
    expect(artwork.imageUrl, 'https://cdn.example.test/x-burger.webp');
    expect(find.text('Pagamento simulado: PIX'), findsOneWidget);
    expect(find.text('Latitude: -22.997100'), findsOneWidget);
    expect(find.text('Pedido aprovado'), findsWidgets);
    expect(find.text('Pedido realizado'), findsWidgets);
    expect(find.text('Mission Claimed'), findsNothing);
    expect(find.text('Mission Uploaded'), findsNothing);
    expect(repository.requestedDetails, <String>[order.id]);

    await tester.ensureVisible(find.text('Ver local no mapa'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Ver local no mapa'));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('order-delivery-map')), findsOneWidget);
  });
}

AppController _appController(OrderRepository repository) {
  return AppController(
    authRepository: DemoAuthRepository(),
    productRepository: DemoProductRepository(),
    checkoutRepository: const DemoCheckoutRepository(),
    orderRepository: repository,
    mapProvider: const DevelopmentMapProvider(),
    locationService: const DevelopmentLocationService(),
    isDemoMode: true,
  );
}

OrderSnapshot _fullOrder(String id, OrderStatus status) {
  return OrderSnapshot(
    id: id,
    status: status,
    paymentMethod: SimulatedPaymentMethod.pix,
    subtotal: 29.90,
    deliveryFee: 7.50,
    discount: 5.98,
    total: 31.42,
    createdAt: DateTime.utc(2026, 8, 8, 16, 45),
    items: const <OrderLineSnapshot>[
      OrderLineSnapshot(
        id: 'item',
        productId: 'produto',
        productName: 'X-Burger',
        category: 'Lanches',
        imageUrl: 'https://cdn.example.test/x-burger.webp',
        unitPrice: 29.90,
        quantity: 1,
        lineTotal: 29.90,
      ),
    ],
    deliveryPoint: const OrderDeliveryPointSnapshot(
      coordinate: GeoCoordinate(latitude: -22.9971, longitude: -46.5832),
      referenceAddress: 'Bom Jesus dos Perdões',
      instructions: 'Área aberta',
    ),
    milestones: <OrderMilestone>[
      OrderMilestone(
        eventType: 'ORDER_SUBMITTED',
        occurredAt: DateTime.utc(2026, 8, 8, 16, 45),
      ),
      OrderMilestone(
        eventType: 'MISSION_CLAIMED',
        occurredAt: DateTime.utc(2026, 8, 8, 16, 46),
      ),
      OrderMilestone(
        eventType: 'MISSION_UPLOADED',
        occurredAt: DateTime.utc(2026, 8, 8, 16, 47),
      ),
    ],
    detailLoaded: true,
  );
}

class _TestHost extends StatelessWidget {
  const _TestHost({required this.app, required this.child});

  final AppController app;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return AppScope(
      controller: app,
      child: MaterialApp(theme: AppTheme.light, home: child),
    );
  }
}

class _WidgetOrderRepository implements OrderRepository {
  _WidgetOrderRepository({
    this.orders = const <OrderSnapshot>[],
    this.listError,
  });

  final List<OrderSnapshot> orders;
  final Object? listError;
  final List<String> requestedDetails = <String>[];
  final Map<String, StreamController<OrderWatchEvent>> _streams =
      <String, StreamController<OrderWatchEvent>>{};

  @override
  Future<OrderSnapshot> getOrder(String orderId) async {
    requestedDetails.add(orderId);
    return orders.firstWhere((OrderSnapshot order) => order.id == orderId);
  }

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) async {
    if (listError case final Object error) throw error;
    final List<OrderSnapshot> filtered = orders
        .where((OrderSnapshot order) {
          return switch (group) {
            OrdersGroup.all => true,
            OrdersGroup.active => order.status.isActive,
            OrdersGroup.history => order.status.isTerminal,
          };
        })
        .map<OrderSnapshot>(
          (OrderSnapshot order) => order.copyWith(
            milestones: const <OrderMilestone>[],
            detailLoaded: false,
          ),
        )
        .toList(growable: false);
    return OrdersPage(
      items: filtered,
      hasMore: false,
      returnedCount: filtered.length,
    );
  }

  @override
  Stream<OrderWatchEvent> watchOrder(String orderId) {
    return _streams
        .putIfAbsent(
          orderId,
          () => StreamController<OrderWatchEvent>.broadcast(),
        )
        .stream;
  }

  void emit(String orderId, OrderWatchEvent event) =>
      _streams[orderId]!.add(event);

  Future<void> close() async {
    for (final StreamController<OrderWatchEvent> stream in _streams.values) {
      await stream.close();
    }
  }
}
