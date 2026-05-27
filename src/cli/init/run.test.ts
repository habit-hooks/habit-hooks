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

function readScripts(cwd: string): Record<string, string> | undefined {
  const pkg = JSON.parse(readFileSync(join(cwd, 'package.json'), 'utf8')) as {
    scripts?: Record<string, string>;
  };
  return pkg.scripts;
}

describe('runInit', () => {
  let s: Setup;

  beforeEach(() => {
    s = makeSetup();
  });
  afterEach(() => {
    rmSync(s.cwd, { recursive: true, force: true });
  });

  it('scaffolds tool configs, habit-hooks config, and baseline on a fresh dir', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(existsSync(join(s.cwd, 'eslint.config.js'))).toBe(true);
    expect(existsSync(join(s.cwd, 'knip.json'))).toBe(true);
    expect(existsSync(join(s.cwd, '.jscpd.json'))).toBe(true);
    expect(existsSync(join(s.cwd, 'habit-hooks.config.js'))).toBe(true);
    expect(existsSync(join(s.cwd, '.habit-hooks-baseline.json'))).toBe(true);
  });

  it('writes a slim v2 habit-hooks config with scope only', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    const contents = readFileSync(join(s.cwd, 'habit-hooks.config.js'), 'utf8');
    expect(contents).toContain('scope');
    expect(contents).toContain('branchBase');
    expect(contents).not.toContain('rules');
    expect(contents).not.toContain('sourceOptions');
    expect(contents).not.toContain('severity');
  });

  it('does not overwrite an existing habit-hooks config and keeps going', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'habit-hooks.config.js'), 'export default {};\n');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('habit-hooks config already present');
    expect(readFileSync(join(s.cwd, 'habit-hooks.config.js'), 'utf8')).toBe('export default {};\n');
  });

  it('does not overwrite an existing eslint config', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'eslint.config.js'), '// existing\n');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(readFileSync(join(s.cwd, 'eslint.config.js'), 'utf8')).toBe('// existing\n');
    expect(result.stdout).toContain('eslint config already present (binary missing)');
  });

  it('prints an install command for tools missing from node_modules', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('To install missing tools, run:');
    expect(result.stdout).toContain('npm install --save-dev');
    expect(result.stdout).toContain('eslint');
    expect(result.stdout).toContain('knip');
    expect(result.stdout).toContain('jscpd');
  });

  it('picks pnpm when pnpm-lock.yaml is present', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'pnpm-lock.yaml'), '');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('pnpm add -D');
  });

  it('omits a tool from the install command when its bin is in node_modules', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const binDir = join(s.cwd, 'node_modules', '.bin');
    mkdirSync(binDir, { recursive: true });
    writeFileSync(join(binDir, 'eslint'), '#!/usr/bin/env node\n');
    const pkgDir = join(s.cwd, 'node_modules', 'eslint');
    mkdirSync(pkgDir, { recursive: true });
    writeFileSync(join(pkgDir, 'package.json'), JSON.stringify({ name: 'eslint' }));
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    const tail = result.stdout.split('To install missing tools, run:')[1] ?? '';
    expect(tail).not.toContain('eslint');
    expect(tail).toContain('knip');
  });

  it('--yes adds habit-hooks script to package.json', async () => {
    writePackageJson(s.cwd, { name: 'demo', scripts: { lint: 'eslint .' } });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(0);
    expect(readScripts(s.cwd)?.['habit-hooks']).toBe('habit-hooks');
  });

  it('refuses to replace a conflicting habit-hooks script (exit 2)', async () => {
    writePackageJson(s.cwd, {
      name: 'demo',
      scripts: { 'habit-hooks': 'echo something else' },
    });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(2);
    expect(result.stderr).toContain("refusing to replace 'habit-hooks'");
    expect(readScripts(s.cwd)?.['habit-hooks']).toBe('echo something else');
  });

  it('--yes wires ci to existing lint/test/build only', async () => {
    writePackageJson(s.cwd, {
      name: 'demo',
      scripts: { lint: 'eslint .', test: 'vitest run' },
    });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(result.exitCode).toBe(0);
    expect(readScripts(s.cwd)?.ci).toBe('npm run lint && npm run test && npm run habit-hooks');
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
    const scripts = readScripts(s.cwd);
    expect(scripts?.['habit-hooks']).toBe('habit-hooks');
    expect(scripts?.ci).toBe('npm run habit-hooks');
    expect(existsSync(join(s.cwd, '.git', 'hooks', 'pre-commit'))).toBe(false);
  });

  it('emits the agent snippet on stdout', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('## Habit Hooks');
    expect(result.stdout).toContain('npm run ci');
    expect(result.stdout).toContain('habit-hooks-review');
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

  it('--dry-run does not write any files', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false), dryRun: true });
    expect(result.exitCode).toBe(0);
    expect(existsSync(join(s.cwd, 'eslint.config.js'))).toBe(false);
    expect(existsSync(join(s.cwd, 'knip.json'))).toBe(false);
    expect(existsSync(join(s.cwd, '.jscpd.json'))).toBe(false);
    expect(existsSync(join(s.cwd, 'habit-hooks.config.js'))).toBe(false);
    expect(existsSync(join(s.cwd, '.habit-hooks-baseline.json'))).toBe(false);
    expect(result.stdout).toContain('[dry-run] would write');
  });

  it('--dry-run still prints the install command', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false), dryRun: true });
    expect(result.stdout).toContain('To install missing tools, run:');
  });

  it('--dry-run leaves an existing package.json byte-identical', async () => {
    writePackageJson(s.cwd, { name: 'demo', scripts: { lint: 'eslint .' } });
    const before = readFileSync(join(s.cwd, 'package.json'), 'utf8');
    await runInit(s.cwd, { prompter: makeAutoPrompter(true), dryRun: true });
    const after = readFileSync(join(s.cwd, 'package.json'), 'utf8');
    expect(after).toBe(before);
  });

  it('prints a starter note when knip.json is freshly scaffolded', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).toContain('knip.json written with starter entry points');
  });

  it('does not print the knip starter note when knip.json already exists', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'knip.json'), '{"entry":["custom.ts"]}');
    const result = await runInit(s.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.stdout).not.toContain('knip.json written with starter entry points');
  });

  it('writes the pre-commit hook with pnpm when pnpm-lock.yaml exists', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'pnpm-lock.yaml'), '');
    mkdirSync(join(s.cwd, '.git', 'hooks'), { recursive: true });
    await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    const body = readFileSync(join(s.cwd, '.git', 'hooks', 'pre-commit'), 'utf8');
    expect(body).toContain('pnpm run habit-hooks');
  });

  it('writes the pre-commit hook with yarn when yarn.lock exists', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    writeFileSync(join(s.cwd, 'yarn.lock'), '');
    mkdirSync(join(s.cwd, '.git', 'hooks'), { recursive: true });
    await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    const body = readFileSync(join(s.cwd, '.git', 'hooks', 'pre-commit'), 'utf8');
    expect(body).toContain('yarn run habit-hooks');
  });

  it('writes the pre-commit hook with npm when no lockfile is present', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    mkdirSync(join(s.cwd, '.git', 'hooks'), { recursive: true });
    await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    const body = readFileSync(join(s.cwd, '.git', 'hooks', 'pre-commit'), 'utf8');
    expect(body).toContain('npm run habit-hooks');
  });

  it('re-running on a scaffolded dir leaves files untouched', async () => {
    writePackageJson(s.cwd, { name: 'demo' });
    await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    const first = readFileSync(join(s.cwd, 'eslint.config.js'), 'utf8');
    const second = await runInit(s.cwd, { prompter: makeAutoPrompter(true) });
    expect(second.exitCode).toBe(0);
    expect(readFileSync(join(s.cwd, 'eslint.config.js'), 'utf8')).toBe(first);
    expect(second.stdout).toContain('eslint config already present');
    expect(second.stdout).toContain('habit-hooks config already present');
  });
});
