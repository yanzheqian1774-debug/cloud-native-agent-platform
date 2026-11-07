import {defineConfig} from '@playwright/test';
import base from './playwright.config';
import {readFileSync} from 'node:fs';
const profile=JSON.parse(readFileSync(new URL('./dist/workbench-build-profile.json',import.meta.url),'utf8'));
if(!profile.trustedWorkbenchRoutes||!profile.resourceDirectory||!profile.resourceAuthoring)throw Error('Build the trusted Workbench profile before management checks.');
const port=Number(process.env.CONSOLE_FRONTEND_PORT??4208);
export default defineConfig({...base,testDir:'./tests/e2e',retries:0,workers:1,timeout:45000,
 use:{...base.use,baseURL:`http://127.0.0.1:${port}`},
 webServer:{command:`npm run preview -- --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false},
 projects:[
  {name:'employee-relations',testMatch:'employee-relations.spec.ts'},
  {name:'employee-existing',testMatch:'digital-employee-work-participation.spec.ts'},
  {name:'employee-composition',testDir:'./tests/resource-management',testMatch:'employee-composition.spec.ts'},
  {name:'sales-scene-preservation',testMatch:'sales-scene-conversation.spec.ts'},
 ],
});
