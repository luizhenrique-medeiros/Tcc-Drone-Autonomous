import 'dart:async';

import 'package:flutter/foundation.dart';

import '../core/location/location_service.dart';
import '../core/maps/map_provider.dart';
import '../core/models/delivery_point.dart';
import '../core/models/order.dart';
import '../core/models/product.dart';
import '../core/models/saved_location.dart';
import '../core/network/api_client.dart';
import '../core/repositories/auth_repository.dart';
import '../core/repositories/checkout_repository.dart';
import '../core/repositories/order_repository.dart';
import '../core/repositories/product_repository.dart';
import '../core/repositories/saved_location_repository.dart';
import '../features/orders/application/orders_controller.dart';
import '../features/saved_locations/application/saved_locations_controller.dart';

class AppController extends ChangeNotifier {
  AppController({
    required AuthRepository authRepository,
    required ProductRepository productRepository,
    required CheckoutRepository checkoutRepository,
    OrderRepository? orderRepository,
    SavedLocationRepository? savedLocationRepository,
    required this.mapProvider,
    required this.locationService,
    required this.isDemoMode,
    this.mapInitializationMessage,
    this.disposeResources,
  }) : _authRepository = authRepository,
       _productRepository = productRepository,
       _checkoutRepository = checkoutRepository,
       _trackSubmittedOrders = orderRepository != null,
       savedLocations = SavedLocationsController(
         repository: savedLocationRepository ?? DemoSavedLocationRepository(),
       ),
       orders = OrdersController(
         repository: orderRepository ?? DemoOrderRepository(),
       );

