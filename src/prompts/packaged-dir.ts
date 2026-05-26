import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const PROBE_FILE = 'eslint-max-params.md';
const SRC_PROMPTS_RELATIVE = join('..', '..', 'src', 'prompts');

export function resolvePackagedDir(): string {
  return existsSync(join(here, PROBE_FILE)) ? here : join(here, SRC_PROMPTS_RELATIVE);
}
