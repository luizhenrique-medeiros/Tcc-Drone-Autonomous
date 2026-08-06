import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../products/presentation/home_screen.dart';
import 'auth_frame.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _name = TextEditingController();
  final TextEditingController _email = TextEditingController();
  final TextEditingController _phone = TextEditingController();
  final TextEditingController _password = TextEditingController();
  final TextEditingController _confirmation = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _password.dispose();
    _confirmation.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final String? error = await AppScope.of(context).register(
      name: _name.text.trim(),
      email: _email.text.trim(),
      password: _password.text,
      phone: _phone.text.trim(),
    );
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = error;
    });
    if (error == null) {
      await Navigator.of(context).pushAndRemoveUntil<void>(
        MaterialPageRoute<void>(builder: (_) => const HomeScreen()),
        (Route<Object?> route) => false,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AuthFrame(
      child: Form(
        key: _formKey,
        child: Column(
          children: <Widget>[
            const Text('Crie sua conta', style: AppTypography.headline),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Cadastro exclusivo de cliente. Administradores não se cadastram aqui.',
              style: AppTypography.body,
              textAlign: TextAlign.center,
            ),
            if (_error != null) ...<Widget>[
              const SizedBox(height: AppSpacing.md),
              AppBanner(
                title: 'Cadastro não concluído',
                message: _error!,
                tone: AppBannerTone.danger,
              ),
            ],
            const SizedBox(height: AppSpacing.lg),
            AppTextField(
              controller: _name,
              label: 'Nome',
              icon: Icons.person_outline,
              textInputAction: TextInputAction.next,
              validator: (String? value) =>
                  (value?.trim().length ?? 0) < 3 ? 'Informe seu nome.' : null,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              controller: _email,
              label: 'E-mail',
              icon: Icons.mail_outline,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              validator: (String? value) => !(value?.contains('@') ?? false)
                  ? 'Informe um e-mail válido.'
                  : null,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              controller: _phone,
              label: 'Telefone (opcional)',
              icon: Icons.phone_outlined,
              keyboardType: TextInputType.phone,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              controller: _password,
              label: 'Senha',
              icon: Icons.lock_outline,
              obscureText: true,
              textInputAction: TextInputAction.next,
              validator: (String? value) => (value?.length ?? 0) < 8
                  ? 'Use ao menos 8 caracteres.'
                  : null,
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              controller: _confirmation,
              label: 'Confirme a senha',
              icon: Icons.lock_reset,
              obscureText: true,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              validator: (String? value) =>
                  value != _password.text ? 'As senhas não coincidem.' : null,
            ),
            const SizedBox(height: AppSpacing.lg),
            AppButton(
              label: 'Cadastrar e entrar',
              loading: _loading,
              onPressed: _submit,
            ),
            const SizedBox(height: AppSpacing.sm),
            AppButton(
              label: 'Voltar ao login',
              variant: AppButtonVariant.text,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}
