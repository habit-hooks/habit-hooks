import { gitExec, GitError } from '../git/exec.js';
import { lastCommitHash } from './file-hash.js';
import { toRepoRelative } from './filter.js';
import type { BaselineFile } from './store.js';

// A per-run cache of the git queries the snooze check needs. The whole-tree
// dirty set comes from one `git status` (not one spawn per file), and
// last-commit hashes are memoized, collapsing the old O(rules x baseline-files)
// git spawns to O(1) status + O(baseline-files) log calls per run.
export interface SnoozeIndex {
  isSnoozed(_absPath: string, _baseline: BaselineFile): boolean;
}

// `git status --porcelain -z` record: `XY <path>`, NUL-separated, no path
// quoting. A rename/copy record is followed by an extra field for the original
// path; both sides count as dirty. Returns the index of the last field consumed.
function parseDirtyRecord(records: string[], i: number, dirty: Set<string>): number {
  const record = records[i];
  if (record.length < 4) return i;
  dirty.add(record.slice(3));
  if (!/[RC]/.test(record.slice(0, 2))) return i;
  if (records[i + 1]) dirty.add(records[i + 1]);
  return i + 1;
}

function computeDirtySet(cwd: string): Set<string> | null {
  let records: string[];
  try {
    records = gitExec(['status', '--porcelain', '-z'], cwd).split('\0');
  } catch (err) {
    if (err instanceof GitError) return null;
    throw err;
  }
  const dirty = new Set<string>();
  for (let i = 0; i < records.length; i += 1) i = parseDirtyRecord(records, i, dirty);
  return dirty;
}

class GitSnoozeIndex implements SnoozeIndex {
  private readonly cwd: string;
  private readonly hashes = new Map<string, string | null>();
  private dirty: Set<string> | null | undefined;

  constructor(cwd: string) {
    this.cwd = cwd;
  }

  private hashFor(rel: string): string | null {
    if (!this.hashes.has(rel)) this.hashes.set(rel, lastCommitHash(this.cwd, rel));
    return this.hashes.get(rel) ?? null;
  }

  private isClean(rel: string): boolean {
    if (this.dirty === undefined) this.dirty = computeDirtySet(this.cwd);
    return this.dirty !== null && !this.dirty.has(rel);
  }

  isSnoozed(absPath: string, baseline: BaselineFile): boolean {
    const rel = toRepoRelative(this.cwd, absPath);
    const entry = baseline.files[rel];
    if (entry === undefined) return false;
    if (this.hashFor(rel) !== entry.snoozedAtCommit) return false;
    return this.isClean(rel);
  }
}

export function createSnoozeIndex(cwd: string): SnoozeIndex {
  return new GitSnoozeIndex(cwd);
}
