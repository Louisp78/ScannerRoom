import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import tailwindcss from '@tailwindcss/vite'
import { ingest } from './vite-plugins/ingest'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools(), tailwindcss(), ingest()],
  server: {
    // The pipeline writes thousands of frames and a Python venv lives there.
    watch: { ignored: ['**/playground/**'] },
    // The API (api/, `npm run dev` there) is served on the same origin, as in
    // production, so the session cookie and the CSRF origin check just work.
    proxy: { '/api': 'http://localhost:3002' },
  },
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
