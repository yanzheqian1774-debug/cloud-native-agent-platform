import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,use:{...base.use,viewport:{width:1440,height:1000}},testMatch:'**/native-durable-progress.spec.ts'});
