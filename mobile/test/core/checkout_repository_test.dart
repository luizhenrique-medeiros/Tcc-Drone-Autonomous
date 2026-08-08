import 'dart:convert';

import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'seleciona o pedido não terminal mais recente da lista da API',
    () async {
      late Uri requestedUri;
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          requestedUri = request.url;
          return http.Response(
            jsonEncode(<Map<String, Object?>>[
              <String, Object?>{
                'id': 'pedido-terminal-recente',
                'status': 'COMPLETED',
                'updated_at': '2026-08-06T12:00:00Z',
              },
              <String, Object?>{
                'id': 'pedido-ativo-recente',
                'status': 'IN_TRANSIT',
                'updated_at': '2026-08-05T12:00:00Z',
              },
              <String, Object?>{
                'id': 'pedido-ativo-antigo',
                'status': 'PENDING_ADMIN_APPROVAL',
                'updated_at': '2026-08-04T12:00:00Z',
              },
            ]),
            200,
            headers: <String, String>{'content-type': 'application/json'},
          );
        }),
      );
      addTearDown(client.close);

      final OrderSnapshot? restored = await ApiCheckoutRepository(
        client,
      ).findLatestActiveOrder();

      expect(requestedUri.path, '/api/v1/orders');
      expect(requestedUri.queryParameters['limit'], '100');
      expect(requestedUri.queryParameters['offset'], '0');
      expect(restored?.id, 'pedido-ativo-recente');
      expect(restored?.status, OrderStatus.inTransit);
    },
  );

  test('retorna null quando todos os pedidos são terminais', () async {
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((_) async {
        return http.Response(
          jsonEncode(<Map<String, Object?>>[
            <String, Object?>{'id': 'pedido-1', 'status': 'COMPLETED'},
            <String, Object?>{'id': 'pedido-2', 'status': 'CANCELLED'},
          ]),
          200,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }),
    );
    addTearDown(client.close);

    expect(await ApiCheckoutRepository(client).findLatestActiveOrder(), isNull);
  });

  test('ignora rascunhos e pagina até encontrar pedido ativo', () async {
    final List<int> requestedOffsets = <int>[];
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((http.Request request) async {
        final int offset = int.parse(request.url.queryParameters['offset']!);
        requestedOffsets.add(offset);
        final List<Map<String, Object?>> orders = offset == 0
            ? List<Map<String, Object?>>.generate(
                100,
                (int index) => <String, Object?>{
                  'id': 'pedido-terminal-$index',
                  'status': 'COMPLETED',
                },
              )
            : <Map<String, Object?>>[
                <String, Object?>{
                  'id': 'rascunho-abandonado',
                  'status': 'DRAFT',
                },
                <String, Object?>{
                  'id': 'pedido-em-andamento',
                  'status': 'PENDING_ADMIN_APPROVAL',
                },
              ];
        return http.Response(
          jsonEncode(orders),
          200,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }),
    );
    addTearDown(client.close);

    final OrderSnapshot? restored = await ApiCheckoutRepository(
      client,
    ).findLatestActiveOrder();

    expect(requestedOffsets, <int>[0, 100]);
    expect(restored?.id, 'pedido-em-andamento');
  });

  test('modo demo não inventa pedido para restaurar', () async {
    expect(
      await const DemoCheckoutRepository().findLatestActiveOrder(),
      isNull,
    );
  });
}
