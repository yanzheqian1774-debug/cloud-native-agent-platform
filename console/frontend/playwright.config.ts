import { defineConfig } from "@playwright/test";

const frontendPort=Number(process.env.CONSOLE_FRONTEND_PORT ?? "4173");
const immutable=process.env.S5_IMMUTABLE_ACCEPTANCE === "1";
const frontendOrigin=process.env.CONSOLE_FRONTEND_ORIGIN ?? `http://127.0.0.1:${frontendPort}`;
const certificateSpki=process.env.PLAYWRIGHT_HTTPS_CERTIFICATE_SPKI;

export default defineConfig({
  testDir: "./tests/e2e",
  testIgnore:
    process.env.S5_V023_IMPL_299_LIVE === "1"
      ? ["**/digital-employee-work-participation.real.spec.ts"]
      : [
          "**/digital-employee-work-participation.real.spec.ts",
          "**/*-live.spec.ts",
        ],
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR,
  timeout: 60_000,
  workers: 1,
  use: {
    baseURL: frontendOrigin,
    trace: "off",
    screenshot: "off",
    video: "off",
    launchOptions: {
      executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH,
      args: certificateSpki
        ? [`--ignore-certificate-errors-spki-list=${certificateSpki}`]
        : undefined,
    },
  },
  webServer: process.env.S5_REUSE_FRONTEND_SERVER === "1" ? undefined : [
    {
      command: immutable
        ? `${process.env.S5_HARNESS_PYTHON} ../../scripts/acceptance/static_proxy_server.py --root dist --host 127.0.0.1 --port ${frontendPort} --backend-url ${process.env.CONSOLE_BACKEND_URL}`
        : `VITE_SUPPLIER_QUALITY_DEMO_MODE=live npm run build && npm run preview -- --host 127.0.0.1 --port ${frontendPort}`,
      url: frontendOrigin,
      reuseExistingServer: false,
    },
  ],
});
