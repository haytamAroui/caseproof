import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
export default defineConfig({
  base: '/workspace/',
  publicDir: fileURLToPath(new URL('./generated', import.meta.url)),
  build: {
    outDir: 'viewer-dist',
    emptyOutDir: true,
    rollupOptions: {
      input: fileURLToPath(new URL('./harness.html', import.meta.url)),
    },
  },
  preview: {
    strictPort: true,
    headers: {
      'Content-Security-Policy':
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; worker-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
      'Cache-Control': 'no-store',
    },
  },
});
