import 'package:flutter/material.dart';

import '../../core/models/product.dart';
import '../tokens/app_colors.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_radii.dart';

class ProductArtwork extends StatelessWidget {
  const ProductArtwork({
    required this.kind,
    this.imageUrl,
    this.semanticLabel,
    this.height = 126,
    super.key,
  });

  final ProductKind kind;
  final String? imageUrl;
  final String? semanticLabel;
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
    final Widget fallback = Container(
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
    final String? normalizedUrl = _networkUrl(imageUrl);
    final Widget artwork = normalizedUrl == null
        ? fallback
        : ClipRRect(
            borderRadius: AppRadii.small,
            child: Image.network(
              normalizedUrl,
              height: height,
              width: double.infinity,
              fit: BoxFit.cover,
              excludeFromSemantics: true,
              loadingBuilder:
                  (
                    BuildContext context,
                    Widget child,
                    ImageChunkEvent? loadingProgress,
                  ) => loadingProgress == null ? child : fallback,
              errorBuilder:
                  (
                    BuildContext context,
                    Object error,
                    StackTrace? stackTrace,
                  ) => fallback,
            ),
          );
    return Semantics(
      image: true,
      label: semanticLabel ?? 'Imagem ilustrativa do produto',
      child: ExcludeSemantics(child: artwork),
    );
  }

  static String? _networkUrl(String? value) {
    final String normalized = value?.trim() ?? '';
    final Uri? uri = Uri.tryParse(normalized);
    if (uri == null ||
        !uri.hasAuthority ||
        (uri.scheme != 'https' && uri.scheme != 'http')) {
      return null;
    }
    return normalized;
  }
}
