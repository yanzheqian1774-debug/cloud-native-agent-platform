import {defineConfig} from '@playwright/test';
import base from './playwright.team.config';
const server=base.webServer as {command:string;url:string;reuseExistingServer:boolean};
export default defineConfig({...base,webServer:{...server,command:'VITE_FIXED_WORK_ACTIVITY_READ_ENABLED=true '+server.command}});
