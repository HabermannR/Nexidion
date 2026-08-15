import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import { fileURLToPath } from 'url';

const projectDir = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectDir, '');

  // Default to localhost for baremetal (Windows/Linux)
  // Docker will override this to 'http://backend:5001' using environment variables!
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:5001';

  return {
    plugins: [react()],

    // npm installs the vendored package as a symlink. Resolve imports from the
    // consumer path so the package's runtime dependencies use frontend/node_modules.
    resolve: {
      preserveSymlinks: true,
    },

    server: {
      fs: {
        allow: [
          // This dynamically allows the entire parent Nexidion folder.
          // This replaces your hardcoded '/app' and works on Windows, Linux, and Docker!
          path.resolve(projectDir, '../')
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
    },

    test: {
      environment: 'jsdom',
    },
  };
});
