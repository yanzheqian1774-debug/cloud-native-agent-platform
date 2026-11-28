import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
const port=Number(process.env.CONSOLE_FRONTEND_PORT??'54149');
export default defineConfig({...base,testMatch:['mcp-saved-selection.spec.ts'],retries:0,workers:1,
 use:{...base.use,baseURL:`http://127.0.0.1:${port}`},
 webServer:{command:`node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false}});
