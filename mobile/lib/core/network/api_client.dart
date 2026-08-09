import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  const ApiException(
    this.message, {
    this.statusCode,
    this.isConnectivityFailure = false,
    this.code,
    this.fields = const <String, Object?>{},
  });

  final String message;
  final int? statusCode;
  final bool isConnectivityFailure;
  final String? code;
  final Map<String, Object?> fields;

  @override
  String toString() => message;
}

/// Cliente HTTP compartilhado por Android e Web.
///
/// `package:http` escolhe a implementação da plataforma sem importar
/// `dart:io` nos bundles do navegador.
class ApiClient {
  ApiClient({required this.baseUrl, http.Client? httpClient})
    : _httpClient = httpClient ?? http.Client();

  final String baseUrl;
  final http.Client _httpClient;
  String? _accessToken;

  set accessToken(String? value) => _accessToken = value;
  String? get accessToken => _accessToken;

  Future<Object?> get(String path, {Map<String, String>? headers}) =>
      _request('GET', path, headers: headers);

  Future<Object?> post(
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) => _request('POST', path, body: body, headers: headers);

  Future<Object?> patch(
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) => _request('PATCH', path, body: body, headers: headers);

  Future<Object?> delete(
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) => _request('DELETE', path, body: body, headers: headers);

  Future<Object?> _request(
    String method,
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? headers,
  }) async {
    try {
      final Uri uri = Uri.parse(baseUrl).resolve(path);
      final http.Request request = http.Request(method, uri)
        ..headers.addAll(<String, String>{
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          ...?headers,
          if (_accessToken case final String token)
            'Authorization': 'Bearer $token',
        });
      if (body != null) request.body = jsonEncode(body);

      final http.StreamedResponse streamed = await _httpClient
          .send(request)
          .timeout(const Duration(seconds: 20));
      final http.Response response = await http.Response.fromStream(
        streamed,
      ).timeout(const Duration(seconds: 20));
      Object? decoded;
      if (response.body.isNotEmpty) {
        try {
          decoded = jsonDecode(response.body);
        } on FormatException catch (error) {
          throw ApiException(
            'A API retornou JSON inválido: $error',
            statusCode: response.statusCode,
          );
        }
      }
      if (response.statusCode < 200 || response.statusCode >= 300) {
        final _ApiErrorDetails details = _extractError(decoded);
        throw ApiException(
          details.message,
          statusCode: response.statusCode,
          code: details.code,
          fields: details.fields,
        );
      }
      return decoded;
    } on ApiException {
      rethrow;
    } on http.ClientException catch (error) {
      throw ApiException(
        'API indisponível: ${error.message}',
        isConnectivityFailure: true,
      );
    } on TimeoutException {
      throw const ApiException(
        'A comunicação com a API expirou.',
        isConnectivityFailure: true,
      );
    } on FormatException catch (error) {
      throw ApiException('URL ou resposta inválida: ${error.message}');
    }
  }

  _ApiErrorDetails _extractError(Object? decoded) {
    if (decoded is Map<String, Object?>) {
      return _ApiErrorDetails.fromMap(decoded);
    }
    if (decoded is Map) {
      return _ApiErrorDetails.fromMap(
        decoded.map<String, Object?>((Object? key, Object? value) {
          return MapEntry<String, Object?>(key.toString(), value);
        }),
      );
    }
    return const _ApiErrorDetails(
      message: 'Não foi possível concluir a comunicação com a API.',
    );
  }

  void close() => _httpClient.close();
}

class _ApiErrorDetails {
  const _ApiErrorDetails({
    required this.message,
    this.code,
    this.fields = const <String, Object?>{},
  });

  factory _ApiErrorDetails.fromMap(Map<String, Object?> json) {
    final Object? rawFields = json['fields'];
    final Map<String, Object?> fields = rawFields is Map
        ? rawFields.map<String, Object?>((Object? key, Object? value) {
            return MapEntry<String, Object?>(key.toString(), value);
          })
        : const <String, Object?>{};
    return _ApiErrorDetails(
      message: (json['detail'] ?? json['message'] ?? 'Falha na API').toString(),
      code: json['code']?.toString(),
      fields: fields,
    );
  }

  final String message;
  final String? code;
  final Map<String, Object?> fields;
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
