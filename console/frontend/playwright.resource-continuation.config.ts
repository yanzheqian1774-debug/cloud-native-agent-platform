import {defineConfig} from '@playwright/test';
import base from './playwright.config';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
const profile=JSON.parse(readFileSync(new URL('./dist/workbench-build-profile.json',import.meta.url),'utf8'));
if(!profile.trustedWorkbenchRoutes||!profile.resourceDirectory||!profile.resourceAuthoring||!profile.draftAssistance)throw Error('Trusted complete resource continuation build required');
const legacyRoot=process.env.CONSOLE_LEGACY_DIST;
if(!legacyRoot)throw Error('Separate existing legacy profile required');
const legacyProfile=JSON.parse(readFileSync(join(legacyRoot,'workbench-build-profile.json'),'utf8'));
if(legacyProfile.resourceDirectory||legacyProfile.resourceAuthoring||!legacyProfile.trustedWorkbenchRoutes)throw Error('Compatibility tests require their original legacy profile');
const port=Number(process.env.CONSOLE_FRONTEND_PORT??'4210');
export default defineConfig({...base,retries:0,testDir:'.',testIgnore:[],use:{...base.use,baseURL:`http://127.0.0.1:${port}`},
 projects:[
  {name:'resource-maintenance',testDir:'./tests/resource-management',testMatch:'*.spec.ts'},
  {name:'employee-preservation',testDir:'./tests/e2e',testMatch:['employee-relations.spec.ts','digital-employee-work-participation.spec.ts']},
  {name:'original-sales-conversation',testDir:'./tests/e2e',testMatch:'sales-scene-conversation.spec.ts'},
  {name:'exact-resource-result-return',testDir:'./tests/e2e',testMatch:['jx01-skill-return.spec.ts','jx02-resource-readback.spec.ts']},
  {name:'legacy-resource-projection',testDir:'./tests/e2e',testMatch:'execution-resource-details.spec.ts',use:{baseURL:`http://127.0.0.1:${port+1}`}},
  {name:'automatic-resource-preparation',testDir:'./tests/e2e',testMatch:'resource-automation.spec.ts'},
 ],
 webServer:[{command:`npm run preview -- --host 127.0.0.1 --port ${port}`,url:`http://127.0.0.1:${port}`,reuseExistingServer:false},{command:`npm run preview -- --outDir "$CONSOLE_LEGACY_DIST" --host 127.0.0.1 --port ${port+1}`,url:`http://127.0.0.1:${port+1}`,reuseExistingServer:false}],
});
