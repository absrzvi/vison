import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// E10-S1 dev-only API mock — active ONLY when VITE_MOCK_API=1 is set on the dev
// server process. Lets the three new surfaces be browser-verified without a
// running cloud-backend. Never part of the production bundle.
function mockApiPlugin() {
  return {
    name: 'oebb-mock-api',
    apply: 'serve',
    configureServer(server) {
      if (process.env.VITE_MOCK_API !== '1') return
      const routes = {
        '/api/v1/analytics/system-health': {
          trains: [
            { id: 'R5001C-031', cctvStatus: 'green', appStatus: 'green', deviceStatus: 'green', last_healthy: null },
            { id: 'R5001C-003', cctvStatus: 'amber', appStatus: 'green', deviceStatus: 'green', last_healthy: new Date(Date.now() - 600_000).toISOString() },
          ],
        },
        '/api/v1/config/confidence-thresholds': {
          per_class: {
            unattended_bag: 0.75, door_obstruction: 0.85, accessibility_detected: 0.7,
            slip_fall: 0.75, luggage_rack_saturation: 0.7,
          },
          degraded_banner_floor: 0.6,
        },
        '/api/v1/health': { status: 'ok', ai_quality_degraded: true },
        '/api/v1/health/ai-pipeline': {
          fleet_state: 'amber',
          trains: [
            {
              train_id: 'R5001C-031', state: 'green',
              last_seen: new Date(Date.now() - 14_000).toISOString(),
              model_versions: { detector_arch: 'yolox_s_leaky', detector_code: 'git:9d4a60df' },
              hailo_device_ok: true,
            },
            {
              train_id: 'R5001C-003', state: 'amber',
              last_seen: new Date(Date.now() - 40_000).toISOString(),
              model_versions: { detector_arch: 'yolox_s_leaky', detector_code: 'git:9d4a60df' },
              hailo_device_ok: false,
            },
          ],
        },
      }
      server.middlewares.use((req, res, next) => {
        const path = req.url?.split('?')[0]
        if (path in routes) {
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(routes[path]))
          return
        }
        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), mockApiPlugin()],
  // Dev-only: when VITE_DEV_PROXY is set, proxy /api to the local backend so the
  // browser sees same-origin requests (prod serves the SPA from the backend
  // origin, so no CORS there). Lets REST/auth surfaces be browser-verified
  // without adding CORS middleware to the backend.
  server: process.env.VITE_DEV_PROXY
    ? { proxy: { '/api': { target: process.env.VITE_DEV_PROXY, changeOrigin: true } } }
    : undefined,
  test: {
    environment: 'node',
    globals: true,
    include: ['src/**/*.test.{js,jsx}', 'src/**/*.spec.{js,jsx}'],
    setupFiles: ['src/test-setup.js'],
  },
})
