import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
import '../../../core/models/product.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/product_artwork.dart';
import '../../../design_system/components/product_card.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';

class ProductDetailScreen extends StatelessWidget {
  const ProductDetailScreen({required this.product, super.key});

  final Product product;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Detalhes do produto')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          ProductArtwork(kind: product.kind, height: 240),
          const SizedBox(height: AppSpacing.lg),
          Text(product.name, style: AppTypography.headline),
          const SizedBox(height: AppSpacing.sm),
          Row(
            children: <Widget>[
              const Icon(
                Icons.star_rounded,
                color: AppColors.accentYellow,
                size: AppIconSizes.medium,
              ),
              const SizedBox(width: AppSpacing.xs),
              Text('${product.rating} (avaliação demonstrativa)'),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Text(
            'De ${formatCurrency(product.price)} / un.',
            style: AppTypography.title,
          ),
          const SizedBox(height: AppSpacing.lg),
          SurfaceCard(
            child: Column(
              children: <Widget>[
                _DetailLine(
                  icon: Icons.schedule,
                  label: 'Entrega aproximada',
                  value: '${product.estimatedMinutes} min',
                ),
                const SizedBox(height: AppSpacing.sm),
                const _DetailLine(
                  icon: Icons.location_on_outlined,
                  label: 'Taxa de entrega',
                  value: 'R\$ 7,50',
                ),
                const SizedBox(height: AppSpacing.sm),
                const _DetailLine(
                  icon: Icons.verified_outlined,
                  label: 'Catálogo',
                  value: 'Demonstração acadêmica',
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(title: 'Descrição'),
          Text(product.description, style: AppTypography.body),
          const SizedBox(height: AppSpacing.xl),
          AppButton(
            label: 'Adicionar ao carrinho',
            variant: AppButtonVariant.accent,
            icon: Icons.add_shopping_cart,
            onPressed: () {
              AppScope.of(context).addProduct(product);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('${product.name} adicionado.')),
              );
            },
          ),
        ],
      ),
    );
  }
}

class _DetailLine extends StatelessWidget {
  const _DetailLine({
    required this.icon,
    required this.label,
    required this.value,
  });

  final IconData icon;
  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        Icon(icon, color: AppColors.accentYellow),
        const SizedBox(width: AppSpacing.sm),
        Expanded(child: Text(label, style: AppTypography.label)),
        Text(value, style: AppTypography.body),
      ],
    );
  }
}
