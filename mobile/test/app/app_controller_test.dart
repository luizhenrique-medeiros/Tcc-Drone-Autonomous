import 'package:drone_delivery_mobile/app/app_controller.dart';
import 'package:drone_delivery_mobile/core/location/location_service.dart';
import 'package:drone_delivery_mobile/core/maps/map_provider.dart';
import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/order.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/repositories/checkout_repository.dart';
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
    expect(controller.total, controller.subtotal + 7.50);
  });

  test(
    'modo integrado autentica antes do catálogo e bloqueia mapa fallback',
    () async {
      final AppController controller = AppController(
        authRepository: DemoAuthRepository(),
        productRepository: DemoProductRepository(),
        checkoutRepository: const DemoCheckoutRepository(),
        mapProvider: const DevelopmentMapProvider(fallbackForGoogle: true),
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

      expect(await controller.submitOrder(), contains('Google Maps'));
      expect(controller.order, isNull);
    },
  );

  test('status desconhecido não vira aprovação pendente', () {
    expect(OrderStatusX.fromApi('NOVO_ESTADO'), OrderStatus.unknown);
  });
}
