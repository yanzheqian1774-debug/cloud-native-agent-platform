import { defineConfig } from "@playwright/test";

const frontendPort=Number(process.env.CONSOLE_FRONTEND_PORT ?? "4173");
const immutable=process.env.S5_IMMUTABLE_ACCEPTANCE === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    trace: "off",
    screenshot: "off",
    video: "off",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
    },
  },
  webServer: [
    {
      command: immutable
        ? `${process.env.S5_HARNESS_PYTHON} ../../scripts/acceptance/static_proxy_server.py --root dist --host 127.0.0.1 --port ${frontendPort} --backend-url ${process.env.CONSOLE_BACKEND_URL}`
        : `VITE_SUPPLIER_QUALITY_DEMO_MODE=live npm run build && npm run preview -- --host 127.0.0.1 --port ${frontendPort}`,
      url: `http://127.0.0.1:${frontendPort}`,
      reuseExistingServer: false,
    },
  ],
});
