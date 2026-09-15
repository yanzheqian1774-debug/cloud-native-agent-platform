import { defineConfig } from "@playwright/test";

function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name}_REQUIRED`);
  return value;
}

export default defineConfig({
  testDir: "./tests/e2e",
  testMatch: "trusted-native-combination.real.spec.ts",
  outputDir: process.env.PLAYWRIGHT_OUTPUT_DIR,
  timeout: 180_000,
  workers: 1,
  retries: 0,
  use: {
    baseURL: required("REL_317_WORKBENCH_URL"),
    ignoreHTTPSErrors: true,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
  },
});
