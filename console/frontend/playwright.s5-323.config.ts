import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests/e2e',testMatch:'s5-323-planning.real.spec.ts',workers:1,retries:0,timeout:30000,outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR,use:{baseURL:'https://127.0.0.1:19324',ignoreHTTPSErrors:true,viewport:{width:1500,height:1050},trace:'off'}});
