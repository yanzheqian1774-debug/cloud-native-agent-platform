import {defineConfig} from '@playwright/test';
import base from './playwright.config';

// Explicit mock-only review scopes. Both product modes run; never admit live files.
const assisted=process.env.PROTOTYPE_REVIEW_MODE==='assisted';
if(assisted!==(process.env.VITE_PROBLEM_DRAFT_ASSISTANCE==='enabled'))throw new Error('Prototype review mode must match the frontend assistance build.');
export default defineConfig({
 ...base,
 testMatch:assisted?[
  '**/s5-321-understanding.spec.ts','**/s5-323-visual.spec.ts',
  '**/s5-323-dialogue.spec.ts','**/s5-323-productization.spec.ts',
  '**/planning-target-recovery.spec.ts','**/planning-readonly-recovery.spec.ts',
 ]:[
  '**/w3-success-criteria.spec.ts','**/s5-324-execution.spec.ts',
  '**/prototype-shared-workspace.spec.ts','**/w2a-honest-shell.spec.ts',
 ],
 testIgnore:['**/*.real.spec.ts','**/*-live.spec.ts'],
});
