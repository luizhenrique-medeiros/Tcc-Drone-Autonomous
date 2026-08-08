import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/order.dart';
import '../network/api_client.dart';

class OrdersPage {
  const OrdersPage({
    required this.items,
    required this.hasMore,
    required this.returnedCount,
  });

  final List<OrderSnapshot> items;
  final bool hasMore;
  final int returnedCount;
}

enum OrderRealtimeState { connecting, connected, reconnecting, unavailable }

sealed class OrderWatchEvent {
  const OrderWatchEvent();
}

class OrderSnapshotEvent extends OrderWatchEvent {
  const OrderSnapshotEvent(this.order);

  final OrderSnapshot order;
}

class OrderConnectionEvent extends OrderWatchEvent {
  const OrderConnectionEvent(this.state);

  final OrderRealtimeState state;
}

abstract interface class OrderRepository {
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  });

  Future<OrderSnapshot> getOrder(String orderId);

  Stream<OrderWatchEvent> watchOrder(String orderId);
}

abstract interface class OrderSocket {
  Future<void> get ready;
  Stream<Object?> get stream;
  void add(Object message);
  Future<void> close();
}

typedef OrderSocketConnector = OrderSocket Function(Uri uri);
typedef OrderRetryDelay = Duration Function(int consecutiveFailures);
typedef OrderDelay = Future<void> Function(Duration duration);

class WebSocketOrderSocket implements OrderSocket {
  WebSocketOrderSocket(Uri uri) : _channel = WebSocketChannel.connect(uri);

  final WebSocketChannel _channel;

  @override
  Future<void> get ready => _channel.ready;

  @override
  Stream<Object?> get stream => _channel.stream;

  @override
  void add(Object message) => _channel.sink.add(message);

  @override
  Future<void> close() async => _channel.sink.close();
}

class ApiOrderRepository implements OrderRepository {
  ApiOrderRepository(
    this._client, {
    OrderSocketConnector? socketConnector,
    OrderRetryDelay? retryDelay,
    OrderDelay? delay,
    this.socketReadyTimeout = const Duration(seconds: 10),
    this.socketIdleTimeout = const Duration(seconds: 35),
    this.heartbeatInterval = const Duration(seconds: 15),
  }) : _socketConnector = socketConnector ?? WebSocketOrderSocket.new,
       _retryDelay = retryDelay ?? _defaultRetryDelay,
       _delay = delay ?? Future<void>.delayed;

  final ApiClient _client;
  final OrderSocketConnector _socketConnector;
  final OrderRetryDelay _retryDelay;
  final OrderDelay _delay;
  final Duration socketReadyTimeout;
  final Duration socketIdleTimeout;
  final Duration heartbeatInterval;

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) async {
    final Object? response = await _client.get(
      '/api/v1/orders?group=${group.apiValue}&limit=$limit&offset=$offset',
    );
    if (response is! List) {
      throw const ApiException('Lista de pedidos inválida recebida da API.');
    }
    final List<OrderSnapshot> orders = response
        .map<OrderSnapshot>((Object? item) {
          final OrderSnapshot order = OrderSnapshot.fromJson(
            expectJsonMap(item),
          );
          if (order.id.trim().isEmpty) {
            throw const ApiException(
              'A API retornou um pedido sem identificador.',
            );
          }
          return order;
        })
        .toList(growable: false);
    return OrdersPage(
      items: orders,
      hasMore: response.length == limit,
      returnedCount: response.length,
    );
  }

  @override
  Future<OrderSnapshot> getOrder(String orderId) async {
    final OrderSnapshot order = OrderSnapshot.fromJson(
      expectJsonMap(await _client.get('/api/v1/orders/$orderId')),
    );
    if (order.id.trim().isEmpty) {
      throw const ApiException('A API retornou um pedido sem identificador.');
    }
    return order;
  }

  @override
  Stream<OrderWatchEvent> watchOrder(String orderId) async* {
    int consecutiveFailures = 0;
    while (true) {
      yield OrderConnectionEvent(
        consecutiveFailures == 0
            ? OrderRealtimeState.connecting
            : OrderRealtimeState.reconnecting,
      );
      final String? token = _client.accessToken;
      if (token != null) {
        try {
          await for (final OrderWatchEvent event in _watchSocket(
            orderId,
            token,
          )) {
            if (event case OrderSnapshotEvent(:final order)) {
              consecutiveFailures = 0;
              yield event;
              if (order.status.isTerminal) return;
            } else {
              yield event;
            }
          }
          consecutiveFailures++;
        } on Object {
          consecutiveFailures++;
        }
      } else {
        consecutiveFailures++;
      }

      yield const OrderConnectionEvent(OrderRealtimeState.reconnecting);
      await _delay(_retryDelay(consecutiveFailures));
      try {
        final OrderSnapshot snapshot = await getOrder(orderId);
        consecutiveFailures = 0;
        yield OrderSnapshotEvent(snapshot);
        if (snapshot.status.isTerminal) return;
        yield const OrderConnectionEvent(OrderRealtimeState.unavailable);
      } on ApiException catch (error) {
        yield const OrderConnectionEvent(OrderRealtimeState.unavailable);
        if (error.statusCode == 401 ||
            error.statusCode == 403 ||
            error.statusCode == 404) {
          rethrow;
        }
        consecutiveFailures++;
      }
    }
  }

  Stream<OrderWatchEvent> _watchSocket(String orderId, String token) async* {
    final Uri apiUri = Uri.parse(_client.baseUrl);
    final Uri socketUri = apiUri
        .resolve('/api/v1/ws/orders/$orderId')
        .replace(scheme: apiUri.scheme == 'https' ? 'wss' : 'ws');
    final OrderSocket socket = _socketConnector(socketUri);
    Timer? heartbeat;
    try {
      await socket.ready.timeout(socketReadyTimeout);
      socket.add(jsonEncode(<String, Object?>{'type': 'AUTH', 'token': token}));
      heartbeat = Timer.periodic(heartbeatInterval, (_) {
        socket.add('ping');
      });
      bool connectedReported = false;
      await for (final Object? rawMessage in socket.stream.timeout(
        socketIdleTimeout,
      )) {
        if (rawMessage is! String) continue;
        final Object? decoded = jsonDecode(rawMessage);
        if (decoded is! Map) continue;
        final Map<String, Object?> message = decoded.map<String, Object?>(
          (Object? key, Object? value) =>
              MapEntry<String, Object?>(key.toString(), value),
        );
        final String type = message['type']?.toString() ?? '';
        if (!connectedReported) {
          connectedReported = true;
          yield const OrderConnectionEvent(OrderRealtimeState.connected);
        }
        if (type == 'pong') continue;
        if (type == 'order.snapshot' || type == 'order.status') {
          yield OrderSnapshotEvent(
            OrderSnapshot.fromJson(expectJsonMap(message['data'])),
          );
        } else if (type == 'mission.status') {
          yield OrderSnapshotEvent(await getOrder(orderId));
        }
      }
    } finally {
      heartbeat?.cancel();
      await socket.close();
    }
  }

  static Duration _defaultRetryDelay(int consecutiveFailures) {
    if (consecutiveFailures <= 0) return const Duration(seconds: 3);
    return Duration(seconds: min(30, 1 << min(consecutiveFailures, 5)));
  }
}

