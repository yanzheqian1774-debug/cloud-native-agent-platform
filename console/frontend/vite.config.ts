import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react(), {
    name: "workbench-build-profile",
    generateBundle() {
      this.emitFile({ type: "asset", fileName: "workbench-build-profile.json", source: JSON.stringify({
        schemaVersion: "workbench-build-profile.v1",
        draftAssistance: process.env.VITE_PROBLEM_DRAFT_ASSISTANCE === "enabled",
        trustedWorkbenchRoutes: process.env.VITE_SUPPLIER_QUALITY_DEMO_MODE === "live",
      }) });
    },
  }],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/healthz": {
        target: process.env.VITE_BACKEND_URL ?? "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
