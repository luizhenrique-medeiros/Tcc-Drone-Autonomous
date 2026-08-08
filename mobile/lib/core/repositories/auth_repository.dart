import '../network/api_client.dart';
import '../security/session_token_store.dart';

class UserSession {
  const UserSession({required this.name, required this.email});

  final String name;
  final String email;
}

abstract interface class AuthRepository {
  Future<UserSession?> restoreSession();

  Future<UserSession> login({required String email, required String password});

  Future<UserSession> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  });

  Future<void> clearSession();
}

class DemoAuthRepository implements AuthRepository {
  @override
  Future<void> clearSession() async {}

  @override
  Future<UserSession?> restoreSession() async => null;

  @override
  Future<UserSession> login({
    required String email,
    required String password,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    return UserSession(name: 'Cliente', email: email);
  }

  @override
  Future<UserSession> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    return UserSession(name: name, email: email);
  }
}

class ApiAuthRepository implements AuthRepository {
  ApiAuthRepository(this._client, this._tokenStore);

  final ApiClient _client;
  final SessionTokenStore _tokenStore;

  @override
  Future<void> clearSession() async {
    _client.accessToken = null;
    await _tokenStore.clear();
  }

  @override
  Future<UserSession?> restoreSession() async {
    final String? token;
    try {
      token = await _tokenStore.read();
    } on Object {
      _client.accessToken = null;
      return null;
    }
    if (token == null || token.isEmpty) return null;
    _client.accessToken = token;
    try {
      return _sessionFromUser(
        expectJsonMap(await _client.get('/api/v1/auth/me')),
      );
    } on ApiException catch (error) {
      if (error.statusCode == 401 || error.statusCode == 403) {
        await clearSession();
      }
      return null;
    }
  }

  @override
  Future<UserSession> login({
    required String email,
    required String password,
  }) async {
    final Map<String, Object?> response = expectJsonMap(
      await _client.post(
        '/api/v1/auth/login',
        body: <String, Object?>{'email': email, 'password': password},
      ),
    );
    final String token = response['access_token']?.toString() ?? '';
    if (token.isEmpty) {
      throw const ApiException('A API não retornou uma sessão válida.');
    }
    final UserSession session = _sessionFromUser(
      expectJsonMap(response['user']),
      email: email,
    );
    _client.accessToken = token;
    try {
      await _tokenStore.write(token);
    } on Object {
      _client.accessToken = null;
      throw const ApiException(
        'Não foi possível armazenar a sessão com segurança neste navegador.',
      );
    }
    return session;
  }

  @override
  Future<UserSession> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  }) async {
    await _client.post(
      '/api/v1/auth/register',
      body: <String, Object?>{
        'name': name,
        'email': email,
        'password': password,
        if (phone != null && phone.isNotEmpty) 'phone': phone,
      },
    );
    return login(email: email, password: password);
  }

  UserSession _sessionFromUser(Map<String, Object?> user, {String email = ''}) {
    final String name = user['name']?.toString().trim() ?? '';
    final String resolvedEmail = (user['email'] ?? email).toString().trim();
    if (name.isEmpty || resolvedEmail.isEmpty) {
      throw const ApiException('A API não retornou um usuário válido.');
    }
    return UserSession(name: name, email: resolvedEmail);
  }
}
