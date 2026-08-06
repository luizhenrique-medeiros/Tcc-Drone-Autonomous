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
  }) : _authRepository = authRepository,
       _productRepository = productRepository,
       _checkoutRepository = checkoutRepository;

  final AuthRepository _authRepository;
  final ProductRepository _productRepository;
  final CheckoutRepository _checkoutRepository;
  final MapProvider mapProvider;
  final LocationService locationService;
  final bool isDemoMode;

  UserSession? session;
  List<Product> products = <Product>[];
  bool isLoadingProducts = false;
  String? productsError;
  final Map<String, int> _quantities = <String, int>{};
  PlaceSuggestion? approximatePlace;
  GeoCoordinate? exactCoordinate;
  String deliveryInstructions = '';
  bool safeAreaConfirmed = false;
  SimulatedPaymentMethod paymentMethod = SimulatedPaymentMethod.pix;
  OrderSnapshot? order;
  bool isSubmittingOrder = false;
  String? checkoutError;
  StreamSubscription<OrderSnapshot>? _trackingSubscription;

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
  double get total => subtotal + deliveryFee;

  /// Demo data is public and can be prepared while the login screen is shown.
  /// The API catalog is authenticated, so real mode waits for a valid session.
  Future<void> initialize() async {
    if (isDemoMode) await loadProducts();
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

  Future<String?> login({
    required String email,
    required String password,
  }) async {
    try {
      session = await _authRepository.login(email: email, password: password);
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
      await loadProducts();
      notifyListeners();
      return null;
    } on Object catch (error) {
      return error.toString();
    }
  }

  void logout() {
    _authRepository.clearSession();
    session = null;
    products = <Product>[];
    productsError = null;
    _quantities.clear();
    approximatePlace = null;
    exactCoordinate = null;
    deliveryInstructions = '';
    safeAreaConfirmed = false;
    paymentMethod = SimulatedPaymentMethod.pix;
    order = null;
    checkoutError = null;
    unawaited(_trackingSubscription?.cancel());
    _trackingSubscription = null;
    notifyListeners();
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

  Future<String?> submitOrder() async {
    final PlaceSuggestion? place = approximatePlace;
    final GeoCoordinate? coordinate = exactCoordinate;
    if (cartLines.isEmpty || place == null || coordinate == null) {
      return 'Carrinho e ponto de entrega precisam estar completos.';
    }
    if (!safeAreaConfirmed) {
      return 'Confirme manualmente que o marcador está em uma área aberta.';
    }

    if (!isDemoMode && mapProvider.isDevelopmentFallback) {
      return 'Pedido bloqueado: o modo integrado exige Google Maps configurado; '
          'o fallback local é exclusivo da demonstração.';
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
            mapProvider: mapProvider.isDevelopmentFallback
                ? 'development_fallback'
                : 'google_maps',
          ),
          paymentMethod: paymentMethod,
        ),
      );
      final String orderId = order!.id;
      await _trackingSubscription?.cancel();
      _trackingSubscription = _checkoutRepository
          .watchOrder(orderId)
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
    super.dispose();
  }
}
