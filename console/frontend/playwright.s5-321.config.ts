import {defineConfig} from '@playwright/test';
const port=Number(process.env.CONSOLE_FRONTEND_PORT??'19321');
export default defineConfig({
  testDir:'./tests/e2e', testMatch:'s5-321-understanding.spec.ts', workers:1, retries:0,
  outputDir:process.env.PLAYWRIGHT_OUTPUT_DIR, timeout:60_000,
  use:{baseURL:`http://127.0.0.1:${port}`,viewport:{width:1440,height:1000},trace:'off'},
  webServer:{command:`VITE_SUPPLIER_QUALITY_DEMO_MODE=live VITE_PROBLEM_DRAFT_ASSISTANCE=enabled npm run build && npm run preview -- --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false},
});
