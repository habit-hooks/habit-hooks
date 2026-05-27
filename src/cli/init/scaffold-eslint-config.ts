import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { TOOL_CONFIG_FILENAMES } from '../../detect/tool.js';
import { ESLINT_CONFIG_FILENAME, ESLINT_CONFIG_TEMPLATE } from './templates/eslint-config.js';

const ALL_FILENAMES = TOOL_CONFIG_FILENAMES.eslint;

export interface ScaffoldResult {
  path: string;
  created: boolean;
}

function existingConfig(cwd: string): string | null {
  for (const name of ALL_FILENAMES) {
    const candidate = join(cwd, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

export function scaffoldEslintConfig(cwd: string): ScaffoldResult {
  const existing = existingConfig(cwd);
  if (existing !== null) return { path: existing, created: false };
  const path = join(cwd, ESLINT_CONFIG_FILENAME);
  writeFileSync(path, ESLINT_CONFIG_TEMPLATE);
  return { path, created: true };
}
