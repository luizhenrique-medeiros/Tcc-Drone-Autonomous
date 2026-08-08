const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const apiBaseUrl = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000/api/v1',
);

const derivedWsBaseUrl = apiBaseUrl
  .replace(/^http:/, 'ws:')
  .replace(/^https:/, 'wss:');

export const DEFAULT_MAPTILER_STYLE_URL =
  'https://api.maptiler.com/maps/hybrid-v4/style.json';

interface MapTilerConfiguration {
  styleUrl: string;
  error: string | null;
}

export const resolveMapTilerConfiguration = (
  apiKey: string | undefined,
  configuredStyleUrl: string | undefined,
): MapTilerConfiguration => {
  const normalizedApiKey = apiKey?.trim() ?? '';
  if (!normalizedApiKey) {
    return {
      styleUrl: '',
      error: 'A chave web do MapTiler não foi configurada.',
    };
  }

  try {
    const styleUrl = new URL(
      configuredStyleUrl?.trim() || DEFAULT_MAPTILER_STYLE_URL,
    );
    const isMapTilerStyle =
      styleUrl.protocol === 'https:' &&
      styleUrl.hostname === 'api.maptiler.com' &&
      styleUrl.pathname.endsWith('/style.json');

    if (!isMapTilerStyle) {
      return {
        styleUrl: '',
        error: 'A URL de estilo do MapTiler é inválida.',
      };
    }

    // A chave é mantida em uma variável separada para evitar que o exemplo de
    // configuração ou o histórico do repositório contenham uma credencial real.
    styleUrl.searchParams.set('key', normalizedApiKey);
    return { styleUrl: styleUrl.toString(), error: null };
  } catch {
    return {
      styleUrl: '',
      error: 'A URL de estilo do MapTiler é inválida.',
    };
  }
};

const mapTilerConfiguration = resolveMapTilerConfiguration(
  import.meta.env.MAPTILER_WEB_API_KEY,
  import.meta.env.MAPTILER_STYLE_URL,
);

export const appConfig = {
  apiBaseUrl,
  wsBaseUrl: trimTrailingSlash(
    import.meta.env.VITE_WS_BASE_URL?.trim() || derivedWsBaseUrl,
  ),
  mapTilerStyleUrl: mapTilerConfiguration.styleUrl,
  mapTilerConfigError: mapTilerConfiguration.error,
  demoMode: import.meta.env.VITE_DEMO_MODE === 'true',
};
