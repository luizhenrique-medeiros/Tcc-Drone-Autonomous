import 'package:flutter/material.dart';

import '../../app/app_scope.dart';
import '../../core/models/order.dart';
import '../../core/models/product.dart';
import '../components/app_banner.dart';
import '../components/app_button.dart';
import '../components/app_text_field.dart';
import '../components/brand_mark.dart';
import '../components/product_card.dart';
import '../components/section_header.dart';
import '../components/status_pill.dart';
import '../components/surface_card.dart';
import '../tokens/app_colors.dart';
import '../tokens/app_radii.dart';
import '../tokens/app_spacing.dart';
import '../tokens/app_typography.dart';

class DesignCatalogScreen extends StatefulWidget {
  const DesignCatalogScreen({super.key});

  @override
  State<DesignCatalogScreen> createState() => _DesignCatalogScreenState();
}

class _DesignCatalogScreenState extends State<DesignCatalogScreen> {
  final TextEditingController _fieldController = TextEditingController();

  @override
  void dispose() {
    _fieldController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final List<Product> products = AppScope.of(context).products;
    return Scaffold(
      appBar: AppBar(title: const Text('Catálogo do design system')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          const Center(child: BrandMark(compact: true)),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(
            title: 'Cores semânticas',
            subtitle: 'Nunca use a cor como único indicador de estado.',
          ),
          const Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: <Widget>[
              _ColorSwatch(label: 'Marca', color: AppColors.brandBlue),
              _ColorSwatch(label: 'Ação', color: AppColors.accentOrange),
              _ColorSwatch(label: 'Sucesso', color: AppColors.success),
              _ColorSwatch(label: 'Alerta', color: AppColors.warning),
              _ColorSwatch(label: 'Erro', color: AppColors.danger),
              _ColorSwatch(label: 'Texto', color: AppColors.navy),
            ],
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Tipografia'),
          const SurfaceCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text('Display 32', style: AppTypography.display),
                SizedBox(height: AppSpacing.xs),
                Text('Headline 24', style: AppTypography.headline),
                SizedBox(height: AppSpacing.xs),
                Text('Título 18', style: AppTypography.title),
                SizedBox(height: AppSpacing.xs),
                Text('Texto de corpo acessível', style: AppTypography.body),
                SizedBox(height: AppSpacing.xs),
                Text('Legenda e metadados', style: AppTypography.caption),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Botões'),
          AppButton(label: 'Ação primária', onPressed: () {}),
          const SizedBox(height: AppSpacing.sm),
          AppButton(
            label: 'Ação de conversão',
            variant: AppButtonVariant.accent,
            onPressed: () {},
          ),
          const SizedBox(height: AppSpacing.sm),
          AppButton(
            label: 'Ação secundária',
            variant: AppButtonVariant.secondary,
            onPressed: () {},
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Campo de formulário'),
          AppTextField(
            controller: _fieldController,
            label: 'Rótulo do campo',
            hint: 'Ajuda contextual',
            icon: Icons.edit_outlined,
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Mensagens'),
          const AppBanner(
            title: 'Informação',
            message: 'Mensagem informativa com ícone e texto.',
          ),
          const SizedBox(height: AppSpacing.sm),
          const AppBanner(
            title: 'Atenção',
            message: 'Mensagem que exige conferência do usuário.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.sm),
          const AppBanner(
            title: 'Falha explícita',
            message: 'Erros nunca são convertidos silenciosamente em sucesso.',
            tone: AppBannerTone.danger,
          ),
          const SizedBox(height: AppSpacing.xl),
          const SectionHeader(title: 'Estados do pedido'),
          const Wrap(
            spacing: AppSpacing.xs,
            runSpacing: AppSpacing.xs,
            children: <Widget>[
              StatusPill(status: OrderStatus.pendingAdminApproval),
              StatusPill(status: OrderStatus.waitingFlightAuthorization),
              StatusPill(status: OrderStatus.inTransit),
              StatusPill(status: OrderStatus.completed),
              StatusPill(status: OrderStatus.rejected),
              StatusPill(status: OrderStatus.failed),
            ],
          ),
          if (products.isNotEmpty) ...<Widget>[
            const SizedBox(height: AppSpacing.xl),
            const SectionHeader(title: 'Card de produto'),
            Align(
              alignment: Alignment.centerLeft,
              child: SizedBox(
                width: 220,
                height: 320,
                child: ProductCard(
                  product: products.first,
                  onTap: () {},
                  onAdd: () {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Componente acionado.')),
                    );
                  },
                ),
              ),
            ),
          ],
          const SizedBox(height: AppSpacing.xl),
        ],
      ),
    );
  }
}

class _ColorSwatch extends StatelessWidget {
  const _ColorSwatch({required this.label, required this.color});

  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 96,
      padding: const EdgeInsets.all(AppSpacing.sm),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        borderRadius: AppRadii.small,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: <Widget>[
          Container(
            width: 52,
            height: 52,
            decoration: BoxDecoration(color: color, shape: BoxShape.circle),
          ),
          const SizedBox(height: AppSpacing.xs),
          Text(label, style: AppTypography.caption),
        ],
      ),
    );
  }
}
