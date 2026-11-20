import {defineConfig} from '@playwright/test';
import base from './playwright.team.config';
const server=base.webServer as {command:string;url:string;reuseExistingServer:boolean};
export default defineConfig({...base,testDir:'./tests',testMatch:['**/current-outcomes-native.spec.ts','**/fixed-work-configuration.spec.ts','**/fixed-work-natural-preview.spec.ts','**/fixed-work-source.spec.ts','**/workflow-policy-publication.spec.ts','**/workflow-authoring.spec.ts'],workers:1,maxFailures:1,webServer:{...server,command:'VITE_FIXED_WORK_NATURAL_PREVIEW_ENABLED=true VITE_FIXED_WORK_ACTIVITY_READ_ENABLED=true VITE_BUSINESS_CAPABILITIES_ENABLED=true VITE_FIXED_WORK_SOURCE_ENABLED=true VITE_CURRENT_WORK_DIRECTORY_ENABLED=true '+server.command}});
