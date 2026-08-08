import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/location/location_service.dart';
import '../core/maps/map_provider.dart';
import '../core/models/delivery_point.dart';
import '../core/models/order.dart';
import '../core/models/product.dart';
import '../core/repositories/auth_repository.dart';
import '../core/repositories/checkout_repository.dart';
import '../core/repositories/product_repository.dart';

class AppController extends ChangeNotifier {
  AppController({
    required AuthRepository authRepository,
    required ProductRepository productRepository,
    required CheckoutRepository checkoutRepository,
    required this.mapProvider,
    required this.locationService,
    required this.isDemoMode,
    this.mapInitializationMessage,
    this.disposeResources,
  }) : _authRepository = authRepository,
       _productRepository = productRepository,
       _checkoutRepository = checkoutRepository;

  final AuthRepository _authRepository;
  final ProductRepository _productRepository;
  final CheckoutRepository _checkoutRepository;
  final MapProvider mapProvider;
  final LocationService locationService;
  final bool isDemoMode;
  String? mapInitializationMessage;
  final VoidCallback? disposeResources;

  UserSession? session;
  List<Product> products = <Product>[];
  bool isLoadingProducts = false;
  String? productsError;
  String? initializationError;
  final Map<String, int> _quantities = <String, int>{};
  PlaceSuggestion? approximatePlace;
  GeoCoordinate? exactCoordinate;
  String deliveryInstructions = '';
  bool safeAreaConfirmed = false;
  SimulatedPaymentMethod paymentMethod = SimulatedPaymentMethod.pix;
  OrderSnapshot? order;
  bool isSubmittingOrder = false;
  String? checkoutError;
  bool mapViewReady = false;
  StreamSubscription<OrderSnapshot>? _trackingSubscription;
  Future<void>? _initialization;

  bool get isAuthenticated => session != null;
  int get cartCount => _quantities.values.fold<int>(0, (int a, int b) => a + b);

  List<CartLine> get cartLines => products
      .where((Product product) => (_quantities[product.id] ?? 0) > 0)
      .map<CartLine>((Product product) {
        return CartLine(
          productId: product.id,
          name: product.name,
          unitPrice: product.price,
          quantity: _quantities[product.id]!,
        );
      })
      .toList(growable: false);

  double get subtotal => cartLines.fold<double>(
    0,
    (double total, CartLine line) => total + line.total,
  );
  double get deliveryFee => cartCount == 0 ? 0 : 7.50;
  double get discount => _money(subtotal * 0.20);
  double get total => _money(subtotal + deliveryFee - discount);

  double _money(double value) => (value * 100).roundToDouble() / 100;

  /// Demo data is public and can be prepared while the login screen is shown.
  /// The API catalog is authenticated, so real mode waits for a valid session.
  Future<void> initialize() => _initialization ??= _initialize();

  Future<void> _initialize() async {
    try {
      if (isDemoMode) {
        await loadProducts();
        return;
      }
      session = await _authRepository.restoreSession();
      if (session != null) {
        await loadProducts();
        await _restoreActiveOrder();
      }
    } on Object {
      session = null;
      initializationError =
          'Não foi possível restaurar a sessão local. Entre novamente.';
    } finally {
      notifyListeners();
    }
  }

  Future<void> loadProducts() async {
    isLoadingProducts = true;
    productsError = null;
    notifyListeners();
    try {
      products = await _productRepository.listProducts();
    } on Object catch (error) {
      productsError = error.toString();
    } finally {
      isLoadingProducts = false;
      notifyListeners();
    }
  }

  Future<void> _restoreActiveOrder() async {
    try {
      final OrderSnapshot? activeOrder = await _checkoutRepository
          .findLatestActiveOrder();
      if (activeOrder == null ||
          activeOrder.status == OrderStatus.draft ||
          activeOrder.status.isTerminal) {
        return;
      }
      order = activeOrder;
      checkoutError = null;
      await _startTracking(activeOrder);
    } on Object catch (error) {
      checkoutError =
          'Não foi possível recuperar o pedido em andamento: $error';
    }
  }

  Future<void> _startTracking(OrderSnapshot initialOrder) async {
    await _trackingSubscription?.cancel();
    _trackingSubscription = null;
    if (initialOrder.status.isTerminal) return;

    _trackingSubscription = _checkoutRepository
        .watchOrder(initialOrder.id)
        .listen(
          (OrderSnapshot snapshot) {
            order = snapshot;
            notifyListeners();
          },
          onError: (Object error) {
            checkoutError = 'Não foi possível atualizar o pedido: $error';
            notifyListeners();
          },
        );
  }

