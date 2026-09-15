import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "digital-employee-work-participation.real.spec.ts",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR,
  timeout: 90_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.S5_310_WORKBENCH_URL,
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
    trace: "off",
    screenshot: "off",
    video: "off",
  },
});
