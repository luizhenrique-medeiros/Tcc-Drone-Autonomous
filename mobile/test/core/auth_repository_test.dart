import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/auth_repository.dart';
import 'package:drone_delivery_mobile/core/security/session_token_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('restaura sessão persistida e valida o usuário na API', () async {
    final MemorySessionTokenStore tokenStore = MemorySessionTokenStore();
    await tokenStore.write('token-persistido');
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((http.Request request) async {
        expect(request.method, 'GET');
        expect(request.url.path, '/api/v1/auth/me');
        expect(request.headers['authorization'], 'Bearer token-persistido');
        return http.Response(
          '{"name":"Luiz","email":"luiz@example.test"}',
          200,
          headers: <String, String>{'content-type': 'application/json'},
        );
      }),
    );
    final ApiAuthRepository repository = ApiAuthRepository(client, tokenStore);

    final UserSession? session = await repository.restoreSession();

    expect(session?.name, 'Luiz');
    expect(session?.email, 'luiz@example.test');
    expect(client.accessToken, 'token-persistido');
    client.close();
  });

  test('remove a sessão persistida quando a API rejeita o token', () async {
    final MemorySessionTokenStore tokenStore = MemorySessionTokenStore();
    await tokenStore.write('token-expirado');
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient(
        (_) async => http.Response(
          '{"detail":"Não autorizado"}',
          401,
          headers: <String, String>{'content-type': 'application/json'},
        ),
      ),
    );
    final ApiAuthRepository repository = ApiAuthRepository(client, tokenStore);

    expect(await repository.restoreSession(), isNull);
    expect(await tokenStore.read(), isNull);
    expect(client.accessToken, isNull);
    client.close();
  });

  test('não persiste token quando a API retorna usuário inválido', () async {
    final MemorySessionTokenStore tokenStore = MemorySessionTokenStore();
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient(
        (_) async => http.Response(
          '{"access_token":"token-sem-usuario","user":{}}',
          200,
          headers: <String, String>{'content-type': 'application/json'},
        ),
      ),
    );
    final ApiAuthRepository repository = ApiAuthRepository(client, tokenStore);

    await expectLater(
      repository.login(email: 'luiz@example.test', password: 'segredo'),
      throwsA(isA<ApiException>()),
    );
    expect(client.accessToken, isNull);
    expect(await tokenStore.read(), isNull);
    client.close();
  });
}
