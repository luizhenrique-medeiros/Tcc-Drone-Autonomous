abstract final class AppBreakpoints {
  static const double compact = 360;
  static const double medium = 600;
  static const double expanded = 840;
  static const double contentMaxWidth = 1440;

  static int productColumns(double width) {
    if (width >= expanded) return 4;
    if (width >= medium) return 3;
    if (width < compact) return 1;
    return 2;
  }
}
