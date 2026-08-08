import 'package:flutter/material.dart';

import '../../core/models/product.dart';
import '../tokens/app_colors.dart';
import '../tokens/app_icon_sizes.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';
import 'product_artwork.dart';
import 'surface_card.dart';

class ProductCard extends StatelessWidget {
  const ProductCard({
    required this.product,
    required this.onTap,
    required this.onAdd,
    super.key,
  });

  final Product product;
  final VoidCallback onTap;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      padding: const EdgeInsets.all(AppSpacing.xs),
      elevated: true,
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          ProductArtwork(
            kind: product.kind,
            imageUrl: product.imageUrl,
            semanticLabel: product.name,
          ),
          const SizedBox(height: AppSpacing.sm),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xs),
            child: Text(
              product.name,
              style: AppTypography.bodyStrong,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.all(AppSpacing.xs),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    formatCurrency(product.price),
                    style: AppTypography.label.copyWith(
                      color: AppColors.brandBlueDark,
                    ),
                  ),
                ),
                Semantics(
                  button: true,
                  label: 'Adicionar ${product.name} ao carrinho',
                  child: IconButton.filled(
                    onPressed: onAdd,
                    icon: const Icon(Icons.add, size: AppIconSizes.small),
                    style: IconButton.styleFrom(
                      backgroundColor: AppColors.accentOrange,
                      foregroundColor: AppColors.surface,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String formatCurrency(double value) {
  return 'R\$ ${value.toStringAsFixed(2).replaceAll('.', ',')}';
}
