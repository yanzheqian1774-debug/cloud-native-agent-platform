import {defineConfig} from '@playwright/test';
import base from './playwright.team.config';
const server=base.webServer as {command:string;url:string;reuseExistingServer:boolean};
export default defineConfig({...base,workers:1,testMatch:'fixed-work-source.spec.ts',webServer:{...server,command:'VITE_FIXED_WORK_SOURCE_ENABLED=true '+server.command}});
