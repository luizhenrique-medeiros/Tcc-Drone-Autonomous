import 'dart:convert';
import 'dart:math';

import '../models/delivery_point.dart';
import '../models/order.dart';
import '../network/api_client.dart';
import 'order_repository.dart';

class CheckoutRequest {
  const CheckoutRequest({
    required this.lines,
    required this.deliveryPoint,
    required this.paymentMethod,
    this.savedLocationId,
    this.savedLocationReviewConfirmed = false,
    this.savedLocationSafeAreaConfirmed = false,
  });

  final List<CartLine> lines;
  final DeliveryPointDraft deliveryPoint;
  final SimulatedPaymentMethod paymentMethod;
  final String? savedLocationId;
  final bool savedLocationReviewConfirmed;
  final bool savedLocationSafeAreaConfirmed;
}

abstract interface class CheckoutRepository {
  Future<OrderSnapshot> submit(CheckoutRequest request);
}

class DemoCheckoutRepository implements CheckoutRepository {
  const DemoCheckoutRepository({
    this.statusInterval = const Duration(seconds: 3),
    this.orderStore,
  });

  final Duration statusInterval;
  final DemoOrderStore? orderStore;

  @override
  Future<OrderSnapshot> submit(CheckoutRequest request) async {
    await Future<void>.delayed(const Duration(milliseconds: 450));
    final DateTime now = DateTime.now().toUtc();
    final double subtotal = request.lines.fold<double>(
      0,
      (double total, CartLine line) => total + line.total,
    );
    final double deliveryFee = request.lines.isEmpty ? 0 : 7.50;
    final double discount = _money(subtotal * 0.20);
    final OrderSnapshot order = OrderSnapshot(
      id: 'DEMO-${DateTime.now().millisecondsSinceEpoch}',
      status: OrderStatus.pendingAdminApproval,
      paymentMethod: request.paymentMethod,
      subtotal: _money(subtotal),
      deliveryFee: deliveryFee,
      discount: discount,
      total: _money(subtotal + deliveryFee - discount),
      items: request.lines
          .map<OrderLineSnapshot>(
            (CartLine line) => OrderLineSnapshot(
              id: 'demo-item-${line.productId}',
              productId: line.productId,
              productName: line.name,
              unitPrice: line.unitPrice,
              quantity: line.quantity,
              lineTotal: line.total,
            ),
          )
          .toList(growable: false),
      deliveryPoint: OrderDeliveryPointSnapshot(
        coordinate: request.deliveryPoint.finalCoordinate,
        label: request.deliveryPoint.approximatePlace.label,
        referenceAddress:
            request.deliveryPoint.approximatePlace.referenceAddress,
        instructions: request.deliveryPoint.instructions,
      ),
      submittedAt: now,
      createdAt: now,
      updatedAt: now,
      lastEventAt: now,
      milestones: <OrderMilestone>[
        OrderMilestone(eventType: 'ORDER_CREATED', occurredAt: now),
        OrderMilestone(eventType: 'ORDER_SUBMITTED', occurredAt: now),
      ],
    );
    orderStore?.save(order);
    return order;
  }
}

class ApiCheckoutRepository implements CheckoutRepository {
  ApiCheckoutRepository(this._client);

  final ApiClient _client;
  String? _attemptKey;
  String? _attemptFingerprint;

  @override
  Future<OrderSnapshot> submit(CheckoutRequest request) async {
    final DeliveryPointDraft point = request.deliveryPoint;
    final GeoCoordinate approximateCoordinate =
        point.approximatePlace.coordinate!;
    final String searchedAddress = point.approximatePlace.referenceAddress;
    final String? finalAddress = point.addressReference?.trim();
    final bool hasSearchedAddress =
        searchedAddress.trim().isNotEmpty &&
        searchedAddress != 'Local sem endereço identificado';
    final bool hasFinalAddress =
        finalAddress != null &&
        finalAddress.isNotEmpty &&
        finalAddress != 'Local sem endereço identificado';
    final Map<String, Object?> pointPayload = <String, Object?>{
      'searched_address': hasSearchedAddress ? searchedAddress : null,
      'address_reference': hasFinalAddress ? finalAddress : null,
      'selection_source': 'MANUAL_MAP_SELECTION',
      'approximate_latitude': approximateCoordinate.latitude,
      'approximate_longitude': approximateCoordinate.longitude,
      'final_latitude': point.finalCoordinate.latitude,
      'final_longitude': point.finalCoordinate.longitude,
      'label': point.approximatePlace.label,
      'instructions': point.instructions,
      'map_provider': point.mapProvider,
      'map_type': point.mapType,
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
      'saved_location_id': request.savedLocationId,
      'saved_location_review_confirmed': request.savedLocationReviewConfirmed,
      'saved_location_safe_area_confirmed':
          request.savedLocationSafeAreaConfirmed,
    });
    if (_attemptFingerprint != fingerprint || _attemptKey == null) {
      _attemptFingerprint = fingerprint;
      _attemptKey = _newAttemptKey();
    }
    final String attemptKey = _attemptKey!;
    String? deliveryPointId;
    if (request.savedLocationId == null) {
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
      deliveryPointId = pointResponse['id'].toString();
    }

    final Map<String, Object?> orderResponse = expectJsonMap(
      await _client.post(
        '/api/v1/orders',
        body: <String, Object?>{
          if (request.savedLocationId
              case final String savedLocationId) ...<String, Object?>{
            'saved_location_id': savedLocationId,
            'saved_location_review_confirmed':
                request.savedLocationReviewConfirmed,
            'saved_location_safe_area_confirmed':
                request.savedLocationSafeAreaConfirmed,
          } else
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

  static String _newAttemptKey() {
    final Random random = Random.secure();
    final String entropy = List<int>.generate(
      16,
      (_) => random.nextInt(256),
    ).map((int value) => value.toRadixString(16).padLeft(2, '0')).join();
    return 'mobile-checkout-$entropy';
  }
}

double _money(double value) => (value * 100).roundToDouble() / 100;
