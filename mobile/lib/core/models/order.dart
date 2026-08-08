import 'delivery_point.dart';

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

  static SimulatedPaymentMethod? fromApi(Object? value) {
    final String normalized = value?.toString().toUpperCase() ?? '';
    return switch (normalized) {
      'PIX' || 'PIX_SIMULATED' => SimulatedPaymentMethod.pix,
      'CREDIT_CARD' ||
      'CREDIT_CARD_SIMULATED' => SimulatedPaymentMethod.creditCard,
      _ => null,
    };
  }
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
    OrderStatus.pendingAdminApproval => 'Aguardando aprovação',
    OrderStatus.approved => 'Pedido aprovado',
    OrderStatus.rejected => 'Pedido recusado',
    OrderStatus.missionPreparing ||
    OrderStatus.missionReady => 'Preparando entrega',
    OrderStatus.waitingFlightAuthorization => 'Preparando drone',
    OrderStatus.missionUploading => 'Enviando missão ao drone',
    OrderStatus.inTransit => 'Em rota',
    OrderStatus.atDestination => 'Drone no destino',
    OrderStatus.delivered => 'Etapa de entrega concluída',
    OrderStatus.returning => 'Drone retornando',
    OrderStatus.completed => 'Concluído',
    OrderStatus.cancelled => 'Cancelado',
    OrderStatus.failed => 'Ocorreu um problema',
    OrderStatus.unknown => 'Estado incompatível',
  };

  String get description => switch (this) {
    OrderStatus.draft => 'Finalize as informações para enviar o pedido.',
    OrderStatus.pendingAdminApproval =>
      'A equipe confere o produto e o ponto exato escolhido.',
    OrderStatus.approved => 'O pedido foi aprovado sem iniciar o voo.',
    OrderStatus.rejected =>
      'A operação não foi aprovada. Consulte o motivo informado.',
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
      'O retorno e o pouso foram reportados pelo sistema.',
    OrderStatus.cancelled => 'Este pedido foi cancelado.',
    OrderStatus.failed =>
      'A equipe foi notificada. Nenhum sucesso é presumido automaticamente.',
    OrderStatus.unknown =>
      'O backend enviou um estado que esta versão não reconhece.',
  };

  bool get isTerminal => <OrderStatus>{
    OrderStatus.rejected,
    OrderStatus.completed,
    OrderStatus.cancelled,
    OrderStatus.failed,
  }.contains(this);

  bool get isActive => this != OrderStatus.draft && !isTerminal;

  static OrderStatus fromApi(Object? value) {
    final String normalized = value?.toString().toUpperCase() ?? '';
    for (final OrderStatus status in OrderStatus.values) {
      if (status.apiValue == normalized) return status;
    }
    return OrderStatus.unknown;
  }
}

enum OrdersGroup { all, active, history }

extension OrdersGroupX on OrdersGroup {
  String get apiValue => switch (this) {
    OrdersGroup.all => 'all',
    OrdersGroup.active => 'active',
    OrdersGroup.history => 'history',
  };
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

class OrderLineSnapshot {
  const OrderLineSnapshot({
    required this.id,
    required this.productId,
    required this.productName,
    required this.unitPrice,
    required this.quantity,
    required this.lineTotal,
    this.category,
    this.imageUrl,
  });

  final String id;
  final String productId;
  final String productName;
  final double unitPrice;
  final int quantity;
  final double lineTotal;
  final String? category;
  final String? imageUrl;

  factory OrderLineSnapshot.fromJson(Map<String, Object?> json) {
    return OrderLineSnapshot(
      id: json['id']?.toString() ?? '',
      productId: json['product_id']?.toString() ?? '',
      productName: json['product_name']?.toString().trim() ?? '',
      unitPrice: _toDouble(json['unit_price']),
      quantity: _toInt(json['quantity']),
      lineTotal: _toDouble(json['line_total'] ?? json['subtotal']),
      category: _cleanText(json['category']),
      imageUrl: _cleanText(json['image_url']),
    );
  }
}

class OrderDeliveryPointSnapshot {
  const OrderDeliveryPointSnapshot({
    required this.coordinate,
    this.label,
    this.searchedAddress,
    this.referenceAddress,
    this.instructions,
  });

  final GeoCoordinate coordinate;
  final String? label;
  final String? searchedAddress;
  final String? referenceAddress;
  final String? instructions;

