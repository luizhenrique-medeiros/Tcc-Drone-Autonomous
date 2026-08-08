import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';

import '../maps/map_provider.dart';
import '../models/delivery_point.dart';

class DiagnosticProbe {
  const DiagnosticProbe({required this.ok, required this.message});

  const DiagnosticProbe.notTested() : ok = null, message = 'Não testado';

  final bool? ok;
  final String message;
}

class RuntimeDiagnosticsService {
  const RuntimeDiagnosticsService({required this.apiBaseUrl});

  final String apiBaseUrl;

  Future<DiagnosticProbe> probeBackend() async {
    final http.Client client = http.Client();
    try {
      final http.Response response = await client
          .get(Uri.parse(apiBaseUrl).resolve('/health'))
          .timeout(const Duration(seconds: 8));
      if (response.statusCode == 200) {
        return const DiagnosticProbe(ok: true, message: 'HTTP 200 em /health');
      }
      return DiagnosticProbe(
        ok: false,
        message: 'HTTP ${response.statusCode} em /health',
      );
    } on TimeoutException {
      return const DiagnosticProbe(ok: false, message: 'Timeout em /health');
    } on Object catch (error) {
      return DiagnosticProbe(
        ok: false,
        message: 'Falha de conexão (${error.runtimeType})',
      );
    } finally {
      client.close();
    }
  }

  Future<DiagnosticProbe> probeWebSocket() async {
    WebSocketChannel? socket;
    try {
      final Uri apiUri = Uri.parse(apiBaseUrl);
      final Uri socketUri = apiUri
          .resolve('/api/v1/ws/diagnostics')
          .replace(scheme: apiUri.scheme == 'https' ? 'wss' : 'ws');
      socket = WebSocketChannel.connect(socketUri);
      await socket.ready.timeout(const Duration(seconds: 8));
      final Object? rawMessage = await socket.stream.first.timeout(
        const Duration(seconds: 8),
      );
      final Object? decoded = rawMessage is String
          ? jsonDecode(rawMessage)
          : null;
      if (decoded is Map && decoded['type'] == 'diagnostics.connected') {
        return const DiagnosticProbe(
          ok: true,
          message: 'Handshake e mensagem recebidos',
        );
      }
      return const DiagnosticProbe(
        ok: false,
        message: 'WebSocket respondeu com contrato inesperado',
      );
    } on TimeoutException {
      return const DiagnosticProbe(ok: false, message: 'Timeout no WebSocket');
    } on Object catch (error) {
      return DiagnosticProbe(
        ok: false,
        message: 'Falha no WebSocket (${error.runtimeType})',
      );
    } finally {
      if (socket != null) {
        try {
          await socket.sink.close();
        } on Object {
          // O resultado do diagnóstico já foi determinado; falha no close não
          // deve sobrescrever a causa principal.
        }
      }
    }
  }

  Future<DiagnosticProbe> probeMapSearch(MapProvider provider) async {
    if (provider.isDevelopmentFallback) {
      return const DiagnosticProbe(
        ok: false,
        message: 'MapTiler não inicializado; provider local ativo',
      );
    }
    try {
      final List<PlaceSuggestion> suggestions = await provider.search(
        'Torre Eiffel',
      );
      return DiagnosticProbe(
        ok: true,
        message: 'Consulta concluída (${suggestions.length} sugestões)',
      );
    } on Object catch (error) {
      return DiagnosticProbe(
        ok: false,
        message: 'Consulta falhou: ${error.toString()}',
      );
    }
  }
}
