import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    headers: {
      "Content-Security-Policy": "script-src 'self' 'wasm-unsafe-eval' 'inline-speculation-rules' http://localhost:* http://127.0.0.1:* https://apis.google.com https://www.gstatic.com; object-src 'self'",
    },
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        popup: new URL('./popup.html', import.meta.url).pathname,
        offscreen: new URL('./offscreen.html', import.meta.url).pathname,
        background: new URL('./src/background.js', import.meta.url).pathname,
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
});
