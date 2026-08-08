import 'dart:async';

import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/product_repository.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('exige confirmação manual da área antes de enviar pedido', () async {
    final AppController controller = AppController(
      authRepository: DemoAuthRepository(),
      productRepository: DemoProductRepository(),
      checkoutRepository: const DemoCheckoutRepository(
        statusInterval: Duration(days: 1),
      ),
      mapProvider: const DevelopmentMapProvider(),
      locationService: const DevelopmentLocationService(),
      isDemoMode: true,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    controller.addProduct(controller.products.first);
    const PlaceSuggestion place = PlaceSuggestion(
      label: 'Região',
      referenceAddress: 'Endereço de referência',
      coordinate: GeoCoordinate(latitude: -23.1, longitude: -46.5),
    );
    controller.selectApproximatePlace(place);
    controller.updateExactCoordinate(
      const GeoCoordinate(latitude: -23.1001, longitude: -46.5001),
    );

    expect(await controller.submitOrder(), contains('área aberta'));

    controller.updateDeliveryDetails(
      instructions: 'Gramado aberto',
      safeArea: true,
    );
    expect(await controller.submitOrder(), isNull);
    expect(controller.order?.status, OrderStatus.pendingAdminApproval);
  });

  test('carrinho calcula quantidades e valores', () async {
    final AppController controller = AppController(
      authRepository: DemoAuthRepository(),
      productRepository: DemoProductRepository(),
      checkoutRepository: const DemoCheckoutRepository(),
      mapProvider: const DevelopmentMapProvider(),
      locationService: const DevelopmentLocationService(),
      isDemoMode: true,
    );
    addTearDown(controller.dispose);
    await controller.initialize();
    final product = controller.products.first;

    controller.addProduct(product);
    controller.addProduct(product);

    expect(controller.cartCount, 2);
    expect(controller.cartLines.single.quantity, 2);
    expect(controller.subtotal, product.price * 2);
    expect(controller.discount, 19.96);
    expect(controller.total, 87.34);
  });

  test(
    'modo integrado autentica antes do catálogo e bloqueia mapa fallback',
    () async {
      final AppController controller = AppController(
        authRepository: DemoAuthRepository(),
        productRepository: DemoProductRepository(),
        checkoutRepository: const DemoCheckoutRepository(),
        mapProvider: const DevelopmentMapProvider(fallbackForMapTiler: true),
        locationService: const DevelopmentLocationService(),
        isDemoMode: false,
      );
      addTearDown(controller.dispose);

      await controller.initialize();
      expect(controller.products, isEmpty);
      expect(
        await controller.login(
          email: 'cliente@teste.local',
          password: '12345678',
        ),
        isNull,
      );
      expect(controller.products, isNotEmpty);

      controller.addProduct(controller.products.first);
      controller.selectApproximatePlace(
        const PlaceSuggestion(
          label: 'Região',
          referenceAddress: 'Endereço',
          coordinate: GeoCoordinate(latitude: -23.1, longitude: -46.5),
        ),
      );
      controller.updateExactCoordinate(
        const GeoCoordinate(latitude: -23.1001, longitude: -46.5001),
      );
      controller.updateDeliveryDetails(instructions: '', safeArea: true);

      expect(await controller.submitOrder(), contains('MapTiler'));
      expect(controller.order, isNull);
    },
  );

  test('status desconhecido não vira aprovação pendente', () {
    expect(OrderStatusX.fromApi('NOVO_ESTADO'), OrderStatus.unknown);
  });

  test(
    'restaura pedido ativo e reabre acompanhamento sem aguardar eventos',
    () async {
      final _RestoringOrderRepository orders = _RestoringOrderRepository(
        activeOrder: const OrderSnapshot(
          id: 'pedido-ativo',
          status: OrderStatus.approved,
        ),
      );
      final AppController controller = AppController(
        authRepository: const _RestoringAuthRepository(),
        productRepository: DemoProductRepository(),
        checkoutRepository: const DemoCheckoutRepository(),
        orderRepository: orders,
        mapProvider: const DevelopmentMapProvider(),
        locationService: const DevelopmentLocationService(),
        isDemoMode: false,
      );
      addTearDown(() async {
        controller.dispose();
        await orders.close();
      });

      await controller.initialize().timeout(const Duration(seconds: 1));

      expect(controller.orders.activeOrders.single.id, 'pedido-ativo');
      expect(
        controller.orders.activeOrders.single.status,
        OrderStatus.approved,
      );
      expect(orders.watchedOrderId, 'pedido-ativo');
      expect(controller.approximatePlace, isNull);
      expect(controller.exactCoordinate, isNull);
      expect(controller.cartLines, isEmpty);

      orders.addUpdate(
        const OrderSnapshotEvent(
          OrderSnapshot(id: 'pedido-ativo', status: OrderStatus.inTransit),
        ),
      );
      await Future<void>.delayed(Duration.zero);

      expect(
        controller.orders.activeOrders.single.status,
        OrderStatus.inTransit,
      );
    },
  );

  test('falha ao recuperar pedido não invalida a sessão restaurada', () async {
    final _RestoringOrderRepository orders = _RestoringOrderRepository(
      error: StateError('API indisponível'),
    );
    final AppController controller = AppController(
      authRepository: const _RestoringAuthRepository(),
      productRepository: DemoProductRepository(),
      checkoutRepository: const DemoCheckoutRepository(),
      orderRepository: orders,
      mapProvider: const DevelopmentMapProvider(),
      locationService: const DevelopmentLocationService(),
      isDemoMode: false,
    );
    addTearDown(() async {
      controller.dispose();
      await orders.close();
    });

    await controller.initialize();

    expect(controller.isAuthenticated, isTrue);
    expect(controller.initializationError, isNull);
    expect(controller.order, isNull);
    expect(controller.orders.loadError, contains('API indisponível'));
    expect(orders.watchedOrderId, isNull);
  });
}

class _RestoringAuthRepository implements AuthRepository {
  const _RestoringAuthRepository();

  @override
  Future<void> clearSession() async {}

  @override
  Future<UserSession> login({required String email, required String password}) {
    throw UnimplementedError();
  }

  @override
  Future<UserSession> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<UserSession?> restoreSession() async => const UserSession(
    name: 'Cliente restaurado',
    email: 'cliente@teste.local',
  );
}

class _RestoringOrderRepository implements OrderRepository {
  _RestoringOrderRepository({this.activeOrder, this.error});

  final OrderSnapshot? activeOrder;
  final Object? error;
  final StreamController<OrderWatchEvent> _updates =
      StreamController<OrderWatchEvent>.broadcast();
  String? watchedOrderId;

  @override
  Future<OrderSnapshot> getOrder(String orderId) async {
    if (activeOrder case final OrderSnapshot order) return order;
    throw StateError('Pedido não encontrado');
  }

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) async {
    if (error case final Object value) throw value;
    final List<OrderSnapshot> items = activeOrder == null
        ? const <OrderSnapshot>[]
        : <OrderSnapshot>[activeOrder!];
    return OrdersPage(
      items: items,
      hasMore: false,
      returnedCount: items.length,
    );
  }

  @override
  Stream<OrderWatchEvent> watchOrder(String orderId) {
    watchedOrderId = orderId;
    return _updates.stream;
  }

  void addUpdate(OrderWatchEvent event) => _updates.add(event);

  Future<void> close() => _updates.close();
}
