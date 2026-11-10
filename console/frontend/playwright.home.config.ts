import {defineConfig} from '@playwright/test';
import base from './playwright.current-work.config';
export default defineConfig({...base,testDir:'./tests/home',testMatch:'**/*.spec.ts',testIgnore:[]});
