import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
const csp =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' blob:; connect-src 'self'; font-src 'self'; worker-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'";
export default defineConfig({
  plugins: [react()],
  base: '/workspace/',
  build: { sourcemap: false },
  server: {
    strictPort: true,
    proxy: { '/v2': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  preview: {
    strictPort: true,
    headers: {
      'Content-Security-Policy': csp,
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer',
    },
  },
  test: { include: ['src/**/*.test.ts', 'scripts/**/*.test.mjs'] },
});
