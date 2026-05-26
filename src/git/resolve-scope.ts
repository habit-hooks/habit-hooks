import type { ScopeConfig } from '../config/schema.js';
import { isGitRepo } from './exec.js';
import {
  getChangedVsBranch,
  getChangedVsCommit,
  getCurrentBranch,
  getLastNCommitsChanges,
  getUncommittedFiles,
  unionFiles,
} from './scope.js';

export type ScopeMode = 'uncommitted' | 'last' | 'branch' | 'since' | 'all';

export interface ScopeFlags {
  last?: number;
  branch?: string;
  since?: string;
  all?: boolean;
}

export interface ResolvedScope {
  mode: ScopeMode;
  changedFiles: Set<string> | null;
}

const DEFAULT_BRANCH_BASE = 'origin/main';
const DEFAULT_MAIN_BRANCH = 'main';

export class GitScopeError extends Error {}

function allScope(): ResolvedScope {
  return { mode: 'all', changedFiles: null };
}

function toSet(files: string[]): Set<string> {
  return new Set(files);
}

function requireRepo(cwd: string, mode: ScopeMode): void {
  if (!isGitRepo(cwd)) {
    throw new GitScopeError(
      `--${mode} requires a git repository (run inside a git working tree)`,
    );
  }
}

function resolveFromFlags(flags: ScopeFlags, scope: ScopeConfig, cwd: string): ResolvedScope | null {
  if (flags.all === true) return allScope();
  if (flags.last !== undefined) return resolveLastFlag(flags.last, cwd);
  if (flags.since !== undefined) return resolveSinceFlag(flags.since, cwd);
  if (flags.branch !== undefined) return resolveBranchFlag(flags.branch, scope, cwd);
  return null;
}

function resolveLastFlag(n: number, cwd: string): ResolvedScope {
  requireRepo(cwd, 'last');
  const files = unionFiles(getLastNCommitsChanges(cwd, n), getUncommittedFiles(cwd));
  return { mode: 'last', changedFiles: toSet(files) };
}

function resolveSinceFlag(hash: string, cwd: string): ResolvedScope {
  requireRepo(cwd, 'since');
  const files = unionFiles(getChangedVsCommit(cwd, hash), getUncommittedFiles(cwd));
  return { mode: 'since', changedFiles: toSet(files) };
}

function resolveBranchFlag(value: string, scope: ScopeConfig, cwd: string): ResolvedScope {
  requireRepo(cwd, 'branch');
  const base = value !== '' ? value : (scope.branchBase ?? DEFAULT_BRANCH_BASE);
  const files = unionFiles(getChangedVsBranch(cwd, base), getUncommittedFiles(cwd));
  return { mode: 'branch', changedFiles: toSet(files) };
}

function resolveUncommitted(cwd: string): ResolvedScope {
  if (!isGitRepo(cwd)) return allScope();
  return { mode: 'uncommitted', changedFiles: toSet(getUncommittedFiles(cwd)) };
}

function tryGetCurrentBranch(cwd: string): string | null {
  try {
    return getCurrentBranch(cwd);
  } catch {
    return null;
  }
}

function tryGetBranchScope(cwd: string, branchBase: string): ResolvedScope {
  try {
    const files = unionFiles(getChangedVsBranch(cwd, branchBase), getUncommittedFiles(cwd));
    return { mode: 'branch', changedFiles: toSet(files) };
  } catch {
    return allScope();
  }
}

function resolveAutoBranch(scope: ScopeConfig, cwd: string): ResolvedScope | null {
  if (!isGitRepo(cwd)) return allScope();
  const current = tryGetCurrentBranch(cwd);
  if (current === null) return allScope();
  if (current === (scope.mainBranch ?? DEFAULT_MAIN_BRANCH)) return null;
  return tryGetBranchScope(cwd, scope.branchBase ?? DEFAULT_BRANCH_BASE);
}

function resolveFromConfig(scopeCfg: ScopeConfig, cwd: string): ResolvedScope {
  if (scopeCfg.onlyChangedFiles === true) return resolveUncommitted(cwd);
  if (scopeCfg.autoBranchOffMain === true) {
    return resolveAutoBranch(scopeCfg, cwd) ?? allScope();
  }
  return allScope();
}

export function resolveScope(
  flags: ScopeFlags,
  scope: ScopeConfig | undefined,
  cwd: string,
): ResolvedScope {
  const scopeCfg = scope ?? {};
  return resolveFromFlags(flags, scopeCfg, cwd) ?? resolveFromConfig(scopeCfg, cwd);
}
