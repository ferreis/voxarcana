import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: { proxy: { '/v1': 'http://127.0.0.1:8765', '/health': 'http://127.0.0.1:8765' } },
})
