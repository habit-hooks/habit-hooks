import { afterEach, describe, expect, it } from 'vitest';
import { rmSync } from 'node:fs';
import { join } from 'node:path';
import { createGitRepo, type GitRepo } from '../../tests/helpers/git.js';
import { lastCommitHash } from './file-hash.js';
import { partitionBySnooze } from './filter.js';
import { createSnoozeIndex } from './snooze-index.js';
import type { BaselineFile } from './store.js';

function baselineWith(files: Record<string, string>): BaselineFile {
  const out: BaselineFile['files'] = {};
  for (const [path, hash] of Object.entries(files)) {
    out[path] = { snoozedAtCommit: hash };
  }
  return { version: 2, files: out };
}

describe('partitionBySnooze (four-quadrant)', () => {
  let repo: GitRepo;

  afterEach(() => {
    if (repo) rmSync(repo.cwd, { recursive: true, force: true });
  });

  it('snoozed + unchanged + clean => skipped', () => {
    repo = createGitRepo();
    repo.writeFile('a.ts', 'export const a = 1;\n');
    repo.commitAll('first');
    const hash = lastCommitHash(repo.cwd, 'a.ts');
    const baseline = baselineWith({ 'a.ts': hash ?? '' });
    const abs = join(repo.cwd, 'a.ts');

    const { active, skipped } = partitionBySnooze([abs], baseline, createSnoozeIndex(repo.cwd));

    expect(skipped).toEqual([abs]);
    expect(active).toEqual([]);
  });

  it('snoozed + unchanged + dirty => active', () => {
    repo = createGitRepo();
    repo.writeFile('a.ts', 'export const a = 1;\n');
    repo.commitAll('first');
    const hash = lastCommitHash(repo.cwd, 'a.ts');
    repo.writeFile('a.ts', 'export const a = 99;\n');
    const baseline = baselineWith({ 'a.ts': hash ?? '' });
    const abs = join(repo.cwd, 'a.ts');

    const { active, skipped } = partitionBySnooze([abs], baseline, createSnoozeIndex(repo.cwd));

    expect(active).toEqual([abs]);
    expect(skipped).toEqual([]);
  });

  it('snoozed + committed-past (hash drifted) => active', () => {
    repo = createGitRepo();
    repo.writeFile('a.ts', 'export const a = 1;\n');
    repo.commitAll('first');
    const oldHash = lastCommitHash(repo.cwd, 'a.ts');
    repo.writeFile('a.ts', 'export const a = 2;\n');
    repo.commitAll('second');
    const baseline = baselineWith({ 'a.ts': oldHash ?? '' });
    const abs = join(repo.cwd, 'a.ts');

    const { active, skipped } = partitionBySnooze([abs], baseline, createSnoozeIndex(repo.cwd));

    expect(active).toEqual([abs]);
    expect(skipped).toEqual([]);
  });

  it('not snoozed => active', () => {
    repo = createGitRepo();
    repo.writeFile('a.ts', 'export const a = 1;\n');
    repo.commitAll('first');
    const baseline = baselineWith({});
    const abs = join(repo.cwd, 'a.ts');

    const { active, skipped } = partitionBySnooze([abs], baseline, createSnoozeIndex(repo.cwd));

    expect(active).toEqual([abs]);
    expect(skipped).toEqual([]);
  });

  it('handles a mix of snoozed/active/missing-entry across many files', () => {
    repo = createGitRepo();
    repo.writeFile('snoozed-clean.ts', 'export const a = 1;\n');
    repo.writeFile('snoozed-dirty.ts', 'export const b = 1;\n');
    repo.writeFile('not-snoozed.ts', 'export const c = 1;\n');
    repo.commitAll('first');
    const cleanHash = lastCommitHash(repo.cwd, 'snoozed-clean.ts');
    const dirtyHash = lastCommitHash(repo.cwd, 'snoozed-dirty.ts');
    repo.writeFile('snoozed-dirty.ts', 'export const b = 99;\n');

    const baseline = baselineWith({
      'snoozed-clean.ts': cleanHash ?? '',
      'snoozed-dirty.ts': dirtyHash ?? '',
    });
    const inputs = [
      join(repo.cwd, 'snoozed-clean.ts'),
      join(repo.cwd, 'snoozed-dirty.ts'),
      join(repo.cwd, 'not-snoozed.ts'),
    ];

    const { active, skipped } = partitionBySnooze(inputs, baseline, createSnoozeIndex(repo.cwd));

    expect(skipped).toEqual([join(repo.cwd, 'snoozed-clean.ts')]);
    expect(active.sort()).toEqual(
      [join(repo.cwd, 'snoozed-dirty.ts'), join(repo.cwd, 'not-snoozed.ts')].sort(),
    );
  });
});
