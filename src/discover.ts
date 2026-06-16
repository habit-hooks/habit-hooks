import fg from 'fast-glob';
import type { Language } from './config/schema.js';

const FILE_GLOBS: Record<Language, string[]> = {
  typescript: ['**/*.{ts,tsx,js,mjs,cjs}'],
  python: ['**/*.py'],
};

export async function discoverFiles(
  cwd: string,
  language: Language,
  exclude: string[] = [],
): Promise<string[]> {
  return fg(FILE_GLOBS[language], {
    cwd,
    absolute: true,
    ignore: ['**/node_modules/**', '**/dist/**', '**/coverage/**', ...exclude],
    dot: false,
  });
}
