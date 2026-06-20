import { runTool, type ShellResult } from './shell.js';
import { isSpawnFailure, spawnFailureOutcome, spawnFailureWarning, type BinResolution } from './notices.js';
import { spawnTarget } from './resolve.js';
import type { CheckOutcome } from '../types.js';

export interface SpawnSkip {
  skipWarning: string;
}

// A spawn/timeout skip becomes a failing outcome: shown to the user and recorded
// as a failure so the run fails (exit 1), per docs/sensors.md.
export function skipOutcome(skip: SpawnSkip, notices: string[]): CheckOutcome {
  return spawnFailureOutcome(notices, skip.skipWarning);
}

interface SpawnWrappedArgs {
  tool: string;
  resolution: BinResolution;
  cwd: string;
  args: string[];
}

export async function spawnWrapped(spec: SpawnWrappedArgs): Promise<ShellResult | SpawnSkip> {
  const { tool, resolution, cwd, args } = spec;
  const target = spawnTarget(resolution.binPath, args);
  const result = await runTool({ bin: target.bin, args: target.args, cwd });
  if (isSpawnFailure(result)) return { skipWarning: spawnFailureWarning(tool, cwd, result.warnings) };
  return result;
}

export function isSpawnSkip(value: ShellResult | SpawnSkip): value is SpawnSkip {
  return (value as SpawnSkip).skipWarning !== undefined;
}

export function parseJsonStdout<T>(stdout: string, startsWith: '{' | '['): T | null {
  const trimmed = stdout.trim();
  if (trimmed.length === 0 || !trimmed.startsWith(startsWith)) return null;
  try {
    return JSON.parse(trimmed) as T;
  } catch {
    return null;
  }
}
