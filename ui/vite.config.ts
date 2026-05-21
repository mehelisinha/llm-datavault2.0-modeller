/// <reference types="node" />
import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

/**
 * Vite config.
 *
 * - All host/port values come from env (no hardcoded literals).
 * - The `/api` proxy targets the FastAPI dev server so the browser sees a
 *   single origin and we avoid CORS in development.
 * - In production the FastAPI app serves the built UI from `dist/` via
 *   `StaticFiles` (Phase B6.7), so the proxy is dev-only.
 */
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const apiTarget = env.VITE_API_PROXY_TARGET ?? "http://localhost:8000";
  const devPort = Number(env.VITE_DEV_PORT ?? 5173);

  return {
    plugins: [react()],
    resolve: {
      alias: { "@": path.resolve(__dirname, "src") },
    },
    server: {
      port: devPort,
      strictPort: true,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true },
        "/health": { target: apiTarget, changeOrigin: true },
        "/openapi.json": { target: apiTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
      target: "es2022",
    },
  };
});
