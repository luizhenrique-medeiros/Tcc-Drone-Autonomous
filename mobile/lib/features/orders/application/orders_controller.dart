import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../core/models/order.dart';
import '../../../core/network/api_client.dart';
import '../../../core/repositories/order_repository.dart';

class OrdersController extends ChangeNotifier {
  OrdersController({required OrderRepository repository, this.pageSize = 20})
    : _repository = repository;

  final OrderRepository _repository;
  final int pageSize;
  final List<OrderSnapshot> _orders = <OrderSnapshot>[];
  final Map<String, StreamSubscription<OrderWatchEvent>> _subscriptions =
      <String, StreamSubscription<OrderWatchEvent>>{};
  final Map<String, OrderRealtimeState> _connectionStates =
      <String, OrderRealtimeState>{};
  final Set<String> _detailLoading = <String>{};
  final Map<String, String> _detailErrors = <String, String>{};

  OrdersGroup group = OrdersGroup.all;
  bool hasLoaded = false;
  bool isInitialLoading = false;
  bool isRefreshing = false;
  bool isLoadingMore = false;
  bool hasMore = false;
  bool isOffline = false;
  String? loadError;
  String? refreshError;
  int _nextOffset = 0;
  int _paginationBacktrack = 0;
  int _requestGeneration = 0;
  Future<void>? _initialLoad;
  int? _initialLoadGeneration;
  bool _disposed = false;

  List<OrderSnapshot> get orders => _visibleOrders().toList(growable: false);

  List<OrderSnapshot> get activeOrders =>
      _orders
          .where((OrderSnapshot order) => order.status.isActive)
          .toList(growable: false)
        ..sort(_compareNewestFirst);

  List<OrderSnapshot> get historyOrders =>
      _orders
          .where((OrderSnapshot order) => order.status.isTerminal)
          .toList(growable: false)
        ..sort(_compareNewestFirst);

  bool get isEmpty => hasLoaded && orders.isEmpty && loadError == null;

  OrderRealtimeState get realtimeState {
    final List<OrderSnapshot> active = activeOrders;
    if (active.isEmpty) return OrderRealtimeState.connected;
    final Iterable<OrderRealtimeState> states = active.map(
      (OrderSnapshot order) =>
          _connectionStates[order.id] ?? OrderRealtimeState.connecting,
    );
    if (states.any(
      (OrderRealtimeState state) => state == OrderRealtimeState.unavailable,
    )) {
      return OrderRealtimeState.unavailable;
    }
    if (states.any(
      (OrderRealtimeState state) =>
          state == OrderRealtimeState.connecting ||
          state == OrderRealtimeState.reconnecting,
    )) {
      return OrderRealtimeState.reconnecting;
    }
    return OrderRealtimeState.connected;
  }

  OrderRealtimeState realtimeStateFor(String orderId) {
    final OrderSnapshot? order = orderById(orderId);
    if (order?.status.isActive != true) return OrderRealtimeState.connected;
    return _connectionStates[orderId] ?? OrderRealtimeState.connecting;
  }

  OrderSnapshot? orderById(String orderId) {
    for (final OrderSnapshot order in _orders) {
      if (order.id == orderId) return order;
    }
    return null;
  }

  bool isDetailLoading(String orderId) => _detailLoading.contains(orderId);

  String? detailError(String orderId) => _detailErrors[orderId];

  Future<void> loadInitial({bool force = false}) {
    if (hasLoaded && !force) return Future<void>.value();
    if (force) {
      _requestGeneration++;
      isInitialLoading = false;
      isRefreshing = false;
      isLoadingMore = false;
    }
    final int generation = _requestGeneration;
    if (_initialLoad case final Future<void> pending
        when _initialLoadGeneration == generation) {
      return pending;
    }
    final Future<void> pending = _loadFirstPage(
      initial: true,
      generation: generation,
      requestedGroup: group,
    );
    _initialLoad = pending;
    _initialLoadGeneration = generation;
    return pending.whenComplete(() {
      if (identical(_initialLoad, pending)) {
        _initialLoad = null;
        _initialLoadGeneration = null;
      }
    });
  }

  Future<void> refresh() {
    if (isRefreshing) return Future<void>.value();
    final int generation = ++_requestGeneration;
    isInitialLoading = false;
    isLoadingMore = false;
    return _loadFirstPage(
      initial: false,
      generation: generation,
      requestedGroup: group,
    );
  }

