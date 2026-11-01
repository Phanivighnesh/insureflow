/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev: /api is proxied to the FastAPI server (default :8000). Production: set VITE_API_BASE to the backend URL.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': { target: process.env.VITE_PROXY_TARGET || 'http://localhost:8000', changeOrigin: true } } },
  test: { environment: 'jsdom', globals: true, globalSetup: ['./tests/globalSetup.ts'],
          env: { VITE_API_BASE: 'http://127.0.0.1:8791' }, setupFiles: ['./tests/setup.ts'], testTimeout: 30000, hookTimeout: 60000,
          include: ['tests/**/*.test.{ts,tsx}'], fileParallelism: false }
})
