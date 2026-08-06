enum ProductKind { pizza, grocery, burger, sushi, dessert, drink }

class Product {
  const Product({
    required this.id,
    required this.name,
    required this.description,
    required this.category,
    required this.kind,
    required this.price,
    required this.rating,
    required this.estimatedMinutes,
    this.available = true,
  });

  final String id;
  final String name;
  final String description;
  final String category;
  final ProductKind kind;
  final double price;
  final double rating;
  final int estimatedMinutes;
  final bool available;

  factory Product.fromJson(Map<String, Object?> json) {
    final String name = (json['name'] ?? json['title'] ?? 'Produto').toString();
    return Product(
      id: (json['id'] ?? '').toString(),
      name: name,
      description: (json['description'] ?? 'Produto acadêmico de demonstração')
          .toString(),
      category: (json['category'] ?? 'Destaques').toString(),
      kind: _kindFrom(name, json['category']?.toString()),
      price: _toDouble(json['price'] ?? json['unit_price']),
      rating: _toDouble(json['rating'], fallback: 4.8),
      estimatedMinutes: _toInt(json['estimated_minutes'], fallback: 30),
      available: json['available'] is bool ? json['available']! as bool : true,
    );
  }

  static double _toDouble(Object? value, {double fallback = 0}) {
    if (value is num) return value.toDouble();
    return double.tryParse(value?.toString() ?? '') ?? fallback;
  }

  static int _toInt(Object? value, {required int fallback}) {
    if (value is num) return value.toInt();
    return int.tryParse(value?.toString() ?? '') ?? fallback;
  }

  static ProductKind _kindFrom(String name, String? category) {
    final String value = '$name ${category ?? ''}'.toLowerCase();
    if (value.contains('sushi')) return ProductKind.sushi;
    if (value.contains('burger') || value.contains('lanche')) {
      return ProductKind.burger;
    }
    if (value.contains('mercado') || value.contains('grocer')) {
      return ProductKind.grocery;
    }
    if (value.contains('doce') || value.contains('brownie')) {
      return ProductKind.dessert;
    }
    if (value.contains('bebida') || value.contains('suco')) {
      return ProductKind.drink;
    }
    return ProductKind.pizza;
  }
}
