import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testDir:'./tests/e2e',testMatch:'digital-employee-work-participation.spec.ts',testIgnore:[]});
