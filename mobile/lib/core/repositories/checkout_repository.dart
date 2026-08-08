import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../models/delivery_point.dart';
import '../models/order.dart';
import '../network/api_client.dart';

class CheckoutRequest {
  const CheckoutRequest({
    required this.lines,
    required this.deliveryPoint,
    required this.paymentMethod,
  });

  final List<CartLine> lines;
  final DeliveryPointDraft deliveryPoint;
  final SimulatedPaymentMethod paymentMethod;
}

abstract interface class CheckoutRepository {
  Future<OrderSnapshot?> findLatestActiveOrder();
  Future<OrderSnapshot> submit(CheckoutRequest request);
  Stream<OrderSnapshot> watchOrder(String orderId);
}

class DemoCheckoutRepository implements CheckoutRepository {
  const DemoCheckoutRepository({
    this.statusInterval = const Duration(seconds: 3),
  });

  final Duration statusInterval;

  @override
  Future<OrderSnapshot?> findLatestActiveOrder() async => null;

  @override
  Future<OrderSnapshot> submit(CheckoutRequest request) async {
    await Future<void>.delayed(const Duration(milliseconds: 450));
    return OrderSnapshot(
      id: 'DEMO-${DateTime.now().millisecondsSinceEpoch}',
      status: OrderStatus.pendingAdminApproval,
      lastEventAt: DateTime.now().toUtc(),
    );
  }

  @override
  Stream<OrderSnapshot> watchOrder(String orderId) async* {
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
    for (final OrderStatus status in progression) {
      await Future<void>.delayed(statusInterval);
      yield OrderSnapshot(
        id: orderId,
        status: status,
        lastEventAt: DateTime.now().toUtc(),
      );
    }
  }
}

class ApiCheckoutRepository implements CheckoutRepository {
  ApiCheckoutRepository(this._client);

  final ApiClient _client;
  String? _attemptKey;
  String? _attemptFingerprint;

  @override
  Future<OrderSnapshot?> findLatestActiveOrder() async {
    const int pageSize = 100;
    int offset = 0;
    while (true) {
      final Object? response = await _client.get(
        '/api/v1/orders?limit=$pageSize&offset=$offset',
      );
      if (response is! List) {
        throw const ApiException('Lista de pedidos inválida recebida da API.');
      }

      for (final Object? item in response) {
        final OrderSnapshot snapshot = OrderSnapshot.fromJson(
          expectJsonMap(item),
        );
        if (snapshot.id.trim().isEmpty) {
          throw const ApiException(
            'A API retornou um pedido sem identificador.',
          );
        }
        if (snapshot.status != OrderStatus.draft &&
            !snapshot.status.isTerminal) {
          return snapshot;
        }
      }
      if (response.length < pageSize) return null;
      offset += pageSize;
    }
  }

  @override
  Future<OrderSnapshot> submit(CheckoutRequest request) async {
    final DeliveryPointDraft point = request.deliveryPoint;
    final GeoCoordinate approximateCoordinate =
        point.approximatePlace.coordinate!;
    final bool hasAddress =
        point.approximatePlace.referenceAddress.trim().isNotEmpty &&
        point.approximatePlace.referenceAddress !=
            'Local sem endereço identificado';
    final Map<String, Object?> pointPayload = <String, Object?>{
      'searched_address': hasAddress
          ? point.approximatePlace.referenceAddress
          : null,
      'address_reference': hasAddress
          ? point.approximatePlace.referenceAddress
          : null,
      'selection_source': 'MANUAL_MAP_SELECTION',
      'approximate_latitude': approximateCoordinate.latitude,
      'approximate_longitude': approximateCoordinate.longitude,
      'final_latitude': point.finalCoordinate.latitude,
      'final_longitude': point.finalCoordinate.longitude,
      'label': point.approximatePlace.label,
      'instructions': point.instructions,
      'map_provider': point.mapProvider,
      'map_type': 'hybrid',
      'region_confirmed': true,
      'exact_point_selected': true,
      'user_confirmed': true,
      'user_confirmed_safe_area': point.safeAreaConfirmed,
    };

    final Map<String, Object?> orderPayload = <String, Object?>{
      'payment_method': request.paymentMethod.apiValue,
      'items': request.lines
          .map<Map<String, Object?>>(
            (CartLine line) => <String, Object?>{
              'product_id': line.productId,
              'quantity': line.quantity,
            },
          )
          .toList(growable: false),
    };
    final String fingerprint = jsonEncode(<String, Object?>{
      'point': pointPayload,
      'order': orderPayload,
    });
    if (_attemptFingerprint != fingerprint || _attemptKey == null) {
      _attemptFingerprint = fingerprint;
      _attemptKey = _newAttemptKey();
    }
    final String attemptKey = _attemptKey!;

    await _client.post(
      '/api/v1/delivery-points/validate',
      body: pointPayload,
      headers: <String, String>{'Idempotency-Key': '$attemptKey:validate'},
    );
    final Map<String, Object?> pointResponse = expectJsonMap(
      await _client.post(
        '/api/v1/delivery-points',
        body: pointPayload,
        headers: <String, String>{'Idempotency-Key': '$attemptKey:point'},
      ),
    );
    final String deliveryPointId = pointResponse['id'].toString();

    final Map<String, Object?> orderResponse = expectJsonMap(
      await _client.post(
        '/api/v1/orders',
        body: <String, Object?>{
          'delivery_point_id': deliveryPointId,
          ...orderPayload,
        },
        headers: <String, String>{'Idempotency-Key': '$attemptKey:order'},
      ),
    );
    final String orderId = orderResponse['id'].toString();
    final Map<String, Object?> submitted = expectJsonMap(
      await _client.post(
        '/api/v1/orders/$orderId/submit',
        headers: <String, String>{'Idempotency-Key': '$attemptKey:submit'},
      ),
    );
    _attemptKey = null;
    _attemptFingerprint = null;
    return OrderSnapshot.fromJson(submitted);
  }

