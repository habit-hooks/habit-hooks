import { afterEach, describe, expect, it } from 'vitest';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { run } from './runner.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = join(here, '..', 'tests', 'fixtures');
const RUFF = spawnSync('ruff', ['--version']).status === 0;

const CLEAN_BANNER = '✅ Habit Hooks: automated checks passed.';

describe('CLI output — clean-run banner + violation-run output', () => {
  let dir = '';
  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
    dir = '';
  });

  it('typescript clean run prints the pass banner and the review reminder (exit 0)', async () => {
    const result = await run(join(fixtures, 'clean-project'));
    expect(result.exitCode).toBe(0);
    expect(result.stdout.startsWith(CLEAN_BANNER)).toBe(true);
    expect(result.stdout).toContain('not correctness or design');
    expect(result.stdout).toContain('reviewer sub-agent');
  });

  it('typescript violation run prints the count header and a coached section (exit 1)', async () => {
    const result = await run(join(fixtures, 'sample-project'));
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toMatch(/^❌ Habit Hooks: \d+ violations/);
    expect(result.stdout).toContain('❌ Too many parameters');
    expect(result.stdout).toContain('Violations:');
  });

  it.skipIf(!RUFF)('python clean run prints the pass banner (exit 0)', async () => {
    dir = mkdtempSync(join(tmpdir(), 'hh-pyclean-'));
    writeFileSync(join(dir, 'habit-hooks.config.json'), JSON.stringify({ language: 'python' }));
    writeFileSync(join(dir, 'ok.py'), 'def add(a, b):\n    return a + b\n');

    const result = await run(dir);

    expect(result.exitCode).toBe(0);
    expect(result.stdout.startsWith(CLEAN_BANNER)).toBe(true);
  });

  it.skipIf(!RUFF)('python violation run prints the count header and a coached section (exit 1)', async () => {
    const result = await run(join(fixtures, 'python-project'));
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toMatch(/^❌ Habit Hooks: \d+ violations/);
    expect(result.stdout).toContain('❌ Too many parameters');
  });
});
