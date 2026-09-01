import { defineConfig } from "@playwright/test";

const externalBaseUrl = process.env.PRODUCTION_ROUTE_BASE_URL;

export default defineConfig({
  testDir: "./tests/production-route",
  timeout: 60_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: externalBaseUrl ?? "http://127.0.0.1:4174",
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: externalBaseUrl ? undefined : {
    command: "npm run build && npm run preview -- --host 127.0.0.1 --port 4174",
    url: "http://127.0.0.1:4174",
    reuseExistingServer: false,
  },
});
