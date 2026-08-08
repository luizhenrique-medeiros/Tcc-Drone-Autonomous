import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../orders/presentation/order_details_screen.dart';

/// Compatibilidade para o fluxo que antes abria uma tela exclusiva de tracking.
/// O acompanhamento agora usa o mesmo detalhe reutilizável de "Meus pedidos".
class OrderTrackingScreen extends StatelessWidget {
  const OrderTrackingScreen({this.orderId, super.key});

  final String? orderId;

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final String? resolvedOrderId = orderId ?? controller.order?.id;
    if (resolvedOrderId == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Acompanhamento')),
        body: const Center(child: Text('Nenhum pedido em acompanhamento.')),
      );
    }
    return OrderDetailsScreen(
      orderId: resolvedOrderId,
      controller: controller.orders,
      mapProvider: controller.mapProvider,
    );
  }
}
