enum ProductKind { pizza, grocery, burger, sushi, dessert, drink }

class Product {
  const Product({
    required this.id,
    required this.name,
    required this.description,
    required this.category,
    required this.kind,
    required this.price,
    this.imageUrl,
    this.rating,
    this.estimatedMinutes,
    this.available = true,
  });

  final String id;
  final String name;
  final String description;
  final String category;
  final ProductKind kind;
  final double price;
  final String? imageUrl;
  final double? rating;
  final int? estimatedMinutes;
  final bool available;

  factory Product.fromJson(Map<String, Object?> json) {
    final String id = json['id']?.toString().trim() ?? '';
    final String name =
        (json['name'] ?? json['title'])?.toString().trim() ?? '';
    if (id.isEmpty || name.isEmpty) {
      throw const FormatException('Produto sem id ou nome.');
    }
    final double price = _requiredDouble(json['price'] ?? json['unit_price']);
    final double? rating = _toNullableDouble(json['rating']);
    final int? estimatedMinutes = _toNullableInt(json['estimated_minutes']);
    if (!price.isFinite || price < 0) {
      throw const FormatException('Produto com preço inválido.');
    }
    if (rating != null && (!rating.isFinite || rating < 0 || rating > 5)) {
      throw const FormatException('Produto com avaliação inválida.');
    }
    if (estimatedMinutes != null && estimatedMinutes < 0) {
      throw const FormatException('Produto com prazo estimado inválido.');
    }
    return Product(
      id: id,
      name: name,
      description: json['description']?.toString() ?? '',
      category: json['category']?.toString() ?? '',
      kind: inferKind(name, json['category']?.toString()),
      price: price,
      imageUrl: _toNullableText(json['image_url']),
      rating: rating,
      estimatedMinutes: estimatedMinutes,
      available: json['available'] is bool ? json['available']! as bool : false,
    );
  }

  static double _requiredDouble(Object? value) {
    if (value is num) return value.toDouble();
    final double? parsed = double.tryParse(value?.toString() ?? '');
    if (parsed == null)
      throw const FormatException('Produto sem preço válido.');
    return parsed;
  }

  static double? _toNullableDouble(Object? value) {
    if (value == null) return null;
    if (value is num) return value.toDouble();
    return double.tryParse(value.toString());
  }

  static int? _toNullableInt(Object? value) {
    if (value == null) return null;
    if (value is num) return value.toInt();
    return int.tryParse(value.toString());
  }

  static String? _toNullableText(Object? value) {
    final String text = value?.toString().trim() ?? '';
    return text.isEmpty ? null : text;
  }

  static ProductKind inferKind(String name, [String? category]) {
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