  Future<String?> login({
    required String email,
    required String password,
  }) async {
    try {
      session = await _authRepository.login(email: email, password: password);
      initializationError = null;
      await loadProducts();
      notifyListeners();
      return null;
    } on Object catch (error) {
      return error.toString();
    }
  }

  Future<String?> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  }) async {
    try {
      session = await _authRepository.register(
        name: name,
        email: email,
        password: password,
        phone: phone,
      );
      initializationError = null;
      await loadProducts();
      notifyListeners();
      return null;
    } on Object catch (error) {
      return error.toString();
    }
  }

  Future<void> logout() async {
    try {
      await _authRepository.clearSession();
    } finally {
      session = null;
      products = <Product>[];
      productsError = null;
      initializationError = null;
      _quantities.clear();
      approximatePlace = null;
      exactCoordinate = null;
      deliveryInstructions = '';
      safeAreaConfirmed = false;
      paymentMethod = SimulatedPaymentMethod.pix;
      order = null;
      checkoutError = null;
      await _trackingSubscription?.cancel();
      _trackingSubscription = null;
      notifyListeners();
    }
  }

  void addProduct(Product product) {
    _quantities.update(product.id, (int value) => value + 1, ifAbsent: () => 1);
    notifyListeners();
  }

  void decrementProduct(Product product) {
    final int current = _quantities[product.id] ?? 0;
    if (current <= 1) {
      _quantities.remove(product.id);
    } else {
      _quantities[product.id] = current - 1;
    }
    notifyListeners();
  }

  int quantityFor(Product product) => _quantities[product.id] ?? 0;

  void selectApproximatePlace(PlaceSuggestion place) {
    approximatePlace = place;
    exactCoordinate = null;
    safeAreaConfirmed = false;
    notifyListeners();
  }

  void updateExactCoordinate(GeoCoordinate coordinate) {
    exactCoordinate = coordinate;
    notifyListeners();
  }

  void updateDeliveryDetails({
    required String instructions,
    required bool safeArea,
  }) {
    deliveryInstructions = instructions.trim();
    safeAreaConfirmed = safeArea;
    notifyListeners();
  }

  void selectPayment(SimulatedPaymentMethod method) {
    paymentMethod = method;
    notifyListeners();
  }

  void markMapViewReady() {
    if (mapViewReady && mapInitializationMessage == null) return;
    mapViewReady = true;
    mapInitializationMessage = null;
    notifyListeners();
  }

  void markMapViewFailed(String message) {
    if (!mapViewReady && mapInitializationMessage == message) return;
    mapViewReady = false;
    mapInitializationMessage = message;
    notifyListeners();
  }

  Future<String?> submitOrder() async {
    final PlaceSuggestion? place = approximatePlace;
    final GeoCoordinate? coordinate = exactCoordinate;
    if (cartLines.isEmpty || place == null || coordinate == null) {
      return 'Carrinho e ponto de entrega precisam estar completos.';
    }
    if (!safeAreaConfirmed) {
      return 'Confirme manualmente que o marcador está em uma área aberta.';
    }
    if (!coordinate.isValid || !(place.coordinate?.isValid ?? false)) {
      return 'As coordenadas de entrega estão fora da faixa válida.';
    }

    if (!isDemoMode && mapProvider.isDevelopmentFallback) {
      return 'Pedido bloqueado: configure o MapTiler online antes de '
          'confirmar coordenadas no modo integrado.';
    }

    isSubmittingOrder = true;
    checkoutError = null;
    notifyListeners();
    try {
      order = await _checkoutRepository.submit(
        CheckoutRequest(
          lines: cartLines,
          deliveryPoint: DeliveryPointDraft(
            approximatePlace: place,
            finalCoordinate: coordinate,
            instructions: deliveryInstructions,
            safeAreaConfirmed: safeAreaConfirmed,
            mapProvider: mapProvider.id,
          ),
          paymentMethod: paymentMethod,
        ),
      );
      await _startTracking(order!);
      return null;
    } on Object catch (error) {
      checkoutError = error.toString();
      return checkoutError;
    } finally {
      isSubmittingOrder = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    unawaited(_trackingSubscription?.cancel());
    disposeResources?.call();
    super.dispose();
  }
}
