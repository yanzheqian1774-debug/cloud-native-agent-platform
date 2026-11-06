import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testDir:'./tests/e2e',testMatch:['continuous-journey.spec.ts','current-work-entry.spec.ts','resource-automation.spec.ts','readonly-continuation.spec.ts','planning-target-recovery.spec.ts','s5-324-planning-admission.spec.ts'],testIgnore:[]});
