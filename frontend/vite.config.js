// In: vite.config.js

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path'; // NEU: Importiere das 'path'-Modul

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  resolve: {
    preserveSymlinks: true, // Behalte diese Einstellung bei

    // ==========================================================
    // NEU: Die ALIAS-Methode
    // ==========================================================
    alias: {
      // Wir erstellen einen Alias.
      // Links: Der Name, den du in deinem `import`-Statement verwendest.
      // Rechts: Der absolute Pfad zum Quellcode-Verzeichnis deines Plugins.
      '@nexidion/remark-internal-links': path.resolve(__dirname, '../../remark-internal-links/src/index.js'),
    },
  },

  // optimizeDeps kann oft entfernt werden, wenn du einen Alias verwendest,
  // aber es schadet nicht, es zur Sicherheit drin zu lassen.
  optimizeDeps: {
    include: ['remark-internal-links'],
  },

  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
    host: true,
  }
});