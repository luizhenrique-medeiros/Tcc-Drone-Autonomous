import react from '@vitejs/plugin-react';

export default {
  plugins: [react()],
  envPrefix: ['VITE_', 'MAPTILER_WEB_API_KEY', 'MAPTILER_STYLE_URL'],
  server: {
    port: 5173,
    strictPort: true,
  },
  preview: {
    port: 4174,
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './tests/setup.ts',
    css: true,
    restoreMocks: true,
  },
};
