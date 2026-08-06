import 'package:flutter/material.dart';

import '../../core/models/product.dart';
import '../tokens/app_colors.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_radii.dart';

class ProductArtwork extends StatelessWidget {
  const ProductArtwork({required this.kind, this.height = 126, super.key});

  final ProductKind kind;
  final double height;

  @override
  Widget build(BuildContext context) {
    final (IconData icon, List<Color> colors) = switch (kind) {
      ProductKind.pizza => (
        Icons.local_pizza_rounded,
        <Color>[const Color(0xFFFFE6B8), AppColors.accentOrange],
      ),
      ProductKind.grocery => (
        Icons.shopping_bag_rounded,
        <Color>[const Color(0xFFE6F5CF), AppColors.success],
      ),
      ProductKind.burger => (
        Icons.lunch_dining_rounded,
        <Color>[const Color(0xFFFFEACB), AppColors.warning],
      ),
      ProductKind.sushi => (
        Icons.set_meal_rounded,
        <Color>[const Color(0xFFFFDFDF), AppColors.danger],
      ),
      ProductKind.dessert => (
        Icons.cake_rounded,
        <Color>[const Color(0xFFF3E2FF), const Color(0xFF9C65CC)],
      ),
      ProductKind.drink => (
        Icons.local_drink_rounded,
        <Color>[const Color(0xFFDFF6FF), AppColors.info],
      ),
    };
    return Container(
      height: height,
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: AppRadii.small,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: colors,
        ),
      ),
      alignment: Alignment.center,
      child: Icon(
        icon,
        size: AppIconSizes.hero,
        color: AppColors.surface.withValues(alpha: 0.92),
      ),
    );
  }
}
