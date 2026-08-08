enum SimulatedPaymentMethod { pix, creditCard }

extension SimulatedPaymentMethodX on SimulatedPaymentMethod {
  String get label => switch (this) {
    SimulatedPaymentMethod.pix => 'PIX',
    SimulatedPaymentMethod.creditCard => 'Cartão de crédito',
  };

  String get apiValue => switch (this) {
    SimulatedPaymentMethod.pix => 'PIX',
    SimulatedPaymentMethod.creditCard => 'CREDIT_CARD',
  };
}

enum OrderStatus {
  draft,
  pendingAdminApproval,
  approved,
  rejected,
  missionPreparing,
  missionReady,
  waitingFlightAuthorization,
  missionUploading,
  inTransit,
  atDestination,
  delivered,
  returning,
  completed,
  cancelled,
  failed,
  unknown,
}

extension OrderStatusX on OrderStatus {
  String get apiValue => switch (this) {
    OrderStatus.draft => 'DRAFT',
    OrderStatus.pendingAdminApproval => 'PENDING_ADMIN_APPROVAL',
    OrderStatus.approved => 'APPROVED',
    OrderStatus.rejected => 'REJECTED',
    OrderStatus.missionPreparing => 'MISSION_PREPARING',
    OrderStatus.missionReady => 'MISSION_READY',
    OrderStatus.waitingFlightAuthorization => 'WAITING_FLIGHT_AUTHORIZATION',
    OrderStatus.missionUploading => 'MISSION_UPLOADING',
    OrderStatus.inTransit => 'IN_TRANSIT',
    OrderStatus.atDestination => 'AT_DESTINATION',
    OrderStatus.delivered => 'DELIVERED',
    OrderStatus.returning => 'RETURNING',
    OrderStatus.completed => 'COMPLETED',
    OrderStatus.cancelled => 'CANCELLED',
    OrderStatus.failed => 'FAILED',
    OrderStatus.unknown => 'UNKNOWN',
  };

  String get title => switch (this) {
    OrderStatus.draft => 'Pedido em rascunho',
    OrderStatus.pendingAdminApproval => 'Aguardando análise',
    OrderStatus.approved => 'Pedido aprovado',
    OrderStatus.rejected => 'Pedido rejeitado',
    OrderStatus.missionPreparing => 'Preparando missão',
    OrderStatus.missionReady => 'Missão revisada',
    OrderStatus.waitingFlightAuthorization => 'Aguardando autorização de voo',
    OrderStatus.missionUploading => 'Enviando missão ao drone',
    OrderStatus.inTransit => 'Drone em rota',
    OrderStatus.atDestination => 'Drone no destino',
    OrderStatus.delivered => 'Comando de entrega registrado',
    OrderStatus.returning => 'Drone retornando',
    OrderStatus.completed => 'Missão encerrada',
    OrderStatus.cancelled => 'Pedido cancelado',
    OrderStatus.failed => 'Falha na operação',
    OrderStatus.unknown => 'Estado incompatível',
  };

  String get description => switch (this) {
    OrderStatus.draft => 'Finalize as informações para enviar o pedido.',
    OrderStatus.pendingAdminApproval =>
      'A equipe confere o produto e o ponto exato escolhido.',
    OrderStatus.approved => 'O pedido foi aprovado sem iniciar o voo.',
    OrderStatus.rejected =>
      'A operação não foi aprovada. Consulte o motivo abaixo.',
    OrderStatus.missionPreparing =>
      'A rota está sendo preparada para revisão no Mission Planner.',
    OrderStatus.missionReady =>
      'A rota foi revisada e ainda não possui autorização de voo.',
    OrderStatus.waitingFlightAuthorization =>
      'Um operador precisa concluir o checklist e autorizar o voo.',
    OrderStatus.missionUploading =>
      'O gateway está validando e carregando a missão autorizada.',
    OrderStatus.inTransit => 'Acompanhe o progresso recebido do sistema.',
    OrderStatus.atDestination => 'O drone chegou ao ponto confirmado.',
    OrderStatus.delivered =>
      'O gateway confirmou a etapa do mecanismo; isso não comprova o recebimento físico.',
    OrderStatus.returning => 'O drone está voltando ao ponto de origem.',
    OrderStatus.completed =>
      'O retorno e o pouso foram reportados; a entrega física ainda exige evidência operacional.',
    OrderStatus.cancelled => 'Este pedido foi cancelado.',
    OrderStatus.failed =>
      'A equipe foi notificada. Nenhum sucesso é presumido automaticamente.',
    OrderStatus.unknown =>
      'O backend enviou um estado que esta versão do aplicativo não reconhece.',
  };

  bool get isTerminal => <OrderStatus>{
    OrderStatus.rejected,
    OrderStatus.completed,
    OrderStatus.cancelled,
    OrderStatus.failed,
  }.contains(this);

  static OrderStatus fromApi(Object? value) {
    final String normalized = value?.toString().toUpperCase() ?? '';
    for (final OrderStatus status in OrderStatus.values) {
      if (status.apiValue == normalized) return status;
    }
    return OrderStatus.unknown;
  }
}

class CartLine {
  const CartLine({
    required this.productId,
    required this.name,
    required this.unitPrice,
    required this.quantity,
  });

  final String productId;
  final String name;
  final double unitPrice;
  final int quantity;

  double get total => unitPrice * quantity;
}

class OrderSnapshot {
  const OrderSnapshot({
    required this.id,
    required this.status,
    this.rejectionReason,
    this.lastEventAt,
  });

  final String id;
  final OrderStatus status;
  final String? rejectionReason;
  final DateTime? lastEventAt;

  factory OrderSnapshot.fromJson(Map<String, Object?> json) {
    return OrderSnapshot(
      id: (json['id'] ?? json['order_id'] ?? '').toString(),
      status: OrderStatusX.fromApi(json['status']),
      rejectionReason: (json['rejection_reason'] ?? json['reason'])?.toString(),
      lastEventAt: DateTime.tryParse(
        (json['updated_at'] ?? json['created_at'] ?? '').toString(),
      ),
    );
  }
}
