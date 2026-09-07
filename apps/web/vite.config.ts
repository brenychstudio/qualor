import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { localProxyError, sessionOrigin } from './devProxy.ts';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        configure(proxy) {
          proxy.on('error', (error, _request, response) => {
            const unavailable = localProxyError(error);
            if (unavailable && 'writeHead' in response && !response.headersSent && !response.writableEnded) {
              response.writeHead(unavailable.status, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
              response.end(JSON.stringify(unavailable.body));
            }
          });
          proxy.on('proxyReq', (proxyRequest, request) => {
            const origin = sessionOrigin(request);
            if (origin) proxyRequest.setHeader('Origin', origin);
          });
        },
      },
    },
  },
});
