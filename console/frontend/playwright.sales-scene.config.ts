import {defineConfig} from '@playwright/test';
import base from './playwright.config';
import {readFileSync} from 'node:fs';
const profile=JSON.parse(readFileSync(new URL('./dist/workbench-build-profile.json',import.meta.url),'utf8'));
if(!profile.trustedWorkbenchRoutes||!profile.draftAssistance||!profile.resourceDirectory||!profile.resourceAuthoring)throw Error('Build the existing trusted Workbench profile before the sales journey check.');
const port=Number(process.env.CONSOLE_FRONTEND_PORT??4198);
export default defineConfig({...base,testDir:'./tests/e2e',timeout:45000,retries:0,workers:1,
 use:{...base.use,baseURL:`http://127.0.0.1:${port}`},
 webServer:{command:`npm run preview -- --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false},
 projects:[
  {name:'sales-scene',testMatch:'sales-scene-conversation.spec.ts'},
  {name:'original-return',testMatch:['jx01-skill-return.spec.ts','jx02-resource-readback.spec.ts']},
  {name:'preserved-reader-guards',testDir:'./tests/resource-management',testMatch:'skill-io-projection.spec.ts'},
  {name:'sales-artifact',testMatch:'s5-324-execution.spec.ts',grep:/gross profit v2 isolated reader|sales diagnostic exposes|mismatched report source/},
 ],
});
