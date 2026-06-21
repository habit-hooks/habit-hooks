import { run, type RunOptions, type RunResult } from '../runner.js';
import { loadBaseline, saveBaseline, BASELINE_VERSION } from './store.js';
import { toRepoRelative } from './filter.js';
import { reapBaseline } from './reap.js';

// Auto-prune reaps baseline entries whose smell is actually fixed. It runs a
// baseline-free full scan so a sensor gated off by the baseline can't make a
// snoozed file look falsely clean, then shares the reaper with `baseline prune`.
// configPath must match the one used for the main run so the re-scan sees the
// same rules — using a different (or default-discovered) config could wrongly
// mark a still-snoozed file as clean and prune it.
async function autoPruneFullRepo(cwd: string, configPath?: string): Promise<string[]> {
  const baseline = loadBaseline(cwd);
  if (Object.keys(baseline.files).length === 0) return [];
  const scan = await run(cwd, { configPath, scopeFlags: { all: true }, applyBaseline: false });
  const violating = new Set(scan.violations.map((v) => toRepoRelative(cwd, v.file)));
  const { files, pruned } = reapBaseline(cwd, baseline, violating);
  if (pruned.length > 0) saveBaseline(cwd, { version: BASELINE_VERSION, files });
  return pruned;
}

function autoPruneNotice(pruned: string[]): string {
  const entries = pruned.length === 1 ? 'entry' : 'entries';
  return `🧹 Auto-pruned ${String(pruned.length)} fixed baseline ${entries}: ${pruned.join(', ')}\n`;
}

// run() is a pure evaluator; auto-prune is the one side effect a full-repo run
// performs. A scoped run never mutates the baseline (a file can look clean only
// because its smell is outside the diff), so it is a guaranteed no-op.
export async function runWithAutoPrune(cwd: string, options: RunOptions): Promise<RunResult> {
  const result = await run(cwd, options);
  if (result.scopeMode !== 'all') return result;
  const pruned = await autoPruneFullRepo(cwd, options.configPath);
  if (pruned.length === 0) return result;
  return { ...result, stdout: result.stdout + autoPruneNotice(pruned) };
}
