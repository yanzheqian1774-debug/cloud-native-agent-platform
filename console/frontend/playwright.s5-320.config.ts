import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "s5-320-kimi-draft-assistance.real.spec.ts",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR,
  timeout: 120_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.S5_320_WORKBENCH_URL,
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
});
