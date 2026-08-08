import 'dart:async';

import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:drone_delivery_mobile/features/orders/application/orders_controller.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('prioriza ativos, ordena recentes e aplica filtros', () async {
    final _FakeOrderRepository repository = _FakeOrderRepository(
      orders: <OrderSnapshot>[
        _order('history-new', OrderStatus.completed, hour: 15),
        _order('active-old', OrderStatus.approved, hour: 12),
        _order('active-new', OrderStatus.inTransit, hour: 14),
      ],
    );
    final OrdersController controller = OrdersController(
      repository: repository,
    );
    addTearDown(() async {
      controller.dispose();
      await repository.close();
    });

    await controller.loadInitial();
    expect(controller.orders.map((OrderSnapshot order) => order.id), <String>[
      'active-new',
      'active-old',
      'history-new',
    ]);

    await controller.selectGroup(OrdersGroup.history);
    expect(controller.orders.single.id, 'history-new');
    expect(repository.requestedGroups.last, OrdersGroup.history);
  });

  test('carrega mais sem duplicar e respeita hasMore', () async {
    final _FakeOrderRepository repository = _FakeOrderRepository(
      orders: <OrderSnapshot>[
        _order('pedido-3', OrderStatus.completed, hour: 15),
        _order('pedido-2', OrderStatus.completed, hour: 14),
        _order('pedido-1', OrderStatus.completed, hour: 13),
      ],
    );
    final OrdersController controller = OrdersController(
      repository: repository,
      pageSize: 2,
    );
    addTearDown(() async {
      controller.dispose();
      await repository.close();
    });

    await controller.loadInitial();
    expect(controller.orders, hasLength(2));
    expect(controller.hasMore, isTrue);

    await controller.loadMore();
    expect(controller.orders, hasLength(3));
    expect(controller.hasMore, isFalse);
    expect(repository.requestedOffsets, <int>[0, 2]);
  });

  test('recuo de paginação evita pulo após atualização terminal', () async {
    final _FakeOrderRepository repository = _FakeOrderRepository(
      orders: <OrderSnapshot>[
        _order('pedido-4', OrderStatus.approved, hour: 16),
        _order('pedido-3', OrderStatus.approved, hour: 15),
        _order('pedido-2', OrderStatus.approved, hour: 14),
        _order('pedido-1', OrderStatus.approved, hour: 13),
      ],
    );
    final OrdersController controller = OrdersController(
      repository: repository,
      pageSize: 2,
    );
    addTearDown(() async {
      controller.dispose();
      await repository.close();
    });

    await controller.loadInitial();
    repository.emit(
      'pedido-4',
      OrderSnapshotEvent(_order('pedido-4', OrderStatus.completed, hour: 16)),
    );
    await Future<void>.delayed(Duration.zero);

    await controller.loadMore();

    expect(repository.requestedOffsets, <int>[0, 1]);
    expect(
      controller.activeOrders.map((OrderSnapshot order) => order.id),
      <String>['pedido-3', 'pedido-2', 'pedido-1'],
    );
    expect(controller.historyOrders.single.id, 'pedido-4');
  });

  test('ignora resposta antiga ao trocar filtros rapidamente', () async {
    final _DeferredOrderRepository repository = _DeferredOrderRepository();
    final OrdersController controller = OrdersController(
      repository: repository,
    );
    addTearDown(controller.dispose);

    final Future<void> activeRequest = controller.selectGroup(
      OrdersGroup.active,
    );
    await Future<void>.delayed(Duration.zero);
    final Future<void> historyRequest = controller.selectGroup(
      OrdersGroup.history,
    );
    await Future<void>.delayed(Duration.zero);

    repository.complete(OrdersGroup.history, <OrderSnapshot>[
      _order('historico', OrderStatus.completed, hour: 14),
    ]);
    await historyRequest;
    repository.complete(OrdersGroup.active, <OrderSnapshot>[
      _order('ativo-antigo', OrderStatus.approved, hour: 15),
    ]);
    await activeRequest;

    expect(controller.group, OrdersGroup.history);
    expect(controller.orders.single.id, 'historico');
    expect(controller.loadError, isNull);
  });

  test(
    'mantém snapshot, sinaliza offline e aplica atualização WebSocket',
    () async {
      final _FakeOrderRepository repository = _FakeOrderRepository(
        orders: <OrderSnapshot>[
          _order('pedido-ativo', OrderStatus.inTransit, hour: 15),
        ],
      );
      final OrdersController controller = OrdersController(
        repository: repository,
      );
      addTearDown(() async {
        controller.dispose();
        await repository.close();
      });
      await controller.loadInitial();

      repository.emit(
        'pedido-ativo',
        const OrderConnectionEvent(OrderRealtimeState.unavailable),
      );
      await Future<void>.delayed(Duration.zero);
      expect(controller.realtimeState, OrderRealtimeState.unavailable);
      expect(controller.activeOrders.single.status, OrderStatus.inTransit);

      repository.emit(
        'pedido-ativo',
        OrderSnapshotEvent(
          _order('pedido-ativo', OrderStatus.completed, hour: 16),
        ),
      );
      await Future<void>.delayed(Duration.zero);
      expect(controller.activeOrders, isEmpty);
      expect(controller.historyOrders.single.status, OrderStatus.completed);
    },
  );

  test(
    'busca detalhe mesmo com itens/ponto e preserva milestones no WebSocket',
    () async {
      final OrderSnapshot summary = _order(
        'pedido-ativo',
        OrderStatus.approved,
        hour: 15,
      );
      final OrderSnapshot detail = summary.copyWith(
        detailLoaded: true,
        milestones: <OrderMilestone>[
          OrderMilestone(
            eventType: 'ORDER_SUBMITTED',
            occurredAt: DateTime.utc(2026, 8, 8, 15),
          ),
        ],
      );
      final _FakeOrderRepository repository = _FakeOrderRepository(
        orders: <OrderSnapshot>[summary],
        detailOrders: <String, OrderSnapshot>{summary.id: detail},
      );
      final OrdersController controller = OrdersController(
        repository: repository,
      );
      addTearDown(() async {
        controller.dispose();
        await repository.close();
      });

      await controller.loadInitial();
      expect(controller.orderById(summary.id)?.hasDetails, isTrue);
      expect(controller.orderById(summary.id)?.detailLoaded, isFalse);

      await controller.loadDetails(summary.id);
      expect(repository.requestedDetails, <String>[summary.id]);
      expect(controller.orderById(summary.id)?.detailLoaded, isTrue);
      expect(controller.orderById(summary.id)?.milestones, hasLength(1));

      repository.emit(
        summary.id,
        OrderSnapshotEvent(_order(summary.id, OrderStatus.inTransit, hour: 16)),
      );
      await Future<void>.delayed(Duration.zero);

      final OrderSnapshot merged = controller.orderById(summary.id)!;
      expect(merged.status, OrderStatus.inTransit);
      expect(merged.detailLoaded, isTrue);
      expect(merged.milestones.single.eventType, 'ORDER_SUBMITTED');
    },
  );

  test('diferencia erro inicial e erro de propriedade no detalhe', () async {
    final _FakeOrderRepository repository = _FakeOrderRepository(
      listError: const ApiException(
        'API indisponível',
        isConnectivityFailure: true,
      ),
      detailError: const ApiException('Pedido não encontrado', statusCode: 404),
    );
    final OrdersController controller = OrdersController(
      repository: repository,
    );
    addTearDown(() async {
      controller.dispose();
      await repository.close();
    });

    await controller.loadInitial();
    expect(controller.hasLoaded, isFalse);
    expect(controller.loadError, 'API indisponível');
    expect(controller.isOffline, isTrue);

    await controller.loadDetails('pedido-alheio');
    expect(controller.detailError('pedido-alheio'), 'Pedido não encontrado');
  });
}