  Future<void> _loadFirstPage({
    required bool initial,
    required int generation,
    required OrdersGroup requestedGroup,
  }) async {
    if (initial) {
      isInitialLoading = true;
      loadError = null;
    } else {
      if (isRefreshing) return;
      isRefreshing = true;
      refreshError = null;
    }
    _notify();
    try {
      final OrdersPage page = await _repository.listOrders(
        group: requestedGroup,
        limit: pageSize,
        offset: 0,
      );
      if (!_isCurrentRequest(generation, requestedGroup)) return;
      final Map<String, OrderSnapshot> cached = <String, OrderSnapshot>{
        for (final OrderSnapshot order in _orders) order.id: order,
      };
      _orders
        ..clear()
        ..addAll(
          page.items.map((OrderSnapshot order) {
            final OrderSnapshot? current = cached[order.id];
            return current == null ? order : _preferComplete(order, current);
          }),
        );
      _sortOrders();
      _nextOffset = page.returnedCount;
      _paginationBacktrack = 0;
      hasMore = page.hasMore;
      hasLoaded = true;
      isOffline = false;
      loadError = null;
      refreshError = null;
      await _syncWatchers();
    } on Object catch (error) {
      if (!_isCurrentRequest(generation, requestedGroup)) return;
      final String message = _errorMessage(error);
      isOffline = _isOfflineError(error);
      if (!hasLoaded || _orders.isEmpty) {
        loadError = message;
      } else {
        refreshError = message;
      }
    } finally {
      if (_isCurrentRequest(generation, requestedGroup)) {
        isInitialLoading = false;
        isRefreshing = false;
        _notify();
      }
    }
  }

  Future<void> loadMore() async {
    if (!hasMore || isLoadingMore || isRefreshing || isInitialLoading) return;
    isLoadingMore = true;
    refreshError = null;
    _notify();
    final int generation = _requestGeneration;
    final OrdersGroup requestedGroup = group;
    final int appliedBacktrack = _paginationBacktrack;
    final int requestOffset = _nextOffset > appliedBacktrack
        ? _nextOffset - appliedBacktrack
        : 0;
    try {
      final OrdersPage page = await _repository.listOrders(
        group: requestedGroup,
        limit: pageSize,
        offset: requestOffset,
      );
      if (!_isCurrentRequest(generation, requestedGroup)) return;
      _nextOffset = requestOffset + page.returnedCount;
      _paginationBacktrack = _paginationBacktrack > appliedBacktrack
          ? _paginationBacktrack - appliedBacktrack
          : 0;
      hasMore = page.hasMore;
      for (final OrderSnapshot order in page.items) {
        _upsert(order, notify: false);
      }
      _sortOrders();
      isOffline = false;
      await _syncWatchers();
    } on Object catch (error) {
      if (_isCurrentRequest(generation, requestedGroup)) {
        refreshError = _errorMessage(error);
        isOffline = _isOfflineError(error);
      }
    } finally {
      if (_isCurrentRequest(generation, requestedGroup)) {
        isLoadingMore = false;
        _notify();
      }
    }
  }

  Future<void> selectGroup(OrdersGroup value) async {
    if (group == value && hasLoaded) return;
    group = value;
    final int generation = ++_requestGeneration;
    hasLoaded = false;
    hasMore = false;
    isOffline = false;
    isInitialLoading = false;
    isRefreshing = false;
    isLoadingMore = false;
    loadError = null;
    refreshError = null;
    _nextOffset = 0;
    _paginationBacktrack = 0;
    _orders.clear();
    await _cancelAllWatchers();
    if (!_isCurrentRequest(generation, value)) return;
    _notify();
    await _loadFirstPage(
      initial: true,
      generation: generation,
      requestedGroup: value,
    );
  }

  Future<void> loadDetails(String orderId, {bool force = false}) async {
    final OrderSnapshot? cached = orderById(orderId);
    if (!force && cached?.detailLoaded == true) {
      _ensureWatching(cached!);
      return;
    }
    if (_detailLoading.contains(orderId)) return;
    _detailLoading.add(orderId);
    _detailErrors.remove(orderId);
    _notify();
    try {
      final OrderSnapshot order = await _repository.getOrder(orderId);
      _upsert(order, notify: false);
      _ensureWatching(order);
    } on Object catch (error) {
      _detailErrors[orderId] = _errorMessage(error);
    } finally {
      _detailLoading.remove(orderId);
      _notify();
    }
  }

  void upsertSubmitted(OrderSnapshot order, {bool watch = true}) {
    hasLoaded = true;
    loadError = null;
    _upsert(order, notify: false);
    if (watch) _ensureWatching(order);
    _notify();
  }

  void _upsert(OrderSnapshot order, {required bool notify}) {
    final int index = _orders.indexWhere(
      (OrderSnapshot current) => current.id == order.id,
    );
    if (index == -1) {
      _orders.add(order);
    } else {
      final OrderSnapshot current = _orders[index];
      _orders[index] = _preferComplete(order, current);
    }
    _sortOrders();
    if (notify) _notify();
  }

  OrderSnapshot _preferComplete(OrderSnapshot incoming, OrderSnapshot current) {
    if (incoming.detailLoaded || !current.detailLoaded) return incoming;
    return OrderSnapshot(
      id: current.id,
      status: incoming.status,
      rejectionReason: incoming.rejectionReason ?? current.rejectionReason,
      lastEventAt: incoming.lastEventAt ?? current.lastEventAt,
      paymentMethod: current.paymentMethod,
      subtotal: current.subtotal,
      deliveryFee: current.deliveryFee,
      discount: current.discount,
      total: current.total,
      items: current.items,
      deliveryPoint: current.deliveryPoint,
      submittedAt: current.submittedAt,
      completedAt: incoming.completedAt ?? current.completedAt,
      createdAt: current.createdAt,
      updatedAt: incoming.updatedAt ?? current.updatedAt,
      milestones: current.milestones,
      detailLoaded: true,
    );
  }

