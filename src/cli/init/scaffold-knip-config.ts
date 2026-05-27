import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { TOOL_CONFIG_FILENAMES } from '../../detect/tool.js';
import { KNIP_CONFIG_FILENAME, KNIP_CONFIG_TEMPLATE } from './templates/knip-config.js';

const ALL_FILENAMES = TOOL_CONFIG_FILENAMES.knip;

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

export function scaffoldKnipConfig(cwd: string): ScaffoldResult {
  const existing = existingConfig(cwd);
  if (existing !== null) return { path: existing, created: false };
  const path = join(cwd, KNIP_CONFIG_FILENAME);
  writeFileSync(path, KNIP_CONFIG_TEMPLATE);
  return { path, created: true };
}
