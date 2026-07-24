import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // The dashboard ships plain CSS (no Tailwind / PostCSS plugins). Without an
  // explicit inline PostCSS config, Vite's postcss-load-config walks up the
  // directory tree and picks up the parent Next.js project's postcss.config.mjs
  // (which references @tailwindcss/postcss, not installed in this package) and
  // the build fails. Setting an empty inline config scopes PostCSS to this
  // package and prevents the upward search.
  css: {
    postcss: { plugins: [] },
  },
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
