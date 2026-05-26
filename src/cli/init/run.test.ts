import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runInit } from './run.js';
import { makeAutoPrompter } from './prompts.js';

interface Setup {
  cwd: string;
}

function makeSetup(): Setup {
  return { cwd: mkdtempSync(join(tmpdir(), 'hh-init-')) };
}

function writePackageJson(cwd: string, data: Record<string, unknown>): void {
  writeFileSync(join(cwd, 'package.json'), JSON.stringify(data, null, 2));
}

describe('runInit', () => {
  let s: Setup;

  beforeEach(() => {
    s = makeSetup();
  });
  afterEach(() => {
    rmSync(s.cwd, { recursive: true, force: true });
  });

  it('writes config and baseline on a fresh dir', async () => {
    writePackageJson(s.cwd, { name: 'demo', scripts: { lint: 'eslint .' } });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(existsSync(join(s.cwd, 'habit-hooks.config.ts'))).toBe(true);
    expect(existsSync(join(s.cwd, '.habit-hooks-baseline.json'))).toBe(true);
  });

  it('refuses to overwrite an existing config (exit 2, no baseline written)', async () => {
    writeFileSync(join(s.cwd, 'habit-hooks.config.ts'), 'export default {};\n');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain('refusing to overwrite');
    expect(existsSync(join(s.cwd, '.habit-hooks-baseline.json'))).toBe(false);
  });

  it('--yes adds habit-hooks script to package.json', async () => {
    writePackageJson(s.cwd, { name: 'demo', scripts: { lint: 'eslint .' } });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(0);
    const pkg = JSON.parse(readFileSync(join(s.cwd, 'package.json'), 'utf8')) as {
      scripts: Record<string, string>;
    };
    expect(pkg.scripts['habit-hooks']).toBe('habit-hooks');
  });

  it('refuses to replace a conflicting habit-hooks script (exit 2)', async () => {
    writePackageJson(s.cwd, {
      name: 'demo',
      scripts: { 'habit-hooks': 'echo something else' },
    });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain("refusing to replace 'habit-hooks'");
    const pkg = JSON.parse(readFileSync(join(s.cwd, 'package.json'), 'utf8')) as {
      scripts: Record<string, string>;
    };
    expect(pkg.scripts['habit-hooks']).toBe('echo something else');
  });

  it('--yes wires ci to existing lint/test/build only', async () => {
    writePackageJson(s.cwd, {
      name: 'demo',
      scripts: { lint: 'eslint .', test: 'vitest run' },
    });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(0);
    const pkg = JSON.parse(readFileSync(join(s.cwd, 'package.json'), 'utf8')) as {
      scripts: Record<string, string>;
    };
    expect(pkg.scripts.ci).toBe('npm run lint && npm run test && npm run habit-hooks');
  });

  it('refuses to replace a conflicting ci script', async () => {
    writePackageJson(s.cwd, {
      name: 'demo',
      scripts: { lint: 'eslint .', ci: 'something custom' },
    });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain("refusing to replace 'ci'");
  });

  it('takes per-prompt defaults: Y for safe additions, N for destructive ones', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    const pkg = JSON.parse(readFileSync(join(s.cwd, 'package.json'), 'utf8')) as {
      scripts?: Record<string, string>;
    };
    expect(pkg.scripts?.['habit-hooks']).toBe('habit-hooks');
    expect(pkg.scripts?.ci).toBe('npm run habit-hooks');
    expect(existsSync(join(s.cwd, '.git', 'hooks', 'pre-commit'))).toBe(false);
  });

  it('emits the agent snippet on stdout', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('## Habit Hooks');
    expect(result.stdout).toContain('npm run ci');
    expect(result.stdout).toContain('habit-hooks-review');
  });

  it('warns when jscpd or knip are missing from node_modules', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('jscpd and knip not installed');
  });

  it('--yes installs a pre-commit hook when .git exists', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    mkdirSync(join(s.cwd, '.git', 'hooks'), { recursive: true });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    const hookPath = join(s.cwd, '.git', 'hooks', 'pre-commit');
    expect(result.exitCode).toBe(0);
    expect(existsSync(hookPath)).toBe(true);
    expect(readFileSync(hookPath, 'utf8')).toContain('npm run habit-hooks');
  });

  it('refuses to overwrite an existing pre-commit hook', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    mkdirSync(join(s.cwd, '.git', 'hooks'), { recursive: true });
    const hookPath = join(s.cwd, '.git', 'hooks', 'pre-commit');
    writeFileSync(hookPath, '#!/bin/sh\necho something\n');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('left untouched');
    expect(readFileSync(hookPath, 'utf8')).toBe('#!/bin/sh\necho something\n');
  });
});
