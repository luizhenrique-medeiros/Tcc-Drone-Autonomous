import 'package:drone_delivery_mobile/core/maps/latest_target_queue.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late LatestTargetQueue<int> queue;

  setUp(() {
    queue = LatestTargetQueue<int>(equals: (first, second) => first == second);
  });

  test(
    'cancels a newer pending move when request returns to active target',
    () {
      queue.request(1, applied: 0);
      expect(queue.beginNext(applied: 0), 1);

      queue.request(2, applied: 0);
      queue.request(1, applied: 0);
      queue.completeActive();

      expect(queue.beginNext(applied: 1), isNull);
    },
  );

  test('returns to applied target after an in-flight move finishes', () {
    queue.request(1, applied: 0);
    expect(queue.beginNext(applied: 0), 1);

    queue.request(0, applied: 0);
    queue.completeActive();

    expect(queue.beginNext(applied: 1), 0);
  });

  test('keeps only the latest target requested during an active move', () {
    queue.request(1, applied: 0);
    expect(queue.beginNext(applied: 0), 1);

    queue.request(2, applied: 0);
    queue.request(3, applied: 0);
    queue.completeActive();

    expect(queue.beginNext(applied: 1), 3);
  });
}
