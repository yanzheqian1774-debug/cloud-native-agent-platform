import {defineConfig} from '@playwright/test';
import base from './playwright.team.config';
const server=base.webServer as {command:string;url:string;reuseExistingServer:boolean};
export default defineConfig({...base,testMatch:'fixed-work-natural-preview.spec.ts',webServer:{...server,command:'VITE_FIXED_WORK_NATURAL_PREVIEW_ENABLED=true '+server.command}});
