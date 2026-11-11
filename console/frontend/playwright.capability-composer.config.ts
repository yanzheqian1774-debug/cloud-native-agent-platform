import {defineConfig} from '@playwright/test';
import base from './playwright.capabilities.config';
export default defineConfig({...base,testMatch:['**/business-capabilities.spec.ts','**/capability-preparation-history.spec.ts','**/conversation-journey.spec.ts','**/business-reply-f3.spec.ts']});
