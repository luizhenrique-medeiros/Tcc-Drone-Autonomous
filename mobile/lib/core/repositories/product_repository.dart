import '../models/product.dart';
import '../network/api_client.dart';

abstract interface class ProductRepository {
  Future<List<Product>> listProducts();
}

class DemoProductRepository implements ProductRepository {
  static const List<Product> products = <Product>[
    Product(
      id: 'demo-pizza-pepperoni',
      name: 'Pizza de Pepperoni',
      description:
          'Massa crocante, queijo derretido, molho artesanal e pepperoni.',
      category: 'Pizza',
      kind: ProductKind.pizza,
      price: 49.90,
      rating: 4.8,
      estimatedMinutes: 30,
    ),
    Product(
      id: 'demo-grocery',
      name: 'Cesta Essencial',
      description: 'Seleção acadêmica de itens de mercado para demonstração.',
      category: 'Mercado',
      kind: ProductKind.grocery,
      price: 38.50,
      rating: 4.7,
      estimatedMinutes: 28,
    ),
    Product(
      id: 'demo-burger',
      name: 'Burger Devcore',
      description: 'Hambúrguer, queijo, salada e acompanhamento crocante.',
      category: 'Lanches',
      kind: ProductKind.burger,
      price: 34.90,
      rating: 4.9,
      estimatedMinutes: 25,
    ),
    Product(
      id: 'demo-sushi',
      name: 'Combinado Sushi',
      description: 'Combinado demonstrativo com peças variadas.',
      category: 'Sushi',
      kind: ProductKind.sushi,
      price: 57.90,
      rating: 4.8,
      estimatedMinutes: 35,
    ),
    Product(
      id: 'demo-dessert',
      name: 'Brownie da Casa',
      description: 'Brownie com chocolate e finalização especial.',
      category: 'Doces',
      kind: ProductKind.dessert,
      price: 16.90,
      rating: 4.6,
      estimatedMinutes: 20,
    ),
    Product(
      id: 'demo-drink',
      name: 'Suco Natural',
      description: 'Bebida natural gelada em embalagem segura.',
      category: 'Bebidas',
      kind: ProductKind.drink,
      price: 11.90,
      rating: 4.7,
      estimatedMinutes: 18,
    ),
  ];

  @override
  Future<List<Product>> listProducts() async => products;
}

class ApiProductRepository implements ProductRepository {
  ApiProductRepository(this._client);

  final ApiClient _client;

  @override
  Future<List<Product>> listProducts() async {
    final Object? response = await _client.get('/api/v1/products');
    if (response is! List) {
      throw const ApiException('Catálogo inválido recebido da API.');
    }
    return response
        .map<Product>((Object? item) => Product.fromJson(expectJsonMap(item)))
        .toList(growable: false);
  }
}
