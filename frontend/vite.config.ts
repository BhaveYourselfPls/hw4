import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API + image requests to the FastAPI backend so the front end can use
// same-origin relative URLs in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/images': { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