  String get displayAddress =>
      referenceAddress ?? searchedAddress ?? label ?? 'Sem referência textual';

  factory OrderDeliveryPointSnapshot.fromJson(Map<String, Object?> json) {
    return OrderDeliveryPointSnapshot(
      coordinate: GeoCoordinate(
        latitude: _toDouble(json['final_latitude'] ?? json['latitude']),
        longitude: _toDouble(json['final_longitude'] ?? json['longitude']),
      ),
      label: _cleanText(json['label']),
      searchedAddress: _cleanText(json['searched_address']),
      referenceAddress: _cleanText(
        json['address_reference'] ?? json['reference_address'],
      ),
      instructions: _cleanText(json['instructions']),
    );
  }
}

class OrderMilestone {
  const OrderMilestone({required this.eventType, required this.occurredAt});

  final String eventType;
  final DateTime occurredAt;

  String? get label => switch (eventType.toUpperCase()) {
    'ORDER_SUBMITTED' => 'Pedido realizado',
    'ORDER_APPROVED' => 'Pedido aprovado',
    'ORDER_REJECTED' => 'Pedido recusado',
    'ORDER_CANCELLED' => 'Pedido cancelado',
    'MISSION_GENERATED' => 'Missão preparada',
    'MISSION_EXECUTING' || 'MISSION_STARTED' => 'Saída do drone',
    'MISSION_DESTINATION_REACHED' ||
    'DESTINATION_REACHED' => 'Chegada ao destino',
    'MISSION_DELIVERY_CONFIRMED' ||
    'DELIVERY_CONFIRMED' => 'Etapa de entrega registrada',
    'MISSION_RETURNING' || 'RETURN_STARTED' => 'Retorno iniciado',
    'MISSION_COMPLETED' || 'ORDER_COMPLETED' => 'Conclusão',
    'MISSION_FAILED' || 'ORDER_FAILED' => 'Falha registrada',
    'MISSION_ABORTED' || 'ORDER_ABORTED' => 'Missão interrompida',
    _ => null,
  };

  factory OrderMilestone.fromJson(Map<String, Object?> json) {
    final String eventType = json['event_type']?.toString().trim() ?? '';
    final DateTime? occurredAt = DateTime.tryParse(
      json['occurred_at']?.toString() ?? '',
    );
    if (eventType.isEmpty || occurredAt == null) {
      throw const FormatException('Marco do pedido inválido.');
    }
    return OrderMilestone(eventType: eventType, occurredAt: occurredAt);
  }
}

class OrderSnapshot {
  const OrderSnapshot({
    required this.id,
    required this.status,
    this.rejectionReason,
    this.lastEventAt,
    this.paymentMethod,
    this.subtotal = 0,
    this.deliveryFee = 0,
    this.discount = 0,
    this.total = 0,
    this.items = const <OrderLineSnapshot>[],
    this.deliveryPoint,
    this.submittedAt,
    this.completedAt,
    this.createdAt,
    this.updatedAt,
    this.milestones = const <OrderMilestone>[],
    this.detailLoaded = false,
  });

  final String id;
  final OrderStatus status;
  final String? rejectionReason;
  final DateTime? lastEventAt;
  final SimulatedPaymentMethod? paymentMethod;
  final double subtotal;
  final double deliveryFee;
  final double discount;
  final double total;
  final List<OrderLineSnapshot> items;
  final OrderDeliveryPointSnapshot? deliveryPoint;
  final DateTime? submittedAt;
  final DateTime? completedAt;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final List<OrderMilestone> milestones;

  /// True only when this snapshot came from the order-detail payload.
  ///
  /// List and WebSocket payloads can contain items and a delivery point, so
  /// their presence alone cannot prove that detail-only fields were loaded.
  final bool detailLoaded;

  String get shortId {
    final String compact = id.replaceAll('-', '').toUpperCase();
    if (compact.isEmpty) return '—';
    return compact.substring(0, compact.length < 8 ? compact.length : 8);
  }

  int get totalItems => items.fold<int>(
    0,
    (int total, OrderLineSnapshot item) => total + item.quantity,
  );

  String get displayTitle {
    if (items.isEmpty) return 'Pedido';
    final String first = items.first.productName.isEmpty
        ? 'Produto'
        : items.first.productName;
    final int remaining = totalItems - 1;
    if (remaining <= 0) return first;
    return '$first + $remaining ${remaining == 1 ? 'item' : 'itens'}';
  }

