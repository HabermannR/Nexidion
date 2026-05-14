// In: vite.config.js

import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load environment variables from the frontend directory
  const env = loadEnv(mode, process.cwd(), '');

  // Use your private link if it exists in a .env file, otherwise use the local Docker backend
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://backend:5001';

  return {
    plugins: [react()],

    resolve: {
      //preserveSymlinks: true,
      alias: {
        // Points to the mounted directory from docker-compose
        '@nexidion/remark-internal-links': path.resolve(__dirname, '../remark-internal-links/src/index.js'),

        // Use this instead if your imports do not have the @nexidion prefix:
        // 'remark-internal-links': path.resolve(__dirname, '../remark-internal-links/src/index.js'),
      },
    },

    // optimizeDeps is removed because local aliases crash it

    server: {
      // Allow Vite to read outside the /app folder to reach the plugin
      fs: {
        allow: [
          '/app',
          '/remark-internal-links'
        ]
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          secure: false,
        },
      },
      host: true, // Listen on all network interfaces for Docker
    }
  };
});