OrderSnapshot _order(String id, OrderStatus status, {required int hour}) {
  return OrderSnapshot(
    id: id,
    status: status,
    createdAt: DateTime.utc(2026, 8, 8, hour),
    total: 29.90,
    items: const <OrderLineSnapshot>[
      OrderLineSnapshot(
        id: 'item',
        productId: 'produto',
        productName: 'X-Burger',
        unitPrice: 29.90,
        quantity: 1,
        lineTotal: 29.90,
      ),
    ],
    deliveryPoint: const OrderDeliveryPointSnapshot(
      coordinate: GeoCoordinate(latitude: -22.9971, longitude: -46.5832),
    ),
  );
}

class _FakeOrderRepository implements OrderRepository {
  _FakeOrderRepository({
    List<OrderSnapshot> orders = const <OrderSnapshot>[],
    this.listError,
    this.detailError,
    this.detailOrders = const <String, OrderSnapshot>{},
  }) : orders = List<OrderSnapshot>.of(orders);

  final List<OrderSnapshot> orders;
  final Object? listError;
  final Object? detailError;
  final Map<String, OrderSnapshot> detailOrders;
  final List<OrdersGroup> requestedGroups = <OrdersGroup>[];
  final List<int> requestedOffsets = <int>[];
  final List<String> requestedDetails = <String>[];
  final Map<String, StreamController<OrderWatchEvent>> _streams =
      <String, StreamController<OrderWatchEvent>>{};

