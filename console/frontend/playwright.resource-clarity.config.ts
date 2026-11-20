import {defineConfig} from '@playwright/test';
import base from './playwright.resource-management.config';
export default defineConfig({...base,testMatch:['**/resource-test-clarity.spec.ts','**/f3-resource-detail.spec.ts','**/prepared-skill-maintenance.spec.ts','**/skill-testing-state.spec.ts','**/employee-resource-closure.spec.ts','**/resource-authoring.spec.ts','**/resource-card-maintenance.spec.ts','**/resource-detail-layout.spec.ts','**/resource-maintenance-journey.spec.ts','**/f3-resource-prototype.spec.ts','**/ui01-resource-detail.spec.ts'],workers:1});
