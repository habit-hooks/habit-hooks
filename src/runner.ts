import fg from 'fast-glob';
import { eslintCheck } from './checks/eslint-check.js';
import { report } from './reporter.js';
import { getRules } from './rules/registry.js';

export interface RunResult {
  stdout: string;
  exitCode: number;
}

async function discoverFiles(cwd: string): Promise<string[]> {
  return fg(['**/*.{ts,tsx,js,mjs,cjs}'], {
    cwd,
    absolute: true,
    ignore: ['**/node_modules/**', '**/dist/**', '**/coverage/**'],
    dot: false,
  });
}

export async function run(cwd: string): Promise<RunResult> {
  const rules = getRules();
  const files = await discoverFiles(cwd);
  const violations = await eslintCheck.run(files, rules);
  return report(violations, rules);
}
