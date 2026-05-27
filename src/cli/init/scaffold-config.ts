import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const CONFIG_FILENAMES = [
  'habit-hooks.config.ts',
  'habit-hooks.config.mjs',
  'habit-hooks.config.js',
  'habit-hooks.config.json',
];

export const NEW_CONFIG_FILENAME = 'habit-hooks.config.js';

export const CONFIG_TEMPLATE = `export default {
  scope: {
    onlyChangedFiles: true,
    branchBase: 'main',
  },
};
`;

export interface ScaffoldResult {
  path: string;
  created: boolean;
}

function existingConfig(cwd: string): string | null {
  for (const name of CONFIG_FILENAMES) {
    const candidate = join(cwd, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export function scaffoldConfig(cwd: string): ScaffoldResult {
  const existing = existingConfig(cwd);
  if (existing !== null) return { path: existing, created: false };
  const path = join(cwd, NEW_CONFIG_FILENAME);
  writeFileSync(path, CONFIG_TEMPLATE);
  return { path, created: true };
}
