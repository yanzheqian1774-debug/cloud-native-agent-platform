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
        resourceDirectory: process.env.VITE_RESOURCE_DIRECTORY_ENABLED === "true",
        resourceAuthoring: process.env.VITE_RESOURCE_AUTHORING_ENABLED === "true",
        currentWorkDirectory: process.env.VITE_CURRENT_WORK_DIRECTORY_ENABLED === "true",
        selectedResourceUpgrades: process.env.VITE_SELECTED_RESOURCE_UPGRADES_ENABLED === "true",
        businessCapabilities: process.env.VITE_BUSINESS_CAPABILITIES_ENABLED === "true",
        businessProcessDefinitions: process.env.VITE_BUSINESS_PROCESS_DEFINITIONS_ENABLED === "true",
        teamDefinitions: process.env.VITE_TEAM_DEFINITIONS_ENABLED === "true",
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
