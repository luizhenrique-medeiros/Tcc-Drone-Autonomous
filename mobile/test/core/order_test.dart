import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('interpreta detalhe completo e mantém somente milestones reais', () {
    final OrderSnapshot order = OrderSnapshot.fromJson(<String, Object?>{
      'id': '938ae62d-1234-5678-9012-abcdefabcdef',
      'status': 'IN_TRANSIT',
      'payment_method': 'PIX',
      'subtotal': '34.90',
      'delivery_fee': '7.50',
      'discount': '6.98',
      'total': '35.42',
      'submitted_at': '2026-08-08T19:45:00Z',
      'items': <Map<String, Object?>>[
        <String, Object?>{
          'id': 'item-1',
          'product_id': 'product-1',
          'product_name': 'X-Burger',
          'category': 'Lanches',
          'image_url': 'https://cdn.example.test/x-burger.webp',
          'unit_price': '34.90',
          'quantity': 3,
          'line_total': '104.70',
        },
      ],
      'delivery_point': <String, Object?>{
        'final_latitude': '-22.997100',
        'final_longitude': '-46.583200',
        'address_reference': 'Bom Jesus dos Perdões',
        'instructions': 'Área aberta',
      },
      'milestones': <Map<String, Object?>>[
        <String, Object?>{
          'event_type': 'ORDER_SUBMITTED',
          'occurred_at': '2026-08-08T19:45:00Z',
        },
      ],
    });

    expect(order.shortId, '938AE62D');
    expect(order.displayTitle, 'X-Burger + 2 itens');
    expect(order.total, 35.42);
    expect(order.paymentMethod, SimulatedPaymentMethod.pix);
    expect(order.items.single.category, 'Lanches');
    expect(
      order.items.single.imageUrl,
      'https://cdn.example.test/x-burger.webp',
    );
    expect(order.deliveryPoint?.coordinate.latitude, -22.9971);
    expect(order.milestones.single.label, 'Pedido realizado');
    expect(order.detailLoaded, isTrue);
  });

  test('nome usa produto único e status possui rótulo central', () {
    const OrderSnapshot order = OrderSnapshot(
      id: 'pedido-1',
      status: OrderStatus.pendingAdminApproval,
      items: <OrderLineSnapshot>[
        OrderLineSnapshot(
          id: 'item',
          productId: 'produto',
          productName: 'Pizza',
          unitPrice: 20,
          quantity: 1,
          lineTotal: 20,
        ),
      ],
    );

    expect(order.displayTitle, 'Pizza');
    expect(order.status.title, 'Aguardando aprovação');
    expect(OrderStatus.completed.isTerminal, isTrue);
    expect(OrderStatus.returning.isTerminal, isFalse);
    expect(OrderStatusX.fromApi('NOVO_ESTADO'), OrderStatus.unknown);
    expect(
      OrderMilestone(
        eventType: 'MISSION_CLAIMED',
        occurredAt: DateTime.utc(2026),
      ).label,
      isNull,
    );
  });

  test('lista com itens e ponto ainda não representa detalhe carregado', () {
    final OrderSnapshot order = OrderSnapshot.fromJson(<String, Object?>{
      'id': 'pedido-lista',
      'status': 'APPROVED',
      'items': <Map<String, Object?>>[
        <String, Object?>{
          'id': 'item',
          'product_id': 'produto',
          'product_name': 'Pizza',
          'unit_price': 20,
          'quantity': 1,
          'line_total': 20,
        },
      ],
      'delivery_point': <String, Object?>{
        'final_latitude': -22.9,
        'final_longitude': -46.5,
      },
    });

    expect(order.hasDetails, isTrue);
    expect(order.detailLoaded, isFalse);
  });
}
