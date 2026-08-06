const trimTrailingSlash = (value: string) => value.replace(/\/+$/, '');

const apiBaseUrl = trimTrailingSlash(
  import.meta.env.VITE_API_BASE_URL?.trim() || 'http://localhost:8000/api/v1',
);

const derivedWsBaseUrl = apiBaseUrl
  .replace(/^http:/, 'ws:')
  .replace(/^https:/, 'wss:');

export const appConfig = {
  apiBaseUrl,
  wsBaseUrl: trimTrailingSlash(
    import.meta.env.VITE_WS_BASE_URL?.trim() || derivedWsBaseUrl,
  ),
  googleMapsKey: import.meta.env.VITE_GOOGLE_MAPS_BROWSER_API_KEY ?? '',
  demoMode: import.meta.env.VITE_DEMO_MODE === 'true',
};
