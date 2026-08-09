import 'dart:convert';

import 'package:drone_delivery_mobile/core/models/delivery_point.dart';
import 'package:drone_delivery_mobile/core/models/saved_location.dart';
import 'package:drone_delivery_mobile/core/network/api_client.dart';
import 'package:drone_delivery_mobile/core/repositories/saved_location_repository.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test(
    'API lista somente o contrato recebido e aceita endereço nulo',
    () async {
      final ApiClient client = ApiClient(
        baseUrl: 'https://api.example.test',
        httpClient: MockClient((http.Request request) async {
          expect(request.method, 'GET');
          expect(request.url.path, '/api/v1/saved-locations');
          expect(request.headers['authorization'], 'Bearer token-cliente');
          return http.Response(
            jsonEncode(<Map<String, Object?>>[
              _locationJson(addressReference: null),
            ]),
            200,
          );
        }),
      )..accessToken = 'token-cliente';
      addTearDown(client.close);

      final List<SavedLocation> locations = await ApiSavedLocationRepository(
        client,
      ).listSavedLocations();

      expect(locations, hasLength(1));
      expect(locations.single.name, 'Casa');
      expect(locations.single.addressReference, isNull);
      expect(locations.single.coordinate.latitude, -23.1175);
    },
  );

  test('API usa POST, PATCH e DELETE sem enviar user_id', () async {
    final List<String> methods = <String>[];
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient((http.Request request) async {
        methods.add(request.method);
        final Map<String, Object?> body = request.body.isEmpty
            ? <String, Object?>{}
            : (jsonDecode(request.body) as Map).map<String, Object?>(
                (Object? key, Object? value) =>
                    MapEntry<String, Object?>(key.toString(), value),
              );
        expect(body.containsKey('user_id'), isFalse);
        if (request.method == 'POST') {
          expect(request.headers['idempotency-key'], isNotEmpty);
          return http.Response(jsonEncode(_locationJson()), 201);
        }
        if (request.method == 'PATCH') {
          expect(request.url.path, '/api/v1/saved-locations/local-1');
          return http.Response(
            jsonEncode(_locationJson(name: 'Casa nova')),
            200,
          );
        }
        expect(request.method, 'DELETE');
        return http.Response('', 204);
      }),
    );
    addTearDown(client.close);
    final ApiSavedLocationRepository repository = ApiSavedLocationRepository(
      client,
    );
    final SavedLocationDraft draft = _confirmedDraft(
      'Casa',
      const GeoCoordinate(latitude: -23.1175, longitude: -46.5502),
    );

    await repository.createSavedLocation(draft);
    final SavedLocation updated = await repository.updateSavedLocation(
      'local-1',
      _confirmedDraft(
        'Casa nova',
        const GeoCoordinate(latitude: -23.1176, longitude: -46.5503),
      ),
    );
    await repository.deleteSavedLocation('local-1');

    expect(updated.name, 'Casa nova');
    expect(methods, <String>['POST', 'PATCH', 'DELETE']);
  });

  test('ApiException preserva código do limite', () async {
    final ApiClient client = ApiClient(
      baseUrl: 'https://api.example.test',
      httpClient: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object?>{
            'code': 'SAVED_LOCATION_LIMIT_REACHED',
            'detail': 'Você pode salvar no máximo 3 localizações.',
            'fields': <String, Object?>{},
          }),
          409,
        ),
      ),
    );
    addTearDown(client.close);

    await expectLater(
      ApiSavedLocationRepository(client).createSavedLocation(
        _confirmedDraft(
          'Casa',
          const GeoCoordinate(latitude: -23, longitude: -46),
        ),
      ),
      throwsA(
        isA<ApiException>()
            .having((ApiException error) => error.statusCode, 'status', 409)
            .having(
              (ApiException error) => error.code,
              'code',
              'SAVED_LOCATION_LIMIT_REACHED',
            ),
      ),
    );
  });

  test('demo começa vazio, permite CRUD e impede a quarta', () async {
    final DemoSavedLocationRepository repository =
        DemoSavedLocationRepository();
    expect(await repository.listSavedLocations(), isEmpty);

    for (int index = 1; index <= 3; index++) {
      await repository.createSavedLocation(
        _confirmedDraft(
          'Local $index',
          GeoCoordinate(latitude: -23 + index / 1000, longitude: -46),
        ),
      );
    }
    await expectLater(
      repository.createSavedLocation(
        _confirmedDraft(
          'Quarta',
          const GeoCoordinate(latitude: -23, longitude: -46),
        ),
      ),
      throwsA(
        isA<ApiException>().having(
          (ApiException error) => error.code,
          'code',
          'SAVED_LOCATION_LIMIT_REACHED',
        ),
      ),
    );

    final SavedLocation first = (await repository.listSavedLocations()).first;
    await repository.updateSavedLocation(
      first.id,
      _confirmedDraft(
        'Atualizada',
        const GeoCoordinate(latitude: -23.2, longitude: -46.2),
      ),
    );
    expect((await repository.listSavedLocations()).first.name, 'Atualizada');
    await repository.deleteSavedLocation(first.id);
    expect(await repository.listSavedLocations(), hasLength(2));
  });
}

Map<String, Object?> _locationJson({
  String name = 'Casa',
  String? addressReference = 'Rua de referência',
}) {
  return <String, Object?>{
    'id': 'local-1',
    'user_id': 'cliente-1',
    'name': name,
    'final_latitude': '-23.1175000',
    'final_longitude': '-46.5502000',
    'map_provider': 'maptiler',
    'map_type': 'hybrid',
    'region_confirmed': true,
    'exact_point_selected': true,
    'user_confirmed': true,
    'user_confirmed_safe_area': true,
    'address_reference': addressReference,
    'instructions': null,
    'accuracy_meters': null,
    'created_at': '2026-08-09T12:00:00Z',
    'updated_at': '2026-08-09T12:00:00Z',
  };
}

SavedLocationDraft _confirmedDraft(String name, GeoCoordinate coordinate) {
  return SavedLocationDraft(
    name: name,
    coordinate: coordinate,
    mapProvider: 'maptiler',
    mapType: 'hybrid',
    regionConfirmed: true,
    exactPointSelected: true,
    userConfirmed: true,
    userConfirmedSafeArea: true,
  );
}
