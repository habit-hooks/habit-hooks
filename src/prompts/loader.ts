import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

function slugify(ruleId: string): string {
  return ruleId.replace(/[:/]/g, '-').replace(/@/g, '');
}

const PROBE_FILE = 'eslint-max-params.md';
const SRC_PROMPTS_RELATIVE = join('..', '..', 'src', 'prompts');

function resolvePackagedDir(): string {
  const alongsideLoader = existsSync(join(here, PROBE_FILE));
  return alongsideLoader ? here : join(here, SRC_PROMPTS_RELATIVE);
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
