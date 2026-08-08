import 'package:drone_delivery_mobile/core/models/product.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Map<String, Object?> validProduct() => <String, Object?>{
    'id': 'product-1',
    'name': 'Produto',
    'description': 'Descrição',
    'category': 'Categoria',
    'price': 10.5,
    'available': true,
  };

  test('API não inventa avaliação nem prazo ausentes', () {
    final Product product = Product.fromJson(validProduct());

    expect(product.rating, isNull);
    expect(product.estimatedMinutes, isNull);
  });

  test('rejeita preço, avaliação e prazo fora da faixa', () {
    expect(
      () => Product.fromJson(<String, Object?>{...validProduct(), 'price': -1}),
      throwsFormatException,
    );
    expect(
      () => Product.fromJson(<String, Object?>{...validProduct(), 'rating': 6}),
      throwsFormatException,
    );
    expect(
      () => Product.fromJson(<String, Object?>{
        ...validProduct(),
        'estimated_minutes': -5,
      }),
      throwsFormatException,
    );
  });
}
