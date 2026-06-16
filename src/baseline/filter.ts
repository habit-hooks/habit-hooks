import { relative, sep } from 'node:path';
import type { SnoozeIndex } from './snooze-index.js';
import type { BaselineFile } from './store.js';

export function toRepoRelative(cwd: string, absPath: string): string {
  return relative(cwd, absPath).split(sep).join('/');
}

interface SnoozePartition {
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
  index: SnoozeIndex,
): SnoozePartition {
  const partition: SnoozePartition = { active: [], skipped: [] };
  for (const abs of files) {
    assignToPartition(partition, abs, index.isSnoozed(abs, baseline));
  }
  return partition;
}
