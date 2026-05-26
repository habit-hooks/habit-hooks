import { afterEach, describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { eslintCheck, resetTsProbeCache } from './eslint-check.js';
import { getRules } from '../rules/registry.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(here, '..', '..', 'tests', 'fixtures');

describe('eslintCheck', () => {
  it('flags a max-params violation in a fixture file', async () => {
    const file = join(fixturesDir, 'max-params.ts');
    const violations = await eslintCheck.run([file], getRules());
    const maxParams = violations.filter((v) => v.ruleId === 'eslint:max-params');
    expect(maxParams.length).toBe(1);
    expect(maxParams[0]?.file).toBe(file);
    expect(maxParams[0]?.line).toBe(1);
  });

  it('returns no violations for a clean fixture', async () => {
    const file = join(fixturesDir, 'clean.ts');
    const violations = await eslintCheck.run([file], getRules());
    expect(violations).toEqual([]);
  });

  it('returns empty when no files supplied', async () => {
    const violations = await eslintCheck.run([], getRules());
    expect(violations).toEqual([]);
  });
});

describe('eslintCheck TS plugin probe', () => {
  let tmpDir: string;

  afterEach(() => {
    if (tmpDir) rmSync(tmpDir, { recursive: true, force: true });
    resetTsProbeCache();
  });

  it('skips @typescript-eslint rules when the plugin is not resolvable from cwd', async () => {
    tmpDir = mkdtempSync(join(tmpdir(), 'hh-noplugin-'));
    const file = join(tmpDir, 'sample.ts');
    writeFileSync(file, 'export const x: any = 1;\n');
    const rules = getRules().filter(
      (r) => r.id === 'eslint:@typescript-eslint/no-explicit-any',
    );
    const violations = await eslintCheck.run([file], rules, tmpDir);
    expect(violations).toEqual([]);
  });

  it('uses the @typescript-eslint variant of no-unused-vars when plugin resolvable', async () => {
    const file = join(fixturesDir, 'sample-project', 'src', 'unused-vars.ts');
    const rules = getRules().filter((r) => r.id === 'eslint:no-unused-vars');
    const violations = await eslintCheck.run([file], rules, process.cwd());
    expect(violations.length).toBe(1);
    expect(violations[0]?.ruleId).toBe('eslint:no-unused-vars');
  });
});
