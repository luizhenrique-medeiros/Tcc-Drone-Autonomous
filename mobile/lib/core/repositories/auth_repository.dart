import '../network/api_client.dart';

class UserSession {
  const UserSession({required this.name, required this.email});

  final String name;
  final String email;
}

abstract interface class AuthRepository {
  Future<UserSession> login({required String email, required String password});

  Future<UserSession> register({
    required String name,
    required String email,
    required String password,
    String? phone,
  });

  void clearSession();
}

class DemoAuthRepository implements AuthRepository {
  @override
  void clearSession() {}

  @override
  Future<UserSession> login({
    required String email,
    required String password,
  }) async {
    await Future<void>.delayed(const Duration(milliseconds: 250));
    return UserSession(name: 'Cliente Demo', email: email);
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
  ApiAuthRepository(this._client);

  final ApiClient _client;

  @override
  void clearSession() => _client.accessToken = null;

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
    _client.accessToken = response['access_token']?.toString();
    final Map<String, Object?> user = expectJsonMap(response['user']);
    return UserSession(
      name: (user['name'] ?? 'Cliente').toString(),
      email: (user['email'] ?? email).toString(),
    );
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
}
