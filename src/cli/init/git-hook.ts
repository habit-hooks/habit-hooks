import { chmodSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const HOOK_BODY = `#!/usr/bin/env sh
npm run habit-hooks
`;

export type HookAction = 'installed' | 'conflict' | 'no-git' | 'kept';

export interface HookResult {
  action: HookAction;
  path?: string;
}

function dependsOnHusky(cwd: string): boolean {
  const pkgPath = join(cwd, 'package.json');
  if (!existsSync(pkgPath)) return false;
  if (!existsSync(join(cwd, '.husky'))) return false;
  const raw = readFileSync(pkgPath, 'utf8');
  return raw.includes('"husky"');
}

function huskyHookPath(cwd: string): string {
  return join(cwd, '.husky', 'pre-commit');
}

function nativeHookPath(cwd: string): string {
  return join(cwd, '.git', 'hooks', 'pre-commit');
}

function writeHook(path: string): HookResult {
  writeFileSync(path, HOOK_BODY);
  chmodSync(path, 0o755);
  return { action: 'installed', path };
}

function installAt(path: string, existingContentMatches: (s: string) => boolean): HookResult {
  if (existsSync(path)) {
    const existing = readFileSync(path, 'utf8');
    if (existingContentMatches(existing)) return { action: 'kept', path };
    return { action: 'conflict', path };
  }
  return writeHook(path);
}

function bodyMatches(content: string): boolean {
  return content.includes('npm run habit-hooks');
}

export function installPreCommitHook(cwd: string): HookResult {
  if (dependsOnHusky(cwd)) {
    return installAt(huskyHookPath(cwd), bodyMatches);
  }
  if (!existsSync(join(cwd, '.git'))) return { action: 'no-git' };
  return installAt(nativeHookPath(cwd), bodyMatches);
}
