import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./tests/e2e', testMatch:'s5-321-understanding.spec.ts', workers:1, retries:0,
  outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR, timeout:60_000,
  use:{baseURL:'http://127.0.0.1:19321',viewport:{width:1440,height:1000},trace:'off'},
  webServer:{command:'VITE_SUPPLIER_QUALITY_DEMO_MODE=live VITE_PROBLEM_DRAFT_ASSISTANCE=enabled npm run build && npm run preview -- --host 127.0.0.1 --port 19321',url:'http://127.0.0.1:19321',reuseExistingServer:false},
});
