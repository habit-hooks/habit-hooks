import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

export const BASELINE_FILENAME = '.habit-hooks-baseline.json';
export const BASELINE_VERSION = 1;

export interface BaselineEntry {
  snoozedAt: string;
}

export interface BaselineFile {
  version: 1;
  files: Record<string, BaselineEntry>;
}

export class BaselineVersionError extends Error {
  constructor(version: number) {
    super(`unsupported baseline version ${String(version)}; expected ${String(BASELINE_VERSION)}`);
    this.name = 'BaselineVersionError';
  }
}

export class BaselineParseError extends Error {
  constructor(message: string) {
    super(`failed to parse baseline: ${message}`);
    this.name = 'BaselineParseError';
  }
}

function baselinePath(cwd: string): string {
  return join(cwd, BASELINE_FILENAME);
}

function emptyBaseline(): BaselineFile {
  return { version: BASELINE_VERSION, files: {} };
}

function parseRaw(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    throw new BaselineParseError(message);
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validateEntry(value: unknown, key: string): BaselineEntry {
  if (!isPlainObject(value)) {
    throw new BaselineParseError(`entry for '${key}' must be an object`);
  }
  const snoozedAt = value.snoozedAt;
  if (typeof snoozedAt !== 'string' || snoozedAt.length === 0) {
    throw new BaselineParseError(`entry for '${key}' is missing 'snoozedAt' string`);
  }
  return { snoozedAt };
}

function validateFiles(value: unknown): Record<string, BaselineEntry> {
  if (!isPlainObject(value)) {
    throw new BaselineParseError(`'files' must be an object`);
  }
  const out: Record<string, BaselineEntry> = {};
  for (const [key, entry] of Object.entries(value)) {
    out[key] = validateEntry(entry, key);
  }
  return out;
}

function validateVersion(value: unknown): void {
  if (typeof value !== 'number') {
    throw new BaselineParseError(`'version' must be a number`);
  }
  if (value !== BASELINE_VERSION) throw new BaselineVersionError(value);
}

function validateBaseline(value: unknown): BaselineFile {
  if (!isPlainObject(value)) {
    throw new BaselineParseError(`root must be an object`);
  }
  validateVersion(value.version);
  return { version: BASELINE_VERSION, files: validateFiles(value.files) };
}

export function loadBaseline(cwd: string): BaselineFile {
  const path = baselinePath(cwd);
  if (!existsSync(path)) return emptyBaseline();
  const raw = readFileSync(path, 'utf8');
  return validateBaseline(parseRaw(raw));
}

function sortedEntries(files: Record<string, BaselineEntry>): Record<string, BaselineEntry> {
  const sorted: Record<string, BaselineEntry> = {};
  for (const key of Object.keys(files).sort()) {
    sorted[key] = files[key];
  }
  return sorted;
}

export function saveBaseline(cwd: string, baseline: BaselineFile): void {
  const ordered: BaselineFile = {
    version: BASELINE_VERSION,
    files: sortedEntries(baseline.files),
  };
  const serialized = `${JSON.stringify(ordered, null, 2)}\n`;
  writeFileSync(baselinePath(cwd), serialized);
}

export function baselineExists(cwd: string): boolean {
  return existsSync(baselinePath(cwd));
}
