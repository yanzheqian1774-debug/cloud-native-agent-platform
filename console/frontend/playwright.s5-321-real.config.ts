import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:'s5-321-understanding.real.spec.ts',workers:1,retries:0,timeout:120_000,outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR,use:{baseURL:'https://127.0.0.1:19322',ignoreHTTPSErrors:true,viewport:{width:1440,height:1000},trace:'off',screenshot:'only-on-failure'}});
