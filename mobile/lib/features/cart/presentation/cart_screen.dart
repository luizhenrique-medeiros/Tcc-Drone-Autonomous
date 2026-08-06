import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/order.dart';
import '../../../core/models/product.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/product_artwork.dart';
import '../../../design_system/components/product_card.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../delivery_point/presentation/approximate_location_screen.dart';

class CartScreen extends StatelessWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final List<CartLine> lines = controller.cartLines;
    return Scaffold(
      appBar: AppBar(title: const Text('Seu carrinho')),
      body: lines.isEmpty
          ? const _EmptyCart()
          : ListView(
              padding: const EdgeInsets.all(AppSpacing.screen),
              children: <Widget>[
                const AppBanner(
                  title: 'Itens demonstrativos',
                  message:
                      'O catálogo não representa venda real. O fluxo acadêmico inicia após a confirmação.',
                ),
                const SizedBox(height: AppSpacing.lg),
                const SectionHeader(title: 'Itens selecionados'),
                for (final CartLine line in lines) ...<Widget>[
                  _CartLineCard(line: line, controller: controller),
                  const SizedBox(height: AppSpacing.sm),
                ],
                const SizedBox(height: AppSpacing.lg),
                _OrderSummary(controller: controller),
                const SizedBox(height: AppSpacing.lg),
                AppButton(
                  label: 'Escolher ponto de entrega',
                  variant: AppButtonVariant.accent,
                  icon: Icons.map_outlined,
                  onPressed: () async {
                    await Navigator.of(context).push<void>(
                      MaterialPageRoute<void>(
                        builder: (_) => const ApproximateLocationScreen(),
                      ),
                    );
                  },
                ),
              ],
            ),
    );
  }
}

class _CartLineCard extends StatelessWidget {
  const _CartLineCard({required this.line, required this.controller});

  final CartLine line;
  final AppController controller;

  @override
  Widget build(BuildContext context) {
    final Product product = controller.products.firstWhere(
      (Product item) => item.id == line.productId,
    );
    return SurfaceCard(
      child: Row(
        children: <Widget>[
          SizedBox(
            width: 72,
            child: ProductArtwork(kind: product.kind, height: 72),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(line.name, style: AppTypography.bodyStrong),
                const SizedBox(height: AppSpacing.xxs),
                Text(
                  formatCurrency(line.unitPrice),
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
          Row(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              IconButton(
                tooltip: 'Remover uma unidade',
                onPressed: () => controller.decrementProduct(product),
                icon: const Icon(Icons.remove_circle_outline),
              ),
              Text('${line.quantity}', style: AppTypography.bodyStrong),
              IconButton(
                tooltip: 'Adicionar uma unidade',
                onPressed: () => controller.addProduct(product),
                icon: const Icon(Icons.add_circle, color: AppColors.brandBlue),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _OrderSummary extends StatelessWidget {
  const _OrderSummary({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      child: Column(
        children: <Widget>[
          _SummaryLine(
            label: 'Subtotal',
            value: formatCurrency(controller.subtotal),
          ),
          const SizedBox(height: AppSpacing.sm),
          _SummaryLine(
            label: 'Taxa de entrega',
            value: formatCurrency(controller.deliveryFee),
          ),
          const Divider(height: AppSpacing.lg),
          _SummaryLine(
            label: 'Total simulado',
            value: formatCurrency(controller.total),
            emphasized: true,
          ),
        ],
      ),
    );
  }
}

class _SummaryLine extends StatelessWidget {
  const _SummaryLine({
    required this.label,
    required this.value,
    this.emphasized = false,
  });

  final String label;
  final String value;
  final bool emphasized;

  @override
  Widget build(BuildContext context) {
    final TextStyle style = emphasized
        ? AppTypography.title
        : AppTypography.body;
    return Row(
      children: <Widget>[
        Expanded(child: Text(label, style: style)),
        Text(value, style: style),
      ],
    );
  }
}

class _EmptyCart extends StatelessWidget {
  const _EmptyCart();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            const Icon(
              Icons.remove_shopping_cart_outlined,
              size: AppIconSizes.hero,
              color: AppColors.slateLight,
            ),
            const SizedBox(height: AppSpacing.md),
            const Text('Seu carrinho está vazio', style: AppTypography.title),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Volte ao catálogo e escolha um produto demonstrativo.',
              style: AppTypography.body,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.lg),
            AppButton(
              label: 'Voltar ao catálogo',
              expand: false,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}
