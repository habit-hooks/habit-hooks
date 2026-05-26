import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

function slugify(ruleId: string): string {
  return ruleId.replace(/:/g, '-');
}

function resolvePromptsDir(): string {
  // When compiled, `here` is .../dist/prompts and the source markdown lives at
  // .../src/prompts. When running tests via vitest, `here` is .../src/prompts
  // and the files sit alongside this loader.
  const localPath = here;
  if (existsSync(join(localPath, 'eslint-max-params.md'))) {
    return localPath;
  }
  return join(here, '..', '..', 'src', 'prompts');
}

export function loadGuidance(ruleId: string, overrideDir?: string): string {
  const dir = overrideDir ?? resolvePromptsDir();
  const filePath = join(dir, `${slugify(ruleId)}.md`);
  if (!existsSync(filePath)) {
    throw new Error(`No guidance found for rule "${ruleId}" at ${filePath}`);
  }
  return readFileSync(filePath, 'utf8').trimEnd();
}
