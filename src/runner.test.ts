import { afterEach, describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { run } from './runner.js';
import { SENSORS_FALLBACK_DEPRECATION } from './config/load.js';
import { lastCommitHash } from './baseline/file-hash.js';
import { saveBaseline } from './baseline/store.js';
import { createGitRepo, type GitRepo } from '../tests/helpers/git.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(here, '..', 'tests', 'fixtures');

const DIRTY_FN = `export function tooMany(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
`;
const CLEAN_FN = `export function add(a: number, b: number): number {
  return a + b;
}
`;

describe('runner.run', () => {
  it('returns exit 1 and grouped output for a project with violations', async () => {
    const result = await run(join(fixturesDir, 'dirty-project'));
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Habit Hooks: 1 violation');
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('bad.ts:1');
  });

  it('returns exit 0 and clean header for a clean project', async () => {
    const result = await run(join(fixturesDir, 'clean-project'));
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Habit Hooks: automated checks passed.');
  });

  it('respects per-rule exclude: test files do not trip max-lines-per-function', async () => {
    const result = await run(join(fixturesDir, 'configured-project'));
    expect(result.stdout).not.toContain('Function too long');
  });

  it('applies project config: disables complexity, uses custom prompt for max-params', async () => {
    const result = await run(join(fixturesDir, 'configured-project'));
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('CUSTOM PROJECT GUIDANCE');
    expect(result.stdout).not.toContain('Function complexity is high');
  });
});

describe('runner.run sensor gating', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  const LONG_COMMENT = 'const x = 1;\n// this comment is long enough to be flagged\nexport const y = x;\n';

  it('fires non-essential-comment by default (control)', async () => {
    dir = mkdtempSync(join(tmpdir(), 'hh-gate-'));
    writeFileSync(join(dir, 'a.ts'), LONG_COMMENT);

    const result = await run(dir);

    expect(result.violations.some((v) => v.ruleId === 'non-essential-comment')).toBe(true);
  });

  it('exits 1 for an enforced smell that has no dedicated prompt template', async () => {
    dir = mkdtempSync(join(tmpdir(), 'hh-gate-'));
    symlinkSync(join(here, '..', 'node_modules'), join(dir, 'node_modules'), 'dir');
    writeFileSync(join(dir, 'eslint.config.mjs'), 'export default [{ rules: { eqeqeq: "error" } }];\n');
    writeFileSync(join(dir, 'a.js'), 'export const x = 1 == 1;\n');

    const result = await run(dir);

    expect(result.violations.some((v) => v.ruleId === 'loose-equality')).toBe(true);
    expect(result.exitCode).toBe(1);
  }, 30_000);

  it('suppresses a non-eslint sensor entirely when its smell is disabled', async () => {
    dir = mkdtempSync(join(tmpdir(), 'hh-gate-'));
    writeFileSync(join(dir, 'a.ts'), LONG_COMMENT);
    writeFileSync(
      join(dir, 'habit-hooks.config.json'),
      JSON.stringify({ smells: { 'non-essential-comment': { disabled: true } } }),
    );

    const result = await run(dir);

    expect(result.violations.some((v) => v.ruleId === 'non-essential-comment')).toBe(false);
  });
});

describe('runner.run with configured sensors', () => {
  it('runs only the consumer custom sensor, with no built-in sensors', async () => {
    const result = await run(join(fixturesDir, 'custom-sensor-project'));

    expect(result.violations.some((v) => v.ruleId === 'custom-marker' && v.file.endsWith('app.ts'))).toBe(true);
    expect(result.exitCode).toBe(1);
    expect(result.violations.some((v) => v.ruleId === 'too-many-parameters')).toBe(false);
    expect(result.violations.some((v) => v.ruleId === 'non-essential-comment')).toBe(false);
    expect(result.stderr).not.toContain(SENSORS_FALLBACK_DEPRECATION);
  });

  it('warns on stderr when no sensors block is configured (preset fallback)', async () => {
    const result = await run(join(fixturesDir, 'dirty-project'));

    expect(result.stderr.join('\n')).toContain(SENSORS_FALLBACK_DEPRECATION);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Too many parameters');
  });
});

