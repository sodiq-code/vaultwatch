import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // /api/* is the legacy mount path used by dashboard/src/liveApi.js
      // (kept for backwards compat). Vite rewrites /api/foo -> /foo on the
      // FastAPI app, so /api/cspr_cloud/blocks -> /cspr_cloud/blocks.
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // /cspr_cloud/* is the canonical proxy path (Critical Fix 6). Forward
      // verbatim — no rewrite — so /cspr_cloud/blocks -> /cspr_cloud/blocks.
      '/cspr_cloud': {
        target: process.env.VITE_API_URL || 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
