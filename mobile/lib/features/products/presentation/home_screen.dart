import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../../../app/app_controller.dart';
import '../../../app/app_scope.dart';
import '../../../core/config/app_config.dart';
import '../../../core/models/product.dart';
import '../../../design_system/components/app_banner.dart';
import '../../../design_system/components/app_button.dart';
import '../../../design_system/components/app_text_field.dart';
import '../../../design_system/components/brand_mark.dart';
import '../../../design_system/components/product_card.dart';
import '../../../design_system/components/section_header.dart';
import '../../../design_system/components/surface_card.dart';
import '../../../design_system/tokens/app_breakpoints.dart';
import '../../../design_system/tokens/app_colors.dart';
import '../../../design_system/tokens/app_icon_sizes.dart';
import '../../../design_system/tokens/app_radii.dart';
import '../../../design_system/tokens/app_spacing.dart';
import '../../../design_system/tokens/app_typography.dart';
import '../../auth/presentation/login_screen.dart';
import '../../cart/presentation/cart_screen.dart';
import '../../diagnostics/presentation/runtime_diagnostics_screen.dart';
import '../../orders/presentation/orders_screen.dart';
import 'product_detail_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _searchController = TextEditingController();
  int _selectedIndex = 0;
  String _query = '';

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppController controller = AppScope.of(context);
    final List<Widget> pages = <Widget>[
      _HomeTab(controller: controller),
      _SearchTab(
        controller: controller,
        searchController: _searchController,
        query: _query,
        onChanged: (String value) => setState(() => _query = value),
      ),
      OrdersScreen(onBrowseProducts: () => setState(() => _selectedIndex = 0)),
      _ProfileTab(controller: controller),
    ];
    return LayoutBuilder(
      builder: (BuildContext context, BoxConstraints constraints) {
        final bool desktop = constraints.maxWidth >= AppBreakpoints.expanded;
        final Widget content = IndexedStack(
          index: _selectedIndex,
          children: pages,
        );
        return Scaffold(
          appBar: AppBar(
            title: switch (_selectedIndex) {
              0 => const BrandMark(compact: true),
              1 => const Text('Buscar produtos'),
              2 => const Text('Meus pedidos'),
              _ => const Text('Minha conta'),
            },
            actions: <Widget>[
              _CartAction(count: controller.cartCount),
              const SizedBox(width: AppSpacing.xs),
            ],
          ),
          body: desktop
              ? Row(
                  children: <Widget>[
                    NavigationRail(
                      extended: constraints.maxWidth >= 1120,
                      selectedIndex: _selectedIndex,
                      onDestinationSelected: (int value) {
                        setState(() => _selectedIndex = value);
                      },
                      destinations: const <NavigationRailDestination>[
                        NavigationRailDestination(
                          icon: Icon(Icons.home_outlined),
                          selectedIcon: Icon(Icons.home_rounded),
                          label: Text('Início'),
                        ),
                        NavigationRailDestination(
                          icon: Icon(Icons.search),
                          label: Text('Buscar'),
                        ),
                        NavigationRailDestination(
                          icon: Icon(Icons.receipt_long_outlined),
                          selectedIcon: Icon(Icons.receipt_long),
                          label: Text('Pedidos'),
                        ),
                        NavigationRailDestination(
                          icon: Icon(Icons.settings_outlined),
                          selectedIcon: Icon(Icons.settings),
                          label: Text('Conta'),
                        ),
                      ],
                    ),
                    const VerticalDivider(width: 1),
                    Expanded(child: content),
                  ],
                )
              : content,
          bottomNavigationBar: desktop
              ? null
              : NavigationBar(
                  selectedIndex: _selectedIndex,
                  onDestinationSelected: (int value) {
                    setState(() => _selectedIndex = value);
                  },
                  destinations: const <NavigationDestination>[
                    NavigationDestination(
                      icon: Icon(Icons.home_outlined),
                      selectedIcon: Icon(Icons.home_rounded),
                      label: 'Início',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.search),
                      label: 'Buscar',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.receipt_long_outlined),
                      selectedIcon: Icon(Icons.receipt_long),
                      label: 'Pedidos',
                    ),
                    NavigationDestination(
                      icon: Icon(Icons.settings_outlined),
                      selectedIcon: Icon(Icons.settings),
                      label: 'Conta',
                    ),
                  ],
                ),
        );
      },
    );
  }
}

