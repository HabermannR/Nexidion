import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // Default to localhost for baremetal (Windows/Linux)
  // Docker will override this to 'http://backend:5001' using environment variables!
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5001';

  return {
    plugins: [react()],

    resolve: {
      alias: {
        // Dynamically points to the sibling directory, regardless of OS
        '@nexidion/remark-internal-links': path.resolve(__dirname, '../remark-internal-links/src/index.js'),
      },
    },

    server: {
      fs: {
        allow: [
          // This dynamically allows the entire parent Nexidion folder.
          // This replaces your hardcoded '/app' and works on Windows, Linux, and Docker!
          path.resolve(__dirname, '../')
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