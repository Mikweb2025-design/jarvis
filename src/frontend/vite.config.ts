import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/',
  build: {
    outDir: '../../dist/frontend',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:9999',
        changeOrigin: true,
      },
      '/assets': {
        target: 'http://127.0.0.1:9999',
        changeOrigin: true,
      },
      '/pages': {
        target: 'http://127.0.0.1:9999',
        changeOrigin: true,
      },
    },
  },
});
