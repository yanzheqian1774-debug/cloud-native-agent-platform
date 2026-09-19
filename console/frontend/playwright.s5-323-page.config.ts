import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:'s5-323-page.real.spec.ts',workers:1,retries:0,timeout:90000,outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR,use:{baseURL:'https://127.0.0.1:19424',ignoreHTTPSErrors:true,trace:'off'}});
