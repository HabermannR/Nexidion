import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // This is the magic part
    proxy: {
      // Any request starting with '/api' will be forwarded
      '/api': {
        // Your Flask backend server address
        target: 'http://localhost:5001', 
        // Important for CORS and virtual hosts
        changeOrigin: true, 
      },
    },
    // This makes your dev server accessible on your local network
    host: true, 
  }
})