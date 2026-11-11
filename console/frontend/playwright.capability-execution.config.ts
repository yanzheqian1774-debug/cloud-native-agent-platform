import {defineConfig} from '@playwright/test';
import base from './playwright.capabilities.config';
export default defineConfig({...base,testMatch:['**/business-capabilities.spec.ts','**/business-reply-f3.spec.ts']});
