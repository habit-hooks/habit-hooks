import { existsSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { defaultRules } from '../../config/defaults.js';

const CONFIG_FILENAMES = [
  'habit-hooks.config.ts',
  'habit-hooks.config.mjs',
  'habit-hooks.config.js',
  'habit-hooks.config.json',
];

export const NEW_CONFIG_FILENAME = 'habit-hooks.config.ts';

function existingConfig(cwd: string): string | null {
  for (const name of CONFIG_FILENAMES) {
    const candidate = join(cwd, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

function renderRuleEntry(id: string): string {
  return `    // '${id}': { severity: 'enforced', changedFilesOnly: false },`;
}

const CONFIG_HEADER = [
  `import type { HabitHooksConfig } from 'habit-hooks';`,
  ``,
  `const config: HabitHooksConfig = {`,
  `  // Override any default rule by uncommenting and editing.`,
  `  // Run \`habit-hooks --help\` for the full option list.`,
  `  rules: {`,
];

const CONFIG_FOOTER = [
  `  },`,
  `  scope: {`,
  `    onlyChangedFiles: false,`,
  `    autoBranchOffMain: false,`,
  `    mainBranch: 'main',`,
  `  },`,
  `};`,
  ``,
  `export default config;`,
  ``,
];

function renderConfigBody(): string {
  const ruleLines = defaultRules.map((r) => renderRuleEntry(r.id));
  return [...CONFIG_HEADER, ...ruleLines, ...CONFIG_FOOTER].join('\n');
}

export interface ScaffoldResult {
  path: string;
  conflict: string | null;
}

export function scaffoldConfig(cwd: string): ScaffoldResult {
  const existing = existingConfig(cwd);
  if (existing !== null) return { path: existing, conflict: existing };
  const path = join(cwd, NEW_CONFIG_FILENAME);
  writeFileSync(path, renderConfigBody());
  return { path, conflict: null };
}
