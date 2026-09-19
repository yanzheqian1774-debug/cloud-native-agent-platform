import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:'s5-323-kimi.real.spec.ts',workers:1,retries:0,timeout:120000,outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR,use:{baseURL:'https://127.0.0.1:19434',ignoreHTTPSErrors:true,trace:'off'}});
