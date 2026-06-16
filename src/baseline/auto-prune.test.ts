import { afterEach, describe, expect, it } from 'vitest';
import { rmSync } from 'node:fs';
import { runWithAutoPrune } from './auto-prune.js';
import { loadBaseline, saveBaseline } from './store.js';
import { lastCommitHash } from './file-hash.js';
import { createGitRepo, type GitRepo } from '../../tests/helpers/git.js';

const DIRTY_FN = `export function tooMany(a: number, b: number, c: number, d: number): number {
  return a + b + c + d;
}
`;
const CLEAN_FN = `export function add(a: number, b: number): number {
  return a + b;
}
`;

function snooze(repo: GitRepo, file: string): void {
  saveBaseline(repo.cwd, {
    version: 2,
    files: { [file]: { snoozedAtCommit: lastCommitHash(repo.cwd, file) ?? '' } },
  });
}

describe('runWithAutoPrune', () => {
  let repo: GitRepo;

  afterEach(() => {
    if (repo) rmSync(repo.cwd, { recursive: true, force: true });
  });

  it('prunes a now-clean baselined file on a full-repo run and reports it', async () => {
    repo = createGitRepo({ withEslint: true });
    repo.writeFile('bad.ts', DIRTY_FN);
    repo.commitAll('add bad');
    snooze(repo, 'bad.ts');
    repo.writeFile('bad.ts', CLEAN_FN);
    repo.commitAll('fix bad');

    const result = await runWithAutoPrune(repo.cwd, { scopeFlags: { all: true } });

    expect(loadBaseline(repo.cwd).files['bad.ts']).toBeUndefined();
    expect(result.stdout).toContain('Auto-pruned');
    expect(result.stdout).toContain('bad.ts');
  });

  it('keeps a still-violating baselined file on a full-repo run', async () => {
    repo = createGitRepo({ withEslint: true });
    repo.writeFile('bad.ts', DIRTY_FN);
    repo.commitAll('add bad');
    snooze(repo, 'bad.ts');

    await runWithAutoPrune(repo.cwd, { scopeFlags: { all: true } });

    expect(loadBaseline(repo.cwd).files['bad.ts']).toBeDefined();
  });

  it('never mutates the baseline on a scoped run, even when the snoozed file is now clean', async () => {
    repo = createGitRepo({ withEslint: true });
    repo.writeFile('bad.ts', DIRTY_FN);
    repo.commitAll('add bad');
    snooze(repo, 'bad.ts');
    repo.writeFile('bad.ts', CLEAN_FN);
    repo.commitAll('fix bad');

    await runWithAutoPrune(repo.cwd, { scopeFlags: { last: 1 } });

    expect(loadBaseline(repo.cwd).files['bad.ts']).toBeDefined();
  });
});
