import { spawnSync } from 'node:child_process';
import type { CommandUnit } from './parser.js';

// eslint-disable-next-line no-control-regex -- ANSI escapes contain the ESC control char by definition
const ANSI = /\x1b\[[0-9;]*m/g;
const ELLIPSIS = '...';

export interface RunResult {
  stdout: string;
  exitCode: number;
}

export type CheckResult = { ok: true } | { ok: false; message: string };

export function normalize(text: string): string {
  const lines = text.replace(ANSI, '').split('\n').map((line) => line.replace(/\s+$/, ''));
  while (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
  return lines.join('\n');
}

function normalizedLines(text: string): string[] {
  const normalized = normalize(text);
  return normalized === '' ? [] : normalized.split('\n');
}

function isEllipsis(line: string): boolean {
  return line.trim() === ELLIPSIS;
}

interface Pattern {
  segments: string[][];
  leadingGap: boolean;
  trailingGap: boolean;
}

function toPattern(lines: string[]): Pattern {
  const segments = lines
    .reduce<string[][]>(
      (acc, line) => (isEllipsis(line) ? [...acc, []] : pushLine(acc, line)),
      [[]],
    )
    .filter((segment) => segment.length > 0);
  return { segments, leadingGap: lines.length > 0 && isEllipsis(lines[0]), trailingGap: lines.length > 0 && isEllipsis(lines[lines.length - 1]) };
}

function pushLine(acc: string[][], line: string): string[][] {
  acc[acc.length - 1].push(line);
  return acc;
}

function indexOfSegment(actual: string[], segment: string[], from: number): number {
  for (let start = from; start + segment.length <= actual.length; start += 1) {
    if (segment.every((line, offset) => line === actual[start + offset])) return start;
  }
  return -1;
}

function placeSegments(pattern: Pattern, actual: string[]): number | null {
  let cursor = 0;
  for (let i = 0; i < pattern.segments.length; i += 1) {
    const anchored = i === 0 && !pattern.leadingGap;
    const found = indexOfSegment(actual, pattern.segments[i], cursor);
    if (found === -1 || (anchored && found !== 0)) return null;
    cursor = found + pattern.segments[i].length;
  }
  return cursor;
}

export function matchesExpected(expected: string, actual: string): boolean {
  const pattern = toPattern(normalizedLines(expected));
  const actualLines = normalizedLines(actual);
  if (pattern.segments.length === 0) return true;
  const end = placeSegments(pattern, actualLines);
  if (end === null) return false;
  return pattern.trailingGap || end === actualLines.length;
}

export async function runUnit(unit: CommandUnit, opts: { cwd: string }): Promise<RunResult> {
  const result = spawnSync('bash', ['-c', unit.command], { cwd: opts.cwd, encoding: 'utf8' });
  const exitCode = typeof result.status === 'number' ? result.status : 1;
  return { stdout: result.stdout ?? '', exitCode };
}

function stdoutMismatchMessage(unit: CommandUnit, result: RunResult): string {
  return [
    '--- expected stdout ---',
    unit.expectedStdout,
    '--- actual stdout ---',
    result.stdout === '' ? '(empty)' : normalize(result.stdout),
  ].join('\n');
}

export function checkUnit(unit: CommandUnit, result: RunResult): CheckResult {
  const header = `Command:\n${unit.command}`;
  if (result.exitCode !== unit.expectedExit) {
    return { ok: false, message: `${header}\nExpected exit ${unit.expectedExit} but got ${result.exitCode}` };
  }
  if (unit.expectedStdout !== null && !matchesExpected(unit.expectedStdout, result.stdout)) {
    return { ok: false, message: `${header}\n${stdoutMismatchMessage(unit, result)}` };
  }
  return { ok: true };
}