class _CartAction extends StatelessWidget {
  const _CartAction({required this.count});

  final int count;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'Carrinho com $count itens',
      child: Stack(
        clipBehavior: Clip.none,
        children: <Widget>[
          IconButton(
            onPressed: () async {
              await Navigator.of(context).push<void>(
                MaterialPageRoute<void>(builder: (_) => const CartScreen()),
              );
            },
            icon: const Icon(Icons.shopping_cart_outlined),
          ),
          if (count > 0)
            Positioned(
              right: 2,
              top: 2,
              child: Container(
                constraints: const BoxConstraints(minWidth: 18, minHeight: 18),
                padding: const EdgeInsets.symmetric(horizontal: 4),
                decoration: const BoxDecoration(
                  color: AppColors.accentOrange,
                  shape: BoxShape.circle,
                ),
                alignment: Alignment.center,
                child: Text(
                  '$count',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.surface,
                    fontSize: 10,
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _HomeTab extends StatelessWidget {
  const _HomeTab({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppBreakpoints.contentMaxWidth,
        ),
        child: RefreshIndicator(
          onRefresh: controller.loadProducts,
          child: CustomScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            slivers: <Widget>[
              SliverPadding(
                padding: const EdgeInsets.fromLTRB(
                  AppSpacing.screen,
                  AppSpacing.md,
                  AppSpacing.screen,
                  AppSpacing.lg,
                ),
                sliver: SliverList.list(
                  children: <Widget>[
                    const _PromotionHero(),
                    const SizedBox(height: AppSpacing.xl),
                    const SectionHeader(
                      title: 'Talvez você se interesse',
                      subtitle: 'Categorias e produtos disponíveis',
                    ),
                  ],
                ),
              ),
              _ProductsSliver(
                controller: controller,
                products: controller.products,
              ),
              const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),
            ],
          ),
        ),
      ),
    );
  }
}

class _PromotionHero extends StatelessWidget {
  const _PromotionHero();

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minHeight: 220),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: const BoxDecoration(
        borderRadius: AppRadii.large,
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: <Color>[
            AppColors.brandBlueDark,
            AppColors.brandBlue,
            AppColors.info,
          ],
        ),
      ),
      child: Stack(
        children: <Widget>[
          Positioned(
            right: -10,
            top: 12,
            child: Icon(
              Icons.public,
              color: AppColors.surface.withValues(alpha: 0.18),
              size: 150,
            ),
          ),
          Positioned(
            right: 20,
            top: 70,
            child: Transform.rotate(
              angle: -0.1,
              child: const Icon(
                Icons.flight,
                color: AppColors.surface,
                size: 76,
              ),
            ),
          ),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 225),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: AppSpacing.xs,
                  ),
                  decoration: const BoxDecoration(
                    color: AppColors.accentOrange,
                    borderRadius: AppRadii.pill,
                  ),
                  child: Text(
                    '20% OFF',
                    style: AppTypography.label.copyWith(
                      color: AppColors.surface,
                    ),
                  ),
                ),
                const SizedBox(height: AppSpacing.md),
                Text(
                  'PROMOÇÃO\nESPECIAL',
                  style: AppTypography.headline.copyWith(
                    color: AppColors.surface,
                    fontSize: 28,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Desconto aplicado aos produtos do carrinho.',
                  style: AppTypography.caption.copyWith(
                    color: AppColors.surface,
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

class _ProductsSliver extends StatelessWidget {
  const _ProductsSliver({required this.controller, required this.products});

  final AppController controller;
  final List<Product> products;

  @override
  Widget build(BuildContext context) {
    if (controller.isLoadingProducts) {
      return const SliverFillRemaining(
        hasScrollBody: false,
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (controller.productsError != null) {
      return SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.screen),
          child: Column(
            children: <Widget>[
              AppBanner(
                title: 'Catálogo indisponível',
                message: controller.productsError!,
                tone: AppBannerTone.danger,
              ),
              const SizedBox(height: AppSpacing.md),
              AppButton(
                label: 'Tentar novamente',
                onPressed: controller.loadProducts,
              ),
            ],
          ),
        ),
      );
    }
    if (products.isEmpty) {
      return const SliverToBoxAdapter(
        child: Padding(
          padding: EdgeInsets.all(AppSpacing.screen),
          child: AppBanner(
            title: 'Nenhum produto disponível',
            message: 'Puxe a tela para atualizar o catálogo.',
            tone: AppBannerTone.warning,
          ),
        ),
      );
    }
    return SliverLayoutBuilder(
      builder: (BuildContext context, constraints) {
        final int columns = AppBreakpoints.productColumns(
          constraints.crossAxisExtent,
        );
        return SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: AppSpacing.screen),
          sliver: SliverGrid.builder(
            itemCount: products.length,
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: columns,
              crossAxisSpacing: AppSpacing.sm,
              mainAxisSpacing: AppSpacing.sm,
              mainAxisExtent: columns == 1 ? 300 : 258,
            ),
            itemBuilder: (BuildContext context, int index) {
              final Product product = products[index];
              return ProductCard(
                product: product,
                onTap: () async {
                  await Navigator.of(context).push<void>(
                    MaterialPageRoute<void>(
                      builder: (_) => ProductDetailScreen(product: product),
                    ),
                  );
                },
                onAdd: () {
                  controller.addProduct(product);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text('${product.name} adicionado ao carrinho.'),
                      duration: const Duration(seconds: 1),
                    ),
                  );
                },
              );
            },
          ),
        );
      },
    );
  }
}

