import type { HabitHooksConfig } from './schema.js';

export { defaultRules } from './catalogue.js';

export const TEST_FILE_EXCLUDE = ['**/*.test.ts', '**/*.spec.ts', 'tests/**'];

const CONFIG_FILE_EXCLUDE = ['habit-hooks.config.*'];

export const defaultConfig: HabitHooksConfig = {
  smells: {
    'oversized-function': { exclude: TEST_FILE_EXCLUDE },
    'oversized-file': { exclude: TEST_FILE_EXCLUDE },
    'duplicated-code': { exclude: TEST_FILE_EXCLUDE },
    'non-essential-comment': { exclude: CONFIG_FILE_EXCLUDE },
  },
};
