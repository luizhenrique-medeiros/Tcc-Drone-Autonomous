import 'dart:convert';

import 'package:drone_delivery_mobile/core/models/mission_telemetry.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('lista usa group, limit e offset e informa próxima página', () async {
    late Uri requestedUri;
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((http.Request request) async {
        requestedUri = request.url;
        return http.Response(
          jsonEncode(<Map<String, Object?>>[
            _orderJson(id: 'pedido-1', status: 'IN_TRANSIT'),
            _orderJson(id: 'pedido-2', status: 'APPROVED'),
          ]),
          200,
        );
      }),
    );
    addTearDown(client.close);

    final OrdersPage page = await ApiOrderRepository(
      client,
    ).listOrders(group: OrdersGroup.active, limit: 2, offset: 4);

    expect(requestedUri.path, '/api/v1/orders');
    expect(requestedUri.queryParameters, <String, String>{
      'group': 'active',
      'limit': '2',
      'offset': '4',
    });
    expect(page.items, hasLength(2));
    expect(page.hasMore, isTrue);
    expect(page.returnedCount, 2);
  });

  test('WebSocket autentica e entrega snapshot terminal', () async {
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((_) async => http.Response('{}', 200)),
    )..accessToken = 'token-de-teste';
    addTearDown(client.close);
    final _FakeOrderSocket socket = _FakeOrderSocket(<Object?>[
      jsonEncode(<String, Object?>{
        'type': 'order.snapshot',
        'data': _orderJson(id: 'pedido-1', status: 'COMPLETED'),
      }),
    ]);
    final ApiOrderRepository repository = ApiOrderRepository(
      client,
      socketConnector: (_) => socket,
      heartbeatInterval: const Duration(days: 1),
    );

    final List<OrderWatchEvent> events = await repository
        .watchOrder('pedido-1')
        .toList();

    expect(socket.sentMessages.single, contains('token-de-teste'));
    expect(
      events.whereType<OrderConnectionEvent>().map((event) => event.state),
      contains(OrderRealtimeState.connected),
    );
    expect(
      events.whereType<OrderSnapshotEvent>().single.order.status,
      OrderStatus.completed,
    );
    expect(socket.closed, isTrue);
  });

  test(
    'WebSocket entrega telemetria e VERIFIED sem derivar status do pedido',
    () async {
      int detailRequests = 0;
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          detailRequests++;
          expect(request.url.path, '/api/v1/orders/pedido-1');
          return http.Response(
            jsonEncode(<String, Object?>{
              ..._orderJson(id: 'pedido-1', status: 'COMPLETED'),
              'milestones': <Object?>[],
            }),
            200,
          );
        }),
      )..accessToken = 'token-de-teste';
      addTearDown(client.close);
      final _FakeOrderSocket socket = _FakeOrderSocket(<Object?>[
        jsonEncode(<String, Object?>{
          'type': 'mission.telemetry',
          'data': <String, Object?>{
            'mission_id': 'mission-1',
            'latitude': -23.11872,
            'longitude': -46.58131,
            'source': 'HARDWARE_REAL',
            'recorded_at': '2026-08-17T10:00:00Z',
            'received_at': '2026-08-17T10:00:01Z',
            'is_stale': false,
          },
        }),
        jsonEncode(<String, Object?>{
          'type': 'mission.status',
          'data': <String, Object?>{
            'id': 'mission-1',
            'order_id': 'pedido-1',
            'status': 'VERIFIED',
            'updated_at': '2026-08-17T10:00:02Z',
          },
        }),
      ]);
      final ApiOrderRepository repository = ApiOrderRepository(
        client,
        socketConnector: (_) => socket,
        heartbeatInterval: const Duration(days: 1),
      );

      final List<OrderWatchEvent> events = await repository
          .watchOrder('pedido-1')
          .toList();

      final MissionTelemetrySnapshot telemetry = events
          .whereType<MissionTelemetryEvent>()
          .single
          .telemetry;
      expect(telemetry.latitude, -23.11872);
      expect(telemetry.source, TelemetrySource.hardwareReal);
      expect(
        events.whereType<MissionStatusEvent>().single.mission.status,
        MissionStatus.verified,
      );
      expect(
        events.whereType<OrderSnapshotEvent>().single.order.status,
        OrderStatus.completed,
      );
      expect(detailRequests, 1);
      expect(socket.closed, isTrue);
    },
  );

  test(
    'falha do WebSocket usa polling e preserva pedido até recuperar',
    () async {
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          expect(request.url.path, '/api/v1/orders/pedido-1');
          return http.Response(
            jsonEncode(<String, Object?>{
              ..._orderJson(id: 'pedido-1', status: 'COMPLETED'),
              'milestones': <Object?>[],
            }),
            200,
          );
        }),
      )..accessToken = 'token-de-teste';
      addTearDown(client.close);
      int delayCalls = 0;
      final _FailingOrderSocket socket = _FailingOrderSocket();
      final ApiOrderRepository repository = ApiOrderRepository(
        client,
        socketConnector: (_) => socket,
        retryDelay: (_) => Duration.zero,
        delay: (_) async {
          delayCalls++;
        },
      );

      final List<OrderWatchEvent> events = await repository
          .watchOrder('pedido-1')
          .toList();

      expect(delayCalls, 1);
      expect(
        events.whereType<OrderConnectionEvent>().map((event) => event.state),
        contains(OrderRealtimeState.reconnecting),
      );
      final OrderSnapshot recovered = events
          .whereType<OrderSnapshotEvent>()
          .single
          .order;
      expect(recovered.status, OrderStatus.completed);
      expect(recovered.detailLoaded, isTrue);
      expect(socket.closed, isTrue);
    },
  );

  test('erro de propriedade do detalhe é preservado', () async {
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((_) async {
        return http.Response(
          jsonEncode(<String, Object?>{'detail': 'Pedido não encontrado'}),
          404,
        );
      }),
    );
    addTearDown(client.close);

    expect(
      () => ApiOrderRepository(client).getOrder('pedido-alheio'),
      throwsA(
        isA<ApiException>()
            .having((ApiException error) => error.statusCode, 'status', 404)
            .having(
              (ApiException error) => error.message,
              'mensagem',
              'Pedido não encontrado',
            ),
      ),
    );
  });
}

Map<String, Object?> _orderJson({required String id, required String status}) {
  return <String, Object?>{
    'id': id,
    'status': status,
    'created_at': '2026-08-08T12:00:00Z',
    'items': <Object?>[],
  };
}

class _FakeOrderSocket implements OrderSocket {
  _FakeOrderSocket(List<Object?> messages)
    : _stream = Stream<Object?>.fromIterable(messages);

  final Stream<Object?> _stream;
  final List<Object> sentMessages = <Object>[];
  bool closed = false;

  @override
  Future<void> get ready async {}

  @override
  Stream<Object?> get stream => _stream;

  @override
  void add(Object message) => sentMessages.add(message);

  @override
  Future<void> close() async => closed = true;
}

class _FailingOrderSocket implements OrderSocket {
  bool closed = false;

  @override
  Future<void> get ready => Future<void>.error(StateError('offline'));

  @override
  Stream<Object?> get stream => const Stream<Object?>.empty();

  @override
  void add(Object message) {}

  @override
  Future<void> close() async => closed = true;
}
