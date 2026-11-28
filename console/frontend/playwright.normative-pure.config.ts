import {defineConfig} from '@playwright/test';
/** Pure projection tests only: no browser, web server or platform/API connection. */
export default defineConfig({testDir:'./tests/normative-section-pure',testMatch:'*.spec.ts',workers:1,reporter:[['list'],['junit',{outputFile:'normative-pure-results.xml'}]],outputDir:'normative-pure-output'});
