import {defineConfig} from '@playwright/test';
// Pure Response stream tests: no browser, platform or model connection.
export default defineConfig({testDir:'./tests/stream-observation',workers:1});
