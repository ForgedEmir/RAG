import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
  optimizeDeps: {
    include: ['react-pdf'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'pdf-viewer': ['react-pdf', 'pdfjs-dist'],
          'mammoth': ['mammoth'],
        },
      },
    },
  },
});
