import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    rollupOptions: {
      input: {
        popup: new URL('./popup.html', import.meta.url).pathname,
        offscreen: new URL('./offscreen.html', import.meta.url).pathname,
      },
    },
  },
});