class DemoOrderStore {
  DemoOrderStore({this.statusInterval = const Duration(seconds: 3)});

  final Duration statusInterval;
  final Map<String, OrderSnapshot> _orders = <String, OrderSnapshot>{};

  void save(OrderSnapshot order) => _orders[order.id] = order;

  OrderSnapshot? find(String orderId) => _orders[orderId];

  List<OrderSnapshot> list(OrdersGroup group) {
    final List<OrderSnapshot> orders = _orders.values
        .where((OrderSnapshot order) {
          if (order.status == OrderStatus.draft) return false;
          return switch (group) {
            OrdersGroup.all => true,
            OrdersGroup.active => order.status.isActive,
            OrdersGroup.history => order.status.isTerminal,
          };
        })
        .toList(growable: false);
    orders.sort(_compareNewestFirst);
    return orders;
  }
}

class DemoOrderRepository implements OrderRepository {
  DemoOrderRepository([DemoOrderStore? store])
    : _store = store ?? DemoOrderStore();

  final DemoOrderStore _store;

  @override
  Future<OrdersPage> listOrders({
    required OrdersGroup group,
    required int limit,
    required int offset,
  }) async {
    final List<OrderSnapshot> all = _store.list(group);
    final int end = min(all.length, offset + limit);
    final List<OrderSnapshot> page = offset >= all.length
        ? const <OrderSnapshot>[]
        : all.sublist(offset, end);
    return OrdersPage(
      items: page,
      hasMore: end < all.length,
      returnedCount: page.length,
    );
  }

  @override
  Future<OrderSnapshot> getOrder(String orderId) async {
    OrderSnapshot? order = _store.find(orderId);
    if (order == null) {
      throw const ApiException('Pedido não encontrado.', statusCode: 404);
    }
    if (!order.detailLoaded) {
      order = order.copyWith(detailLoaded: true);
      _store.save(order);
    }
    return order;
  }

  @override
  Stream<OrderWatchEvent> watchOrder(String orderId) async* {
    OrderSnapshot current = await getOrder(orderId);
    yield const OrderConnectionEvent(OrderRealtimeState.connected);
    const List<OrderStatus> progression = <OrderStatus>[
      OrderStatus.approved,
      OrderStatus.missionPreparing,
      OrderStatus.missionReady,
      OrderStatus.waitingFlightAuthorization,
      OrderStatus.missionUploading,
      OrderStatus.inTransit,
      OrderStatus.atDestination,
      OrderStatus.delivered,
      OrderStatus.returning,
      OrderStatus.completed,
    ];
    final int currentIndex = progression.indexOf(current.status);
    final int start = current.status == OrderStatus.pendingAdminApproval
        ? 0
        : max(0, currentIndex + 1);
    for (int index = start; index < progression.length; index++) {
      await Future<void>.delayed(_store.statusInterval);
      current = current.copyWith(
        status: progression[index],
        lastEventAt: DateTime.now().toUtc(),
      );
      _store.save(current);
      yield OrderSnapshotEvent(current);
    }
  }
}

int _compareNewestFirst(OrderSnapshot first, OrderSnapshot second) {
  final DateTime firstDate =
      first.displayDate ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
  final DateTime secondDate =
      second.displayDate ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
  return secondDate.compareTo(firstDate);
}
