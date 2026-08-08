import 'package:flutter/material.dart';

import '../../../app/app_scope.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../products/presentation/home_screen.dart';
import 'auth_frame.dart';
import 'register_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final GlobalKey<FormState> _formKey = GlobalKey<FormState>();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _loading = false;
  String? _error;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    final String? error = await AppScope.of(context).login(
      email: _emailController.text.trim(),
      password: _passwordController.text,
    );
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = error;
    });
    if (error == null) {
      await Navigator.of(context).pushReplacement<void, void>(
        MaterialPageRoute<void>(builder: (_) => const HomeScreen()),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final String? startupError = AppScope.of(context).initializationError;
    return AuthFrame(
      child: Form(
        key: _formKey,
        child: Column(
          children: <Widget>[
            const Text('Bem-vindo', style: AppTypography.headline),
            const SizedBox(height: AppSpacing.xs),
            const Text(
              'Entre para escolher produtos e o ponto da entrega.',
              style: AppTypography.body,
              textAlign: TextAlign.center,
            ),
            if (_error != null || startupError != null) ...<Widget>[
              const SizedBox(height: AppSpacing.md),
              AppBanner(
                title: 'Não foi possível entrar',
                message: _error ?? startupError!,
                tone: AppBannerTone.danger,
              ),
            ],
            const SizedBox(height: AppSpacing.lg),
            AppTextField(
              key: const Key('login-email'),
              controller: _emailController,
              label: 'E-mail',
              hint: 'Digite seu e-mail',
              icon: Icons.mail_outline,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              validator: (String? value) {
                if (value == null || !value.contains('@')) {
                  return 'Informe um e-mail válido.';
                }
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.md),
            AppTextField(
              key: const Key('login-password'),
              controller: _passwordController,
              label: 'Senha',
              hint: 'Digite sua senha',
              icon: Icons.lock_outline,
              obscureText: true,
              textInputAction: TextInputAction.done,
              onSubmitted: (_) => _submit(),
              validator: (String? value) {
                if (value == null || value.length < 6) {
                  return 'A senha deve ter ao menos 6 caracteres.';
                }
                return null;
              },
            ),
            const SizedBox(height: AppSpacing.lg),
            AppButton(
              key: const Key('login-submit'),
              label: 'Entrar',
              loading: _loading,
              onPressed: _submit,
            ),
            const SizedBox(height: AppSpacing.md),
            AppButton(
              label: 'Criar uma conta',
              variant: AppButtonVariant.text,
              onPressed: () async {
                await Navigator.of(context).push<void>(
                  MaterialPageRoute<void>(
                    builder: (_) => const RegisterScreen(),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
