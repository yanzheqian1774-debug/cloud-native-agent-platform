import {defineConfig} from '@playwright/test';
import base from './playwright.current-work.config';
export default defineConfig({...base,testMatch:['**/current-outcomes-native.spec.ts'],testIgnore:[]});
