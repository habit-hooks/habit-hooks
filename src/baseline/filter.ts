import { relative, sep } from 'node:path';
import { isWorkingTreeCleanFor, lastCommitHash } from './file-hash.js';
import type { BaselineFile } from './store.js';

export function toRepoRelative(cwd: string, absPath: string): string {
  return relative(cwd, absPath).split(sep).join('/');
}

function isSnoozed(relPath: string, baseline: BaselineFile, cwd: string): boolean {
  const entry = baseline.files[relPath];
  if (entry === undefined) return false;
  const currentHash = lastCommitHash(cwd, relPath);
  if (currentHash === null) return false;
  if (currentHash !== entry.snoozedAt) return false;
  return isWorkingTreeCleanFor(cwd, relPath);
}

export interface SnoozePartition {
  active: string[];
  skipped: string[];
}

function assignToPartition(
  partition: SnoozePartition,
  abs: string,
  snoozed: boolean,
): void {
  if (snoozed) partition.skipped.push(abs);
  else partition.active.push(abs);
}

export function partitionBySnooze(
  files: string[],
  baseline: BaselineFile,
  cwd: string,
): SnoozePartition {
  const partition: SnoozePartition = { active: [], skipped: [] };
  for (const abs of files) {
    const rel = toRepoRelative(cwd, abs);
    assignToPartition(partition, abs, isSnoozed(rel, baseline, cwd));
  }
  return partition;
}
