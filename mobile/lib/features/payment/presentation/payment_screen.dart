import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/models/order.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/product_card.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../tracking/presentation/order_tracking_screen.dart';

class PaymentScreen extends StatefulWidget {
  const PaymentScreen({super.key});

  @override
  State<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends State<PaymentScreen> {
  Future<void> _submit() async {
    final AppController controller = AppScope.of(context);
    final String? error = await controller.submitOrder();
    if (!mounted) return;
    if (error != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: AppColors.danger),
      );
      return;
    }
    await Navigator.of(context).pushAndRemoveUntil<void>(
      MaterialPageRoute<void>(builder: (_) => const OrderTrackingScreen()),
      (Route<Object?> route) => route.isFirst,
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Forma de pagamento')),
      body: ListView(
        padding: const EdgeInsets.all(AppSpacing.screen),
        children: <Widget>[
          const AppBanner(
            title: 'Pagamento 100% simulado',
            message:
                'Nenhum cartão, CVV, validade, chave PIX ou dado bancário será solicitado, armazenado ou processado.',
            tone: AppBannerTone.warning,
          ),
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(
            title: 'Escolha apenas para registro acadêmico',
            subtitle: 'A opção selecionada não realiza cobrança.',
          ),
          _PaymentTile(
            method: SimulatedPaymentMethod.pix,
            selected: controller.paymentMethod == SimulatedPaymentMethod.pix,
            icon: Icons.pix,
            description: 'Registra PIX como preferência simulada.',
            onTap: () => controller.selectPayment(SimulatedPaymentMethod.pix),
          ),
          const SizedBox(height: AppSpacing.sm),
          _PaymentTile(
            method: SimulatedPaymentMethod.creditCard,
            selected:
                controller.paymentMethod == SimulatedPaymentMethod.creditCard,
            icon: Icons.credit_card,
            description:
                'Registra crédito simulado sem coletar números ou titular.',
            onTap: () =>
                controller.selectPayment(SimulatedPaymentMethod.creditCard),
          ),
          const SizedBox(height: AppSpacing.lg),
          const SectionHeader(title: 'Resumo'),
          SurfaceCard(
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
          ),
          const SizedBox(height: AppSpacing.lg),
          AppButton(
            key: const Key('submit-simulated-order'),
            label: 'Enviar pedido para aprovação',
            variant: AppButtonVariant.accent,
            icon: Icons.send_outlined,
            loading: controller.isSubmittingOrder,
            onPressed: controller.isSubmittingOrder ? null : _submit,
          ),
          const SizedBox(height: AppSpacing.sm),
          const Text(
            'O envio cria um pedido pendente. Aprovar o pedido e autorizar o voo são ações administrativas separadas.',
            style: AppTypography.caption,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}

class _PaymentTile extends StatelessWidget {
  const _PaymentTile({
    required this.method,
    required this.selected,
    required this.icon,
    required this.description,
    required this.onTap,
  });

  final SimulatedPaymentMethod method;
  final bool selected;
  final IconData icon;
  final String description;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SurfaceCard(
      onTap: onTap,
      borderColor: selected ? AppColors.brandBlue : AppColors.border,
      child: Row(
        children: <Widget>[
          Container(
            width: 52,
            height: 52,
            decoration: const BoxDecoration(
              color: AppColors.brandBlueSoft,
              shape: BoxShape.circle,
            ),
            child: Icon(
              icon,
              size: AppIconSizes.medium,
              color: AppColors.brandBlue,
            ),
          ),
          const SizedBox(width: AppSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: <Widget>[
                Text(method.label, style: AppTypography.bodyStrong),
                Text(description, style: AppTypography.caption),
              ],
            ),
          ),
          Icon(
            selected ? Icons.check_circle : Icons.radio_button_unchecked,
            color: selected ? AppColors.brandBlue : AppColors.slateLight,
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