describe('runner.run with scope', () => {
  let repo: GitRepo;

  afterEach(() => {
    if (repo) rmSync(repo.cwd, { recursive: true, force: true });
  });

  function writeConfig(cwd: string, changedFilesOnly: boolean): void {
    const cfg = {
      smells: {
        'too-many-parameters': { changedFilesOnly },
        'oversized-function': { disabled: true },
      },
    };
    writeFileSync(join(cwd, 'habit-hooks.config.json'), JSON.stringify(cfg));
  }

  it('changedFilesOnly rule limited to last-commit files with --last 1', async () => {
    repo = createGitRepo({ withEslint: true });
    writeConfig(repo.cwd, true);
    repo.writeFile('old-bad.ts', DIRTY_FN);
    repo.commitAll('old');
    repo.writeFile('new-bad.ts', DIRTY_FN);
    repo.commitAll('new');

    const result = await run(repo.cwd, { scopeFlags: { last: 1 } });

    expect(result.stdout).toContain('Habit Hooks: 1 violation');
    expect(result.stdout).toContain('new-bad.ts');
    expect(result.stdout).not.toContain('old-bad.ts');
  });

  it('full-scope rule still checks every file under --last 1', async () => {
    repo = createGitRepo({ withEslint: true });
    writeConfig(repo.cwd, false);
    repo.writeFile('old-bad.ts', DIRTY_FN);
    repo.commitAll('old');
    repo.writeFile('clean.ts', CLEAN_FN);
    repo.commitAll('clean');

    const result = await run(repo.cwd, { scopeFlags: { last: 1 } });

    expect(result.stdout).toContain('old-bad.ts');
  });

  it('skips rule entirely when scope produces an empty file list', async () => {
    repo = createGitRepo({ withEslint: true });
    writeConfig(repo.cwd, true);
    repo.writeFile('old-bad.ts', DIRTY_FN);
    repo.commitAll('old');
    repo.writeFile('clean.ts', CLEAN_FN);
    repo.commitAll('only clean changed');

    const result = await run(repo.cwd, { scopeFlags: { last: 1 } });

    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Habit Hooks: automated checks passed.');
  });

  it('--all overrides config.onlyChangedFiles and lints the full set', async () => {
    repo = createGitRepo({ withEslint: true });
    const cfg = {
      scope: { onlyChangedFiles: true },
      smells: {
        'too-many-parameters': { changedFilesOnly: true },
        'oversized-function': { disabled: true },
      },
    };
    writeFileSync(join(repo.cwd, 'habit-hooks.config.json'), JSON.stringify(cfg));
    repo.writeFile('committed-bad.ts', DIRTY_FN);
    repo.commitAll('committed');

    const result = await run(repo.cwd, { scopeFlags: { all: true } });

    expect(result.stdout).toContain('committed-bad.ts');
  });
});

describe('runner.run sensor failure', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  // A directory where the eslint bin is expected forces a spawn failure (EACCES)
  // without depending on the host toolchain.
  function breakEslintBin(cwd: string): void {
    mkdirSync(join(cwd, 'node_modules', '.bin', 'eslint'), { recursive: true });
  }

  it('fails the run (exit 1) on a sensor spawn failure, still rendering other sensors', async () => {
    dir = mkdtempSync(join(tmpdir(), 'hh-sensorfail-'));
    writeFileSync(join(dir, 'eslint.config.js'), 'export default [];\n');
    writeFileSync(join(dir, 'app.ts'), '// a flagged explanatory comment\nexport const a = 1;\n');
    breakEslintBin(dir);

    const result = await run(dir, { applyBaseline: false });

    expect(result.exitCode).toBe(1);
    expect(result.stderr.join('\n')).toContain('eslint');
    expect(result.stdout).toContain('app.ts');
  });
});

describe('runner.run with baseline', () => {
  let repo: GitRepo;

  afterEach(() => {
    if (repo) rmSync(repo.cwd, { recursive: true, force: true });
  });

  function writeMaxParamsConfig(cwd: string): void {
    const cfg = {
      smells: { 'oversized-function': { disabled: true } },
    };
    writeFileSync(join(cwd, 'habit-hooks.config.json'), JSON.stringify(cfg));
  }

  it('skips snoozed clean files entirely', async () => {
    repo = createGitRepo({ withEslint: true });
    writeMaxParamsConfig(repo.cwd);
    repo.writeFile('bad.ts', DIRTY_FN);
    repo.commitAll('add bad');
    const hash = lastCommitHash(repo.cwd, 'bad.ts');
    saveBaseline(repo.cwd, {
      version: 2,
      files: { 'bad.ts': { snoozedAtCommit: hash ?? '' } },
    });

    const result = await run(repo.cwd);

    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Habit Hooks: automated checks passed.');
    expect(result.stdout).not.toContain('bad.ts');
  });

  it('resurfaces violations when a snoozed file is edited (working tree dirty)', async () => {
    repo = createGitRepo({ withEslint: true });
    writeMaxParamsConfig(repo.cwd);
    repo.writeFile('bad.ts', DIRTY_FN);
    repo.commitAll('add bad');
    const hash = lastCommitHash(repo.cwd, 'bad.ts');
    saveBaseline(repo.cwd, {
      version: 2,
      files: { 'bad.ts': { snoozedAtCommit: hash ?? '' } },
    });

    repo.writeFile(
      'bad.ts',
      `${DIRTY_FN}\nexport const trivial = 1;\n`,
    );

    const result = await run(repo.cwd);

    expect(result.stdout).toContain('bad.ts');
    expect(result.exitCode).toBe(1);
  });
});
