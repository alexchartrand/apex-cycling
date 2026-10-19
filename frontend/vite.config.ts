/// <reference types="vitest/config" />
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, process.cwd(), ''), ...process.env }
  return {
    plugins: [
      react(),
      VitePWA({
        // The app shows its own "update available" prompt (src/pwa/).
        registerType: 'prompt',
        injectRegister: false,
        includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
        manifest: {
          name: 'ApexCycling',
          short_name: 'Apex',
          description: 'Track cycling training: sqorz laps, records, pursuit and aero tools.',
          lang: 'fr',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          orientation: 'portrait',
          theme_color: '#0B1220',
          background_color: '#0B1220',
          icons: [
            { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png' },
            { src: '/icons/icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          navigateFallback: '/index.html',
          navigateFallbackDenylist: [/^\/api\//],
          globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
          // Only Latin font subsets are worth precaching for a FR/EN app.
          globIgnores: ['**/*-{cyrillic,cyrillic-ext,greek,greek-ext,vietnamese}-*.woff2'],
          runtimeCaching: [
            {
              // Athlete data (+ who's logged in): network-first, so the
              // last-seen sessions still open on flaky velodrome wifi.
              // Wiped on logout (useLogout).
              urlPattern: ({ url, request }) =>
                request.method === 'GET' &&
                (url.pathname.startsWith('/api/athletes/') || url.pathname === '/api/auth/me'),
              handler: 'NetworkFirst',
              options: {
                cacheName: 'apex-api',
                networkTimeoutSeconds: 5,
                expiration: { maxEntries: 300, maxAgeSeconds: 7 * 24 * 60 * 60 },
                cacheableResponse: { statuses: [200] },
              },
            },
          ],
        },
      }),
    ],
    server: {
      // Proxying keeps the SPA and API on one origin in dev, same as prod, so
      // the samesite=lax auth cookies never cross origins.
      proxy: {
        '/api': {
          target: env.API_PROXY_TARGET ?? 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