  final AuthRepository _authRepository;
  final ProductRepository _productRepository;
  final CheckoutRepository _checkoutRepository;
  final bool _trackSubmittedOrders;
  final OrdersController orders;
  final SavedLocationsController savedLocations;
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
  String? finalAddressReference;
  LocationSelectionResult? currentLocationSelection;
  String? selectedSavedLocationOriginId;
  bool selectedSavedLocationWasAdjusted = false;
  bool saveCurrentLocation = false;
  String savedLocationName = '';
  String? savedLocationWarning;
  SimulatedPaymentMethod paymentMethod = SimulatedPaymentMethod.pix;
  OrderSnapshot? order;
  bool isSubmittingOrder = false;
  bool isSavingLocationAfterOrder = false;
  Future<void>? pendingSavedLocationSave;
  String? checkoutError;
  bool mapViewReady = false;
  Future<void>? _initialization;
  bool _disposed = false;
  int _sessionGeneration = 0;

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
        await Future.wait<void>(<Future<void>>[
          loadProducts(),
          orders.loadInitial(),
          savedLocations.load(),
        ]);
        return;
      }
      session = await _authRepository.restoreSession();
      if (session != null) {
        await Future.wait<void>(<Future<void>>[
          loadProducts(),
          orders.loadInitial(),
          savedLocations.load(),
        ]);
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

  Future<String?> login({
    required String email,
    required String password,
  }) async {
    try {
      final UserSession authenticated = await _authRepository.login(
        email: email,
        password: password,
      );
      _sessionGeneration++;
      session = authenticated;
      initializationError = null;
      await Future.wait<void>(<Future<void>>[
        loadProducts(),
        orders.loadInitial(force: true),
        savedLocations.load(force: true),
      ]);
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
      final UserSession authenticated = await _authRepository.register(
        name: name,
        email: email,
        password: password,
        phone: phone,
      );
      _sessionGeneration++;
      session = authenticated;
      initializationError = null;
      await Future.wait<void>(<Future<void>>[
        loadProducts(),
        orders.loadInitial(force: true),
        savedLocations.load(force: true),
      ]);
      notifyListeners();
      return null;
    } on Object catch (error) {
      return error.toString();
    }
  }

  Future<void> logout() async {
    _sessionGeneration++;
    pendingSavedLocationSave = null;
    isSavingLocationAfterOrder = false;
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
      finalAddressReference = null;
      currentLocationSelection = null;
      selectedSavedLocationOriginId = null;
      selectedSavedLocationWasAdjusted = false;
      saveCurrentLocation = false;
      savedLocationName = '';
      savedLocationWarning = null;
      paymentMethod = SimulatedPaymentMethod.pix;
      order = null;
      checkoutError = null;
      await orders.reset();
      await savedLocations.reset(clearSessionData: isDemoMode);
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
    deliveryInstructions = '';
    safeAreaConfirmed = false;
    finalAddressReference = null;
    currentLocationSelection = null;
    selectedSavedLocationOriginId = null;
    selectedSavedLocationWasAdjusted = false;
    saveCurrentLocation = false;
    savedLocationName = '';
    savedLocationWarning = null;
    notifyListeners();
  }

  void applyLocationSelection(LocationSelectionResult result) {
    approximatePlace = result.approximatePlace;
    exactCoordinate = result.finalCoordinate;
    deliveryInstructions = result.instructions;
    safeAreaConfirmed = result.safeAreaConfirmed;
    finalAddressReference = result.addressReference;
    currentLocationSelection = result;
    selectedSavedLocationOriginId = result.savedLocationId;
    selectedSavedLocationWasAdjusted = result.wasAdjusted;
    saveCurrentLocation = false;
    savedLocationName = '';
    savedLocationWarning = null;
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

  bool get canOfferSaveCurrentLocation =>
      currentLocationSelection != null &&
      exactCoordinate != null &&
      selectedSavedLocationOriginId == null &&
      savedLocations.hasLoaded &&
      savedLocations.loadError == null &&
      !savedLocations.limitReached;

  void configureSavedLocation({required bool enabled, required String name}) {
    saveCurrentLocation = enabled;
    savedLocationName = name;
    savedLocationWarning = null;
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
    savedLocationWarning = null;
    notifyListeners();
    try {
      final String? savedLocationId =
          selectedSavedLocationOriginId != null &&
              !selectedSavedLocationWasAdjusted
          ? selectedSavedLocationOriginId
          : null;
      order = await _checkoutRepository.submit(
        CheckoutRequest(
          lines: cartLines,
          deliveryPoint: DeliveryPointDraft(
            approximatePlace: place,
            finalCoordinate: coordinate,
            instructions: deliveryInstructions,
            safeAreaConfirmed: safeAreaConfirmed,
            mapProvider:
                currentLocationSelection?.mapProvider ?? mapProvider.id,
            mapType: currentLocationSelection?.mapType ?? 'hybrid',
            addressReference: finalAddressReference,
          ),
          paymentMethod: paymentMethod,
          savedLocationId: savedLocationId,
          savedLocationReviewConfirmed:
              currentLocationSelection?.userConfirmed ?? false,
          savedLocationSafeAreaConfirmed: safeAreaConfirmed,
        ),
      );
      orders.upsertSubmitted(order!, watch: _trackSubmittedOrders);
      _startLocationSaveAfterOrder(coordinate);
      return null;
    } on Object catch (error) {
      checkoutError = error.toString();
      return checkoutError;
    } finally {
      isSubmittingOrder = false;
      notifyListeners();
    }
  }

  void _startLocationSaveAfterOrder(GeoCoordinate coordinate) {
    if (!saveCurrentLocation || selectedSavedLocationOriginId != null) return;
    final LocationSelectionResult? selection = currentLocationSelection;
    if (selection == null) {
      savedLocationWarning =
          'O pedido foi criado, mas faltou a confirmação do mapa para salvar a localização.';
      return;
    }
    final String name = savedLocationName.trim();
    if (name.isEmpty || name.length > SavedLocationDraft.maxNameLength) {
      savedLocationWarning =
          'O pedido foi criado, mas o nome da localização salva é inválido.';
      return;
    }
    final SavedLocationDraft draft = SavedLocationDraft(
      name: name,
      coordinate: coordinate,
      mapProvider: selection.mapProvider,
      mapType: selection.mapType,
      regionConfirmed: selection.regionConfirmed,
      exactPointSelected: selection.exactPointSelected,
      userConfirmed: selection.userConfirmed,
      userConfirmedSafeArea: selection.safeAreaConfirmed,
      addressReference: finalAddressReference,
      instructions: deliveryInstructions,
    );
    saveCurrentLocation = false;
    savedLocationName = '';
    isSavingLocationAfterOrder = true;
    final int sessionGeneration = _sessionGeneration;
    final Future<void> pending = _saveLocationAfterOrder(
      draft,
      sessionGeneration,
    );
    pendingSavedLocationSave = pending;
    unawaited(
      pending.whenComplete(() {
        if (!_isCurrentSession(sessionGeneration)) return;
        if (!identical(pendingSavedLocationSave, pending)) return;
        pendingSavedLocationSave = null;
        isSavingLocationAfterOrder = false;
        if (!_disposed) notifyListeners();
      }),
    );
  }

  Future<void> _saveLocationAfterOrder(
    SavedLocationDraft draft,
    int sessionGeneration,
  ) async {
    try {
      await savedLocations.create(draft);
    } on Object catch (error) {
      if (!_isCurrentSession(sessionGeneration)) return;
      if (error is ApiException &&
          error.code == 'SAVED_LOCATION_LIMIT_REACHED') {
        await savedLocations.refresh();
        if (!_isCurrentSession(sessionGeneration)) return;
      }
      final String message = error.toString().trim();
      savedLocationWarning = message.isEmpty
          ? 'O pedido foi criado, mas a localização não pôde ser salva.'
          : 'O pedido foi criado, mas a localização não pôde ser salva: $message';
    }
  }

  bool _isCurrentSession(int generation) =>
      !_disposed && generation == _sessionGeneration;

  @override
  void dispose() {
    _disposed = true;
    orders.dispose();
    savedLocations.dispose();
    disposeResources?.call();
    super.dispose();
  }
}
