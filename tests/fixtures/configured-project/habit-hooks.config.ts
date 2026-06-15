import type { HabitHooksConfig } from '../../../src/config/schema.js';

const config: HabitHooksConfig = {
  prompts: './prompts',
  smells: {
    'high-complexity': { disabled: true },
  },
};

export default config;
