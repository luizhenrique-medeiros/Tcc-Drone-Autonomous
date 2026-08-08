/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly MAPTILER_STYLE_URL?: string;
  readonly MAPTILER_WEB_API_KEY?: string;
  readonly VITE_API_BASE_URL?: string;
  readonly VITE_DEMO_MODE?: string;
  readonly VITE_WS_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
