import {defineConfig} from '@playwright/test';
import base from './playwright.capabilities.config';
export default defineConfig({...base,testMatch:['**/capability-preparation-history.spec.ts','**/business-capabilities.spec.ts']});
