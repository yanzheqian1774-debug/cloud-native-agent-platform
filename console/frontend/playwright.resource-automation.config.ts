import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testDir:'./tests/e2e',testMatch:'resource-automation.spec.ts',testIgnore:[]});
