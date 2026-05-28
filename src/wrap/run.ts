import { runTool, type ShellResult } from './shell.js';
import { isSpawnFailure, spawnFailureWarning, type BinResolution } from './notices.js';
import { spawnTarget } from './resolve.js';

interface SpawnSkip {
  skipWarning: string;
}

export async function spawnWrapped(
  tool: string,
  resolution: BinResolution,
  cwd: string,
  args: string[],
): Promise<ShellResult | SpawnSkip> {
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
