import react from '@vitejs/plugin-react';

export default {
  plugins: [react()],
  server: {
    port: 5174,
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
