import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const HABIT_HOOKS_SCRIPT = 'habit-hooks';
const HABIT_HOOKS_COMMAND = 'habit-hooks';
const CI_SCRIPT = 'ci';

const CI_CANDIDATES = ['lint', 'test', 'build', HABIT_HOOKS_SCRIPT];

interface PackageJson {
  scripts?: Record<string, string>;
  [key: string]: unknown;
}

export interface ScriptResult {
  action: 'added' | 'kept' | 'conflict' | 'no-package-json';
  before?: string;
}

function readPackageJson(cwd: string): { path: string; data: PackageJson } | null {
  const path = join(cwd, 'package.json');
  if (!existsSync(path)) return null;
  const raw = readFileSync(path, 'utf8');
  return { path, data: JSON.parse(raw) as PackageJson };
}

function writePackageJson(path: string, data: PackageJson): void {
  writeFileSync(path, `${JSON.stringify(data, null, 2)}\n`);
}

function ensureScripts(data: PackageJson): Record<string, string> {
  if (!data.scripts) data.scripts = {};
  return data.scripts;
}

export function addHabitHooksScript(cwd: string): ScriptResult {
  const pkg = readPackageJson(cwd);
  if (pkg === null) return { action: 'no-package-json' };
  const scripts = ensureScripts(pkg.data);
  const existing = scripts[HABIT_HOOKS_SCRIPT];
  if (existing === HABIT_HOOKS_COMMAND) return { action: 'kept', before: existing };
  if (existing !== undefined) return { action: 'conflict', before: existing };
  scripts[HABIT_HOOKS_SCRIPT] = HABIT_HOOKS_COMMAND;
  writePackageJson(pkg.path, pkg.data);
  return { action: 'added' };
}

function buildCiCommand(scripts: Record<string, string>): string {
  const present = CI_CANDIDATES.filter((name) => scripts[name] !== undefined);
  return present.map((name) => `npm run ${name}`).join(' && ');
}

export function addCiScript(cwd: string): ScriptResult {
  const pkg = readPackageJson(cwd);
  if (pkg === null) return { action: 'no-package-json' };
  const scripts = ensureScripts(pkg.data);
  const desired = buildCiCommand(scripts);
  const existing = scripts[CI_SCRIPT];
  if (existing === desired) return { action: 'kept', before: existing };
  if (existing !== undefined) return { action: 'conflict', before: existing };
  scripts[CI_SCRIPT] = desired;
  writePackageJson(pkg.path, pkg.data);
  return { action: 'added' };
}
