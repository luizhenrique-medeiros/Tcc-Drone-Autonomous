import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/order_repository.dart';
import 'package:flutter_test/flutter_test.dart';

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
}
