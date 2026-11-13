import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testMatch:['understanding-adoption.spec.ts'],workers:1});
