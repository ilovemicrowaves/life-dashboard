import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'

// Bewust conservatief: ES2018 zodat het draait op de oudere Chromium (~87)
// in de WebOS-browser van de TV. Geen container queries / :has() / subgrid in CSS.
export default defineConfig({
  plugins: [svelte()],
  build: {
    target: 'es2018',
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    // In dev draait de API apart; proxy /api ernaartoe.
    proxy: {
      '/api': 'http://127.0.0.1:8765',
    },
  },
})
