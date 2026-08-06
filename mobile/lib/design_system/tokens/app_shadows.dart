import 'package:flutter/material.dart';

abstract final class AppShadows {
  static const List<BoxShadow> card = <BoxShadow>[
    BoxShadow(color: Color(0x120F274A), blurRadius: 18, offset: Offset(0, 6)),
  ];

  static const List<BoxShadow> floating = <BoxShadow>[
    BoxShadow(color: Color(0x24174A9C), blurRadius: 24, offset: Offset(0, 10)),
  ];
}
