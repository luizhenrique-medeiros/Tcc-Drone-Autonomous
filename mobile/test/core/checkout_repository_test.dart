import 'dart:convert';

import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('checkout demo preserva dados para lista e detalhe', () async {
    final DemoOrderStore store = DemoOrderStore(
      statusInterval: const Duration(days: 1),
    );
    final DemoCheckoutRepository checkout = DemoCheckoutRepository(
      orderStore: store,
    );
    final OrderSnapshot submitted = await checkout.submit(
      CheckoutRequest(
        lines: const <CartLine>[
          CartLine(
            productId: 'produto-1',
            name: 'X-Burger',
            unitPrice: 34.90,
            quantity: 1,
          ),
        ],
        deliveryPoint: DeliveryPointDraft(
          approximatePlace: const PlaceSuggestion(
            label: 'Destino',
            referenceAddress: 'Endereço de referência',
            coordinate: GeoCoordinate(latitude: -23, longitude: -46),
          ),
          finalCoordinate: const GeoCoordinate(
            latitude: -23.0001,
            longitude: -46.0001,
          ),
          instructions: 'Gramado aberto',
          safeAreaConfirmed: true,
          mapProvider: 'development',
        ),
        paymentMethod: SimulatedPaymentMethod.pix,
      ),
    );

    final OrdersPage page = await DemoOrderRepository(
      store,
    ).listOrders(group: OrdersGroup.all, limit: 20, offset: 0);
    expect(page.items.single.id, submitted.id);
    expect(page.items.single.items.single.productName, 'X-Burger');
    expect(page.items.single.deliveryPoint?.instructions, 'Gramado aberto');
    expect(page.items.single.total, 35.42);
  });

  test(
    'ponto manual preserva endereço, tipo de mapa e omite flags de local salvo',
    () async {
      final List<String> requestedPaths = <String>[];
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          requestedPaths.add(request.url.path);
          final Map<String, Object?> body = request.body.isEmpty
              ? <String, Object?>{}
              : (jsonDecode(request.body) as Map).map<String, Object?>(
                  (Object? key, Object? value) =>
                      MapEntry<String, Object?>(key.toString(), value),
                );
          if (request.url.path == '/api/v1/delivery-points/validate') {
            expect(body['searched_address'], 'Rua pesquisada, 10');
            expect(body['address_reference'], isNull);
            expect(body['map_provider'], 'maptiler');
            expect(body['map_type'], 'satellite');
            expect(body['user_confirmed_safe_area'], isTrue);
            return http.Response(jsonEncode(<String, Object?>{}), 200);
          }
          if (request.url.path == '/api/v1/delivery-points') {
            expect(body['address_reference'], isNull);
            return http.Response(
              jsonEncode(<String, Object?>{'id': 'point-1'}),
              201,
            );
          }
          if (request.url.path == '/api/v1/orders') {
            expect(body['delivery_point_id'], 'point-1');
            expect(body.containsKey('saved_location_id'), isFalse);
            expect(
              body.containsKey('saved_location_review_confirmed'),
              isFalse,
            );
            expect(
              body.containsKey('saved_location_safe_area_confirmed'),
              isFalse,
            );
            return http.Response(
              jsonEncode(<String, Object?>{'id': 'order-1'}),
              201,
            );
          }
          expect(request.url.path, '/api/v1/orders/order-1/submit');
          return http.Response(
            jsonEncode(<String, Object?>{
              'id': 'order-1',
              'status': 'PENDING_ADMIN_APPROVAL',
              'created_at': '2026-08-09T12:00:00Z',
              'items': <Object?>[],
            }),
            200,
          );
        }),
      );
      addTearDown(client.close);

      await ApiCheckoutRepository(client).submit(
        CheckoutRequest(
          lines: const <CartLine>[
            CartLine(
              productId: 'product-1',
              name: 'Produto',
              unitPrice: 10,
              quantity: 1,
            ),
          ],
          deliveryPoint: DeliveryPointDraft(
            approximatePlace: const PlaceSuggestion(
              label: 'Região pesquisada',
              referenceAddress: 'Rua pesquisada, 10',
              coordinate: GeoCoordinate(latitude: -23, longitude: -46),
            ),
            finalCoordinate: const GeoCoordinate(
              latitude: -23.001,
              longitude: -46.001,
            ),
            instructions: '',
            safeAreaConfirmed: true,
            mapProvider: 'maptiler',
            mapType: 'satellite',
          ),
          paymentMethod: SimulatedPaymentMethod.pix,
        ),
      );

      expect(requestedPaths, <String>[
        '/api/v1/delivery-points/validate',
        '/api/v1/delivery-points',
        '/api/v1/orders',
        '/api/v1/orders/order-1/submit',
      ]);
    },
  );

  test(
    'local salvo sem ajuste envia saved_location_id e não cria outro ponto',
    () async {
      final List<String> requestedPaths = <String>[];
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          requestedPaths.add(request.url.path);
          if (request.url.path == '/api/v1/orders') {
            final Map<String, Object?> body = (jsonDecode(request.body) as Map)
                .map<String, Object?>((Object? key, Object? value) {
                  return MapEntry<String, Object?>(key.toString(), value);
                });
            expect(body['saved_location_id'], 'saved-1');
            expect(body['saved_location_review_confirmed'], isTrue);
            expect(body['saved_location_safe_area_confirmed'], isTrue);
            expect(body.containsKey('delivery_point_id'), isFalse);
            return http.Response(
              jsonEncode(<String, Object?>{'id': 'order-1'}),
              201,
            );
          }
          expect(request.url.path, '/api/v1/orders/order-1/submit');
          return http.Response(
            jsonEncode(<String, Object?>{
              'id': 'order-1',
              'status': 'PENDING_ADMIN_APPROVAL',
              'created_at': '2026-08-09T12:00:00Z',
              'items': <Object?>[],
            }),
            200,
          );
        }),
      );
      addTearDown(client.close);

      await ApiCheckoutRepository(client).submit(
        CheckoutRequest(
          lines: const <CartLine>[
            CartLine(
              productId: 'product-1',
              name: 'Produto',
              unitPrice: 10,
              quantity: 1,
            ),
          ],
          deliveryPoint: DeliveryPointDraft(
            approximatePlace: const PlaceSuggestion(
              label: 'Casa',
              referenceAddress: 'Rua A',
              coordinate: GeoCoordinate(latitude: -23, longitude: -46),
            ),
            finalCoordinate: const GeoCoordinate(latitude: -23, longitude: -46),
            instructions: '',
            safeAreaConfirmed: true,
            mapProvider: 'maptiler',
          ),
          paymentMethod: SimulatedPaymentMethod.pix,
          savedLocationId: 'saved-1',
          savedLocationReviewConfirmed: true,
          savedLocationSafeAreaConfirmed: true,
        ),
      );

      expect(requestedPaths, <String>[
        '/api/v1/orders',
        '/api/v1/orders/order-1/submit',
      ]);
    },
  );
}