  Iterable<OrderSnapshot> _visibleOrders() sync* {
    for (final OrderSnapshot order in _orders) {
      if (order.status == OrderStatus.draft) continue;
      final bool visible = switch (group) {
        OrdersGroup.all => true,
        OrdersGroup.active => order.status.isActive,
        OrdersGroup.history => order.status.isTerminal,
      };
      if (visible) yield order;
    }
  }

  void _sortOrders() {
    _orders.sort((OrderSnapshot first, OrderSnapshot second) {
      if (group == OrdersGroup.all &&
          first.status.isActive != second.status.isActive) {
        return first.status.isActive ? -1 : 1;
      }
      return _compareNewestFirst(first, second);
    });
  }

  Future<void> _syncWatchers() async {
    final Set<String> activeIds = _orders
        .where((OrderSnapshot order) => order.status.isActive)
        .map((OrderSnapshot order) => order.id)
        .toSet();
    final List<String> obsolete = _subscriptions.keys
        .where((String orderId) => !activeIds.contains(orderId))
        .toList(growable: false);
    for (final String orderId in obsolete) {
      await _subscriptions.remove(orderId)?.cancel();
      _connectionStates.remove(orderId);
    }
    for (final OrderSnapshot order in _orders) {
      _ensureWatching(order);
    }
  }

  void _ensureWatching(OrderSnapshot order) {
    if (!order.status.isActive || _subscriptions.containsKey(order.id)) return;
    _connectionStates[order.id] = OrderRealtimeState.connecting;
    _subscriptions[order.id] = _repository
        .watchOrder(order.id)
        .listen(
          (OrderWatchEvent event) {
            if (_disposed) return;
            switch (event) {
              case OrderSnapshotEvent(:final order):
                final OrderSnapshot? previous = orderById(order.id);
                if (previous?.status.isActive == true &&
                    order.status.isTerminal) {
                  _paginationBacktrack++;
                }
                _upsert(order, notify: false);
                if (order.status.isTerminal) {
                  _connectionStates.remove(order.id);
                }
              case OrderConnectionEvent(:final state):
                _connectionStates[order.id] = state;
            }
            _notify();
          },
          onError: (Object error) {
            if (_disposed) return;
            _connectionStates[order.id] = OrderRealtimeState.unavailable;
            refreshError = 'Atualização em tempo real indisponível: $error';
            _notify();
          },
          onDone: () {
            if (_disposed) return;
            _subscriptions.remove(order.id);
            final OrderSnapshot? current = orderById(order.id);
            if (current?.status.isActive == true) {
              _connectionStates[order.id] = OrderRealtimeState.unavailable;
            } else {
              _connectionStates.remove(order.id);
            }
            _notify();
          },
        );
  }

  Future<void> reset() async {
    await _cancelAllWatchers();
    _orders.clear();
    _detailLoading.clear();
    _detailErrors.clear();
    group = OrdersGroup.all;
    hasLoaded = false;
    isInitialLoading = false;
    isRefreshing = false;
    isLoadingMore = false;
    hasMore = false;
    isOffline = false;
    loadError = null;
    refreshError = null;
    _nextOffset = 0;
    _paginationBacktrack = 0;
    _requestGeneration++;
    _notify();
  }

  Future<void> _cancelAllWatchers() async {
    final List<StreamSubscription<OrderWatchEvent>> subscriptions =
        _subscriptions.values.toList(growable: false);
    _subscriptions.clear();
    _connectionStates.clear();
    for (final StreamSubscription<OrderWatchEvent> subscription
        in subscriptions) {
      await subscription.cancel();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  bool _isCurrentRequest(int generation, OrdersGroup requestedGroup) {
    return !_disposed &&
        generation == _requestGeneration &&
        requestedGroup == group;
  }

  @override
  void dispose() {
    _disposed = true;
    for (final StreamSubscription<OrderWatchEvent> subscription
        in _subscriptions.values) {
      unawaited(subscription.cancel());
    }
    _subscriptions.clear();
    super.dispose();
  }
}

int _compareNewestFirst(OrderSnapshot first, OrderSnapshot second) {
  final DateTime firstDate =
      first.displayDate ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
  final DateTime secondDate =
      second.displayDate ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
  return secondDate.compareTo(firstDate);
}

String _errorMessage(Object error) {
  final String message = error.toString().trim();
  return message.isEmpty ? 'Não foi possível carregar os pedidos.' : message;
}

bool _isOfflineError(Object error) {
  return error is ApiException && error.isConnectivityFailure;
}
