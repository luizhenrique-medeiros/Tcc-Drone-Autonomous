typedef TargetEquals<T> = bool Function(T first, T second);

/// Serializes asynchronous moves while keeping only the latest requested
/// target.
class LatestTargetQueue<T extends Object> {
  LatestTargetQueue({required TargetEquals<T> equals}) : _equals = equals;

  final TargetEquals<T> _equals;
  T? _active;
  T? _pending;

  /// Records the latest target requested by the UI.
  ///
  /// When the request returns to the move that is already active, any newer
  /// pending move is obsolete and is discarded.
  void request(T target, {required T applied}) {
    final T? active = _active;
    if (active != null) {
      _pending = _equals(target, active) ? null : target;
      return;
    }

    final T? pending = _pending;
    if (pending != null && _equals(target, pending)) return;
    _pending = _equals(target, applied) ? null : target;
  }

  /// Starts the next move, if the desired target differs from the target
  /// currently applied to the map.
  T? beginNext({required T applied}) {
    if (_active != null) return null;
    final T? next = _pending;
    _pending = null;
    if (next == null || _equals(next, applied)) return null;
    _active = next;
    return next;
  }

  void completeActive() {
    _active = null;
  }

  void clear() {
    _active = null;
    _pending = null;
  }
}
