import { isAbsolute, join } from 'node:path';
import type { ShellResult } from './shell.js';
import type { CheckOutcome } from '../types.js';

export interface BinResolution {
  binPath: string;
  isFallback: boolean;
}

export function fallbackNotice(tool: string, cwd: string): string {
  return `habit-hooks: using bundled ${tool} (no ${tool} installation found in ${cwd})`;
}

export function spawnFailureWarning(tool: string, cwd: string, warnings: string[]): string {
  const detail = warnings.length > 0 ? warnings.join('; ') : 'spawn failure';
  return `habit-hooks: ${tool} skipped in ${cwd} (${detail})`;
}

export function firstLine(text: string): string {
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.length > 0) return trimmed;
  }
  return '';
}

export function isSpawnFailure(result: ShellResult): boolean {
  return result.exitCode === -1;
}

export function emptyOutcome(stderr: string[]): CheckOutcome {
  return { violations: [], stderr };
}

// A run-wide collector for sensor diagnostics. `notices` is shown to the user;
// `failures` records sensors that could not run (spawn/timeout) and fails the
// run (exit 1), per docs/sensors.md.
export interface SensorSink {
  notices: string[];
  failures: string[];
}

// A sensor that could not spawn or timed out: the message is shown (stderr) and
// recorded as a failure so the run fails (exit 1), per docs/sensors.md.
export function spawnFailureOutcome(notices: string[], message: string): CheckOutcome {
  return { violations: [], stderr: [...notices, message], failures: [message] };
}

export function recordSpawnFailure(sink: SensorSink, message: string): void {
  sink.notices.push(message);
  sink.failures.push(message);
}

export function noticesFor(tool: string, resolution: BinResolution, cwd: string): string[] {
  return resolution.isFallback ? [fallbackNotice(tool, cwd)] : [];
}

export function absolutize(cwd: string, file: string): string {
  return isAbsolute(file) ? file : join(cwd, file);
}
