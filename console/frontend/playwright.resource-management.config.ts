import {defineConfig} from '@playwright/test';
import base from './playwright.config';
const port=Number(process.env.CONSOLE_FRONTEND_PORT??'4178');
export default defineConfig({...base,testDir:'./tests/resource-management',testIgnore:['**/current-work-native.spec.ts','**/current-attention-native.spec.ts'],retries:0,
 use:{...base.use,baseURL:`http://127.0.0.1:${port}`},
 webServer:{command:`VITE_RESOURCE_AUTHORING_ENABLED=true VITE_RESOURCE_DIRECTORY_ENABLED=true VITE_SUPPLIER_QUALITY_DEMO_MODE=live VITE_PROBLEM_DRAFT_ASSISTANCE=enabled npm run build && npm run preview -- --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false}});
