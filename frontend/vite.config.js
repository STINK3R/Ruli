import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API dev-proxy тоже проходит через единственный опубликованный сервис nginx.
const backend = process.env.VITE_DEV_PROXY_TARGET || 'http://localhost'

export default defineConfig({
  plugins: [react()],
  build: {
    // Движок карты — отдельным файлом: он крупный и меняется реже кода приложения.
    rollupOptions: { output: { manualChunks: { maplibre: ['maplibre-gl'] } } },
    chunkSizeWarningLimit: 1100,
  },
  server: {
    port: 5173,
    // Те же пути, что проксирует nginx в Docker, — фронтенд везде ходит на /api.
    proxy: {
      '/api': backend,
      '/admin': backend,
      '/static': backend,
      '/media': backend,
    },
  },
})
