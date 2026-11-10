import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testMatch:'**/current-work-native.spec.ts',testIgnore:[],
 webServer:{...base.webServer as object,command:'VITE_CURRENT_WORK_DIRECTORY_ENABLED=true VITE_RESOURCE_AUTHORING_ENABLED=true VITE_RESOURCE_DIRECTORY_ENABLED=true VITE_SUPPLIER_QUALITY_DEMO_MODE=live VITE_PROBLEM_DRAFT_ASSISTANCE=enabled npm run build && npm run preview -- --host 127.0.0.1 --port 4178',url:'http://127.0.0.1:4178',reuseExistingServer:false}});
