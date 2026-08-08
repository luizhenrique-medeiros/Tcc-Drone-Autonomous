import 'package:drone_delivery_mobile/core/models/product.dart';
import 'package:drone_delivery_mobile/design_system/components/product_artwork.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('usa Image.network para URL HTTP real', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ProductArtwork(
          kind: ProductKind.burger,
          imageUrl: 'https://cdn.example.test/produto.webp',
          semanticLabel: 'X-Burger',
        ),
      ),
    );

    final Image image = tester.widget<Image>(find.byType(Image));
    expect(image.image, isA<NetworkImage>());
    expect(
      (image.image as NetworkImage).url,
      'https://cdn.example.test/produto.webp',
    );
  });

  testWidgets('usa artwork local quando URL está ausente ou inválida', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ProductArtwork(
          kind: ProductKind.pizza,
          imageUrl: 'arquivo-local.png',
        ),
      ),
    );

    expect(find.byType(Image), findsNothing);
    expect(find.byIcon(Icons.local_pizza_rounded), findsOneWidget);
  });

  testWidgets('erro de rede preserva artwork como fallback', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: ProductArtwork(
          kind: ProductKind.sushi,
          imageUrl: 'https://invalid.example.test/sushi.webp',
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.set_meal_rounded), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
