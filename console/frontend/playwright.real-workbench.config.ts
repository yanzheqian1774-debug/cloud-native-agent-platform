import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: process.env.S5_310_WORKBENCH_URL,
    ignoreHTTPSErrors: true,
    trace: "retain-on-failure",
  },
});