  DateTime? get displayDate => submittedAt ?? createdAt ?? lastEventAt;

  bool get hasDetails => items.isNotEmpty && deliveryPoint != null;

  OrderSnapshot copyWith({
    OrderStatus? status,
    String? rejectionReason,
    DateTime? lastEventAt,
    List<OrderMilestone>? milestones,
    bool? detailLoaded,
  }) {
    return OrderSnapshot(
      id: id,
      status: status ?? this.status,
      rejectionReason: rejectionReason ?? this.rejectionReason,
      lastEventAt: lastEventAt ?? this.lastEventAt,
      paymentMethod: paymentMethod,
      subtotal: subtotal,
      deliveryFee: deliveryFee,
      discount: discount,
      total: total,
      items: items,
      deliveryPoint: deliveryPoint,
      submittedAt: submittedAt,
      completedAt: completedAt,
      createdAt: createdAt,
      updatedAt: updatedAt,
      milestones: milestones ?? this.milestones,
      detailLoaded: detailLoaded ?? this.detailLoaded,
    );
  }

  factory OrderSnapshot.fromJson(Map<String, Object?> json) {
    final DateTime? createdAt = _toDateTime(json['created_at']);
    final DateTime? updatedAt = _toDateTime(json['updated_at']);
    final Object? rawItems = json['items'];
    final Object? rawMilestones = json['milestones'];
    return OrderSnapshot(
      id: (json['id'] ?? json['order_id'] ?? '').toString(),
      status: OrderStatusX.fromApi(json['status']),
      rejectionReason: _cleanText(json['rejection_reason'] ?? json['reason']),
      lastEventAt: updatedAt ?? createdAt,
      paymentMethod: SimulatedPaymentMethodX.fromApi(
        json['payment_method'] ?? json['simulated_payment_method'],
      ),
      subtotal: _toDouble(json['subtotal']),
      deliveryFee: _toDouble(json['delivery_fee']),
      discount: _toDouble(json['discount']),
      total: _toDouble(json['total']),
      items: rawItems is List
          ? rawItems
                .map<OrderLineSnapshot>(
                  (Object? item) => OrderLineSnapshot.fromJson(
                    _expectMap(item, 'Item do pedido inválido.'),
                  ),
                )
                .toList(growable: false)
          : const <OrderLineSnapshot>[],
      deliveryPoint: json['delivery_point'] == null
          ? null
          : OrderDeliveryPointSnapshot.fromJson(
              _expectMap(json['delivery_point'], 'Ponto de entrega inválido.'),
            ),
      submittedAt: _toDateTime(json['submitted_at']),
      completedAt: _toDateTime(json['completed_at']),
      createdAt: createdAt,
      updatedAt: updatedAt,
      milestones: rawMilestones is List
          ? rawMilestones
                .map<OrderMilestone>(
                  (Object? item) => OrderMilestone.fromJson(
                    _expectMap(item, 'Marco do pedido inválido.'),
                  ),
                )
                .toList(growable: false)
          : const <OrderMilestone>[],
      detailLoaded: json.containsKey('milestones'),
    );
  }
}

double _toDouble(Object? value) {
  if (value == null) return 0;
  if (value is num) return value.toDouble();
  final double? parsed = double.tryParse(value.toString());
  if (parsed == null || !parsed.isFinite) {
    throw const FormatException('Valor numérico inválido no pedido.');
  }
  return parsed;
}

int _toInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  final int? parsed = int.tryParse(value?.toString() ?? '');
  if (parsed == null) {
    throw const FormatException('Quantidade inválida no pedido.');
  }
  return parsed;
}

DateTime? _toDateTime(Object? value) {
  if (value == null) return null;
  return DateTime.tryParse(value.toString());
}

String? _cleanText(Object? value) {
  final String text = value?.toString().trim() ?? '';
  return text.isEmpty ? null : text;
}

Map<String, Object?> _expectMap(Object? value, String message) {
  if (value is Map<String, Object?>) return value;
  if (value is Map) {
    return value.map<String, Object?>(
      (Object? key, Object? item) =>
          MapEntry<String, Object?>(key.toString(), item),
    );
  }
  throw FormatException(message);
}