  @override
  Stream<OrderSnapshot> watchOrder(String orderId) async* {
    int consecutiveFailures = 0;
    while (true) {
      final String? token = _client.accessToken;
      if (token != null) {
        try {
          await for (final OrderSnapshot snapshot in _watchSocket(
            orderId,
            token,
          )) {
            consecutiveFailures = 0;
            yield snapshot;
            if (snapshot.status.isTerminal) return;
          }
        } on Object {
          consecutiveFailures++;
        }
      }

      final int delaySeconds = consecutiveFailures == 0
          ? 3
          : min(30, 1 << min(consecutiveFailures, 5));
      await Future<void>.delayed(Duration(seconds: delaySeconds));
      try {
        final OrderSnapshot snapshot = OrderSnapshot.fromJson(
          expectJsonMap(await _client.get('/api/v1/orders/$orderId')),
        );
        consecutiveFailures = 0;
        yield snapshot;
        if (snapshot.status.isTerminal) return;
      } on ApiException catch (error) {
        if (error.statusCode == 401 ||
            error.statusCode == 403 ||
            error.statusCode == 404) {
          rethrow;
        }
        consecutiveFailures++;
      }
    }
  }

  Stream<OrderSnapshot> _watchSocket(String orderId, String token) async* {
    final Uri apiUri = Uri.parse(_client.baseUrl);
    final Uri socketUri = apiUri
        .resolve('/api/v1/ws/orders/$orderId')
        .replace(scheme: apiUri.scheme == 'https' ? 'wss' : 'ws');
    final WebSocketChannel socket = WebSocketChannel.connect(socketUri);
    await socket.ready.timeout(const Duration(seconds: 10));
    socket.sink.add(
      jsonEncode(<String, Object?>{'type': 'AUTH', 'token': token}),
    );
    final Timer heartbeat = Timer.periodic(const Duration(seconds: 15), (_) {
      socket.sink.add('ping');
    });
    try {
      await for (final Object? rawMessage in socket.stream.timeout(
        const Duration(seconds: 35),
      )) {
        if (rawMessage is! String) continue;
        final Object? decoded = jsonDecode(rawMessage);
        if (decoded is! Map) continue;
        final Map<String, Object?> message = decoded.map<String, Object?>(
          (Object? key, Object? value) =>
              MapEntry<String, Object?>(key.toString(), value),
        );
        final String type = message['type']?.toString() ?? '';
        if (type == 'pong') continue;
        if (type == 'order.snapshot' || type == 'order.status') {
          yield OrderSnapshot.fromJson(expectJsonMap(message['data']));
        } else if (type == 'mission.status') {
          yield OrderSnapshot.fromJson(
            expectJsonMap(await _client.get('/api/v1/orders/$orderId')),
          );
        }
      }
    } finally {
      heartbeat.cancel();
      await socket.sink.close();
    }
  }

  static String _newAttemptKey() {
    final Random random = Random.secure();
    final String entropy = List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((int value) => value.toRadixString(16).padLeft(2, '0')).join();
    return 'mobile-checkout-$entropy';
  }
}
