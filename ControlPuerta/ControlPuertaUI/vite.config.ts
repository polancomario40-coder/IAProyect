import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: './', // Rutas relativas para que funcione en cualquier ruta, subcarpeta o subdominio en IIS
  server: {
    port: 5175,
    proxy: {
      '/api': {
        target: 'http://localhost:5200',
        changeOrigin: true,
      }
    }
  }
})
