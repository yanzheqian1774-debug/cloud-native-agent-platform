import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

// These assertions require the assisted-entry build. Keep the manual-entry
// acceptance build separate; both suites run in CI without skipped assertions.
const port = Number(process.env.CONSOLE_FRONTEND_PORT ?? "4173");
export default defineConfig({
  ...base,
  testDir: "./tests/assisted-entry",
  testIgnore: [],
  retries: 0,
  webServer: {
    command: `VITE_SUPPLIER_QUALITY_DEMO_MODE=live VITE_PROBLEM_DRAFT_ASSISTANCE=enabled npm run build && npm run preview -- --host 127.0.0.1 --port ${port}`,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
  },
});
