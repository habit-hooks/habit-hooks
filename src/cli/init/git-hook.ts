import { chmodSync, existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { detectPackageManager, runScriptCommand } from './install-commands.js';

export type HookAction = 'installed' | 'conflict' | 'no-git' | 'kept';

export interface HookResult {
  action: HookAction;
  path?: string;
}

function hookBodyFor(cwd: string): string {
  const command = runScriptCommand(detectPackageManager(cwd), 'habit-hooks');
  return `#!/usr/bin/env sh\n${command}\n`;
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

function writeHook(path: string, body: string): HookResult {
  writeFileSync(path, body);
  chmodSync(path, 0o755);
  return { action: 'installed', path };
}

function bodyMatches(content: string): boolean {
  return content.includes(' run habit-hooks');
}

function installAt(path: string, body: string): HookResult {
  if (existsSync(path)) {
    const existing = readFileSync(path, 'utf8');
    if (bodyMatches(existing)) return { action: 'kept', path };
    return { action: 'conflict', path };
  }
  return writeHook(path, body);
}

export function installPreCommitHook(cwd: string): HookResult {
  const body = hookBodyFor(cwd);
  if (dependsOnHusky(cwd)) return installAt(huskyHookPath(cwd), body);
  if (!existsSync(join(cwd, '.git'))) return { action: 'no-git' };
  return installAt(nativeHookPath(cwd), body);
}
