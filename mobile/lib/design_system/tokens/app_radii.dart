import 'package:flutter/widgets.dart';

abstract final class AppRadii {
  static const double smallValue = 8;
  static const double mediumValue = 14;
  static const double largeValue = 22;
  static const double pillValue = 999;

  static const BorderRadius small = BorderRadius.all(
    Radius.circular(smallValue),
  );
  static const BorderRadius medium = BorderRadius.all(
    Radius.circular(mediumValue),
  );
  static const BorderRadius large = BorderRadius.all(
    Radius.circular(largeValue),
  );
  static const BorderRadius pill = BorderRadius.all(Radius.circular(pillValue));
}
