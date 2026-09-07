import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('leaflet') || id.includes('mapbox-gl')) {
              return 'vendor-maps';
            }
            if (id.includes('recharts') || id.includes('d3')) {
              return 'vendor-charts';
            }
            if (id.includes('three/src/renderers') || id.includes('three/src/materials') || id.includes('three/src/textures')) {
              return 'vendor-three-render';
            }
            if (id.includes('three')) {
              return 'vendor-three-core';
            }
            if (id.includes('lucide-react') || id.includes('framer-motion')) {
              return 'vendor-icons';
            }
            if (id.includes('react') || id.includes('zustand') || id.includes('axios')) {
              return 'vendor-core';
            }
            return 'vendor-misc';
          }
        },
      },
    },
  },
});
