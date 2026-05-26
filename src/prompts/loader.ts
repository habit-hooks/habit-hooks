import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { resolvePackagedDir } from './packaged-dir.js';

function slugify(ruleId: string): string {
  return ruleId.replace(/[:/]/g, '-').replace(/@/g, '');
}

function tryRead(path: string): string | null {
  return existsSync(path) ? readFileSync(path, 'utf8').trimEnd() : null;
}

function missingError(ruleId: string, attempts: string[]): Error {
  const lines = attempts.map((p) => `  - ${p}`).join('\n');
  return new Error(`No guidance found for rule "${ruleId}". Tried:\n${lines}`);
}

export interface LoadGuidanceOptions {
  overrideDir?: string;
  packagedDir?: string;
}

function candidatePaths(slug: string, opts: LoadGuidanceOptions): string[] {
  const packagedDir = opts.packagedDir ?? resolvePackagedDir();
  const paths: string[] = [];
  if (opts.overrideDir !== undefined) paths.push(join(opts.overrideDir, `${slug}.md`));
  paths.push(join(packagedDir, `${slug}.md`));
  return paths;
}

export function loadGuidance(ruleId: string, opts: LoadGuidanceOptions = {}): string {
  const attempts = candidatePaths(slugify(ruleId), opts);
  for (const path of attempts) {
    const text = tryRead(path);
    if (text !== null) return text;
  }
  throw missingError(ruleId, attempts);
}
