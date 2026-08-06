import 'dart:async';
import 'dart:convert';
import 'dart:io';

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({required this.baseUrl, HttpClient? httpClient})
    : _httpClient = httpClient ?? HttpClient();

  final String baseUrl;
  final HttpClient _httpClient;
  String? _accessToken;

  set accessToken(String? value) => _accessToken = value;
  String? get accessToken => _accessToken;

  Future<Object?> get(String path, {Map<String, String>? headers}) =>
      _request('GET', path, headers: headers);

  Future<Object?> post(
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) {
    return _request('POST', path, body: body, headers: headers);
  }

  Future<Object?> _request(
    String method,
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) async {
    try {
      final Uri uri = Uri.parse(baseUrl).resolve(path);
      final HttpClientRequest request = await _httpClient
          .openUrl(method, uri)
          .timeout(const Duration(seconds: 12));
      request.headers.set(HttpHeaders.acceptHeader, 'application/json');
      request.headers.set(HttpHeaders.contentTypeHeader, 'application/json');
      headers?.forEach(request.headers.set);
      if (_accessToken case final String token) {
        request.headers.set(HttpHeaders.authorizationHeader, 'Bearer $token');
      }
      if (body != null) request.write(jsonEncode(body));

      final HttpClientResponse response = await request.close().timeout(
        const Duration(seconds: 20),
      );
      final String responseText = await utf8.decoder.bind(response).join();
      Object? decoded;
      if (responseText.isNotEmpty) {
        try {
          decoded = jsonDecode(responseText);
        } on FormatException catch (error) {
          throw ApiException(
            'A API retornou JSON inválido: $error',
            statusCode: response.statusCode,
          );
        }
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw ApiException(
          _extractError(decoded),
          statusCode: response.statusCode,
        );
      }
      return decoded;
    } on ApiException {
      rethrow;
    } on SocketException catch (error) {
      throw ApiException('API indisponível: ${error.message}');
    } on HttpException catch (error) {
      throw ApiException('Falha HTTP: ${error.message}');
    } on TimeoutException {
      throw const ApiException('A comunicação com a API expirou.');
    }
  }

  String _extractError(Object? decoded) {
    if (decoded is Map<String, Object?>) {
      return (decoded['detail'] ?? decoded['message'] ?? 'Falha na API')
          .toString();
    }
    if (decoded is Map) {
      return (decoded['detail'] ?? decoded['message'] ?? 'Falha na API')
          .toString();
    }
    return 'Não foi possível concluir a comunicação com a API.';
  }

  void close() => _httpClient.close(force: true);
}

Map<String, Object?> expectJsonMap(Object? value) {
  if (value is Map<String, Object?>) return value;
  if (value is Map) {
    return value.map<String, Object?>((Object? key, Object? item) {
      return MapEntry<String, Object?>(key.toString(), item);
    });
  }
  throw const ApiException('Resposta inválida recebida da API.');
}
