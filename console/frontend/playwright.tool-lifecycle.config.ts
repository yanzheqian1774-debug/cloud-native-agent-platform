import {defineConfig} from '@playwright/test';
import base from './playwright.tool-import.config';
const port=Number(process.env.CONSOLE_FRONTEND_PORT??'54139');
export default defineConfig({...base,testMatch:['tool-lifecycle.spec.ts','tool-import.spec.ts'],retries:0,workers:1,use:{...base.use,baseURL:`http://127.0.0.1:${port}`},webServer:{command:`node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false}});