  @override
  Future<OrderSnapshot> getOrder(String orderId) async {
    requestedDetails.add(orderId);
    if (detailError case final Object error) throw error;
    if (detailOrders[orderId] case final OrderSnapshot detail) return detail;
    return orders.firstWhere((OrderSnapshot order) => order.id == orderId);
  }

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) async {
    requestedGroups.add(group);
    requestedOffsets.add(offset);
    if (listError case final Object error) throw error;
    final List<OrderSnapshot> filtered = orders
        .where((OrderSnapshot order) {
          return switch (group) {
            OrdersGroup.all => true,
            OrdersGroup.active => order.status.isActive,
            OrdersGroup.history => order.status.isTerminal,
          };
        })
        .toList(growable: false);
    final int end = (offset + limit).clamp(0, filtered.length);
    final List<OrderSnapshot> page = offset >= filtered.length
        ? const <OrderSnapshot>[]
        : filtered.sublist(offset, end);
    return OrdersPage(
      items: page,
      hasMore: end < filtered.length,
      returnedCount: page.length,
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

  void emit(String orderId, OrderWatchEvent event) {
    if (event case OrderSnapshotEvent(:final order)) {
      final int index = orders.indexWhere(
        (OrderSnapshot current) => current.id == order.id,
      );
      if (index >= 0) orders[index] = order;
      orders.sort((OrderSnapshot first, OrderSnapshot second) {
        if (first.status.isActive != second.status.isActive) {
          return first.status.isActive ? -1 : 1;
        }
        return second.createdAt!.compareTo(first.createdAt!);
      });
    }
    _streams[orderId]!.add(event);
  }

  Future<void> close() async {
    for (final StreamController<OrderWatchEvent> stream in _streams.values) {
      await stream.close();
    }
  }
}

class _DeferredOrderRepository implements OrderRepository {
  final Map<OrdersGroup, Completer<OrdersPage>> _requests =
      <OrdersGroup, Completer<OrdersPage>>{};

  @override
  Future<OrderSnapshot> getOrder(String orderId) {
    throw UnimplementedError();
  }

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) {
    final Completer<OrdersPage> request = Completer<OrdersPage>();
    _requests[group] = request;
    return request.future;
  }

  void complete(OrdersGroup group, List<OrderSnapshot> orders) {
    _requests[group]!.complete(
      OrdersPage(items: orders, hasMore: false, returnedCount: orders.length),
    );
  }

  @override
  Stream<OrderWatchEvent> watchOrder(String orderId) {
    return const Stream<OrderWatchEvent>.empty();
  }
}
