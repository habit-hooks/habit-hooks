import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runInit } from './run.js';
import { makeAutoPrompter } from './prompts.js';

interface E2eDir {
  cwd: string;
}

function makeE2eDir(): E2eDir {
  return { cwd: mkdtempSync(join(tmpdir(), 'habit-hooks-e2e-')) };
}

function writeMinimalPackageJson(cwd: string): void {
  writeFileSync(join(cwd, 'package.json'), JSON.stringify({ name: 'x', version: '0.0.0' }, null, 2));
}

describe('runInit end-to-end on real tmpdirs', () => {
  let d: E2eDir;

  beforeEach(() => {
    d = makeE2eDir();
  });
  afterEach(() => {
    rmSync(d.cwd, { recursive: true, force: true });
  });

  it('dry-run on an empty dir writes nothing and announces planned writes', async () => {
    const result = await runInit(d.cwd, { prompter: makeAutoPrompter(false), dryRun: true });
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain(`[dry-run] would write ${join(d.cwd, 'habit-hooks.config.js')}`);
    expect(result.stdout).toContain(`[dry-run] would write ${join(d.cwd, '.habit-hooks-baseline.json')}`);
    expect(readdirSync(d.cwd)).toEqual([]);
  });

  it('scaffolds all configs on a dir with package.json (prompter answers default)', async () => {
    writeMinimalPackageJson(d.cwd);
    const result = await runInit(d.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(existsSync(join(d.cwd, 'habit-hooks.config.js'))).toBe(true);
    expect(existsSync(join(d.cwd, '.habit-hooks-baseline.json'))).toBe(true);
    expect(existsSync(join(d.cwd, 'eslint.config.js'))).toBe(true);
    expect(existsSync(join(d.cwd, 'knip.json'))).toBe(true);
    expect(existsSync(join(d.cwd, '.jscpd.json'))).toBe(true);
  });

  it('leaves a pre-existing eslint.config.js untouched and still scaffolds knip and jscpd', async () => {
    writeMinimalPackageJson(d.cwd);
    const marker = '// existing-eslint-marker-9f3a\n';
    writeFileSync(join(d.cwd, 'eslint.config.js'), marker);
    const result = await runInit(d.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(readFileSync(join(d.cwd, 'eslint.config.js'), 'utf8')).toBe(marker);
    expect(result.stdout).toContain('eslint config already present');
    expect(existsSync(join(d.cwd, 'knip.json'))).toBe(true);
    expect(existsSync(join(d.cwd, '.jscpd.json'))).toBe(true);
  });

  it('pins current behaviour: legacy .eslintrc.json does not block scaffolding eslint.config.js', async () => {
    // Pins today's gap: TOOL_CONFIG_FILENAMES in src/detect/tool.ts lists only flat-config
    // names, so .eslintrc.json is invisible to detection. Delete this test when that gap closes.
    writeMinimalPackageJson(d.cwd);
    const marker = '{"_marker":"legacy-eslintrc-7b21"}\n';
    writeFileSync(join(d.cwd, '.eslintrc.json'), marker);
    const result = await runInit(d.cwd, { prompter: makeAutoPrompter(false) });
    expect(result.exitCode).toBe(0);
    expect(readFileSync(join(d.cwd, '.eslintrc.json'), 'utf8')).toBe(marker);
    expect(existsSync(join(d.cwd, 'eslint.config.js'))).toBe(true);
  });
});