class _SearchTab extends StatelessWidget {
  const _SearchTab({
    required this.controller,
    required this.searchController,
    required this.query,
    required this.onChanged,
  });

  final AppController controller;
  final TextEditingController searchController;
  final String query;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final List<Product> results = controller.products
        .where((Product product) {
          final String value = '${product.name} ${product.category}'
              .toLowerCase();
          return value.contains(query.trim().toLowerCase());
        })
        .toList(growable: false);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(
          maxWidth: AppBreakpoints.contentMaxWidth,
        ),
        child: CustomScrollView(
          slivers: <Widget>[
            SliverPadding(
              padding: const EdgeInsets.all(AppSpacing.screen),
              sliver: SliverToBoxAdapter(
                child: AppTextField(
                  controller: searchController,
                  label: 'Buscar no catálogo',
                  hint: 'Pizza, sushi, bebidas…',
                  icon: Icons.search,
                  onChanged: onChanged,
                ),
              ),
            ),
            _ProductsSliver(controller: controller, products: results),
            const SliverToBoxAdapter(child: SizedBox(height: AppSpacing.xl)),
          ],
        ),
      ),
    );
  }
}

class _ProfileTab extends StatelessWidget {
  const _ProfileTab({required this.controller});

  final AppController controller;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760),
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.screen),
          children: <Widget>[
            SurfaceCard(
              child: Row(
                children: <Widget>[
                  const CircleAvatar(
                    radius: AppIconSizes.large,
                    backgroundColor: AppColors.brandBlueSoft,
                    foregroundColor: AppColors.brandBlue,
                    child: Icon(Icons.person),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: <Widget>[
                        Text(
                          controller.session?.name ?? 'Cliente',
                          style: AppTypography.bodyStrong,
                        ),
                        Text(
                          controller.session?.email ?? '',
                          style: AppTypography.caption,
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xl),
            if (kDebugMode && AppConfig.diagnosticsEnabled) ...<Widget>[
              AppButton(
                label: 'Diagnóstico de desenvolvimento',
                variant: AppButtonVariant.secondary,
                icon: Icons.bug_report_outlined,
                onPressed: () async {
                  await Navigator.of(context).push<void>(
                    MaterialPageRoute<void>(
                      builder: (_) => const RuntimeDiagnosticsScreen(),
                    ),
                  );
                },
              ),
              const SizedBox(height: AppSpacing.sm),
            ],
            AppButton(
              label: 'Sair',
              variant: AppButtonVariant.secondary,
              icon: Icons.logout,
              onPressed: () async {
                await controller.logout();
                if (!context.mounted) return;
                await Navigator.of(context).pushAndRemoveUntil<void>(
                  MaterialPageRoute<void>(builder: (_) => const LoginScreen()),
                  (Route<Object?> route) => false,
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
