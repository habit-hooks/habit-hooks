import fg from 'fast-glob';

const FILE_GLOBS: Record<string, string[]> = {
  typescript: ['**/*.{ts,tsx,js,mjs,cjs}'],
  python: ['**/*.py'],
};

export interface DiscoverOptions {
  exclude?: string[];
  files?: string[];
}

// Explicit `files` globs win; otherwise a built-in language supplies defaults; an
// unknown language with no `files` resolves to nothing.
export function globsFor(language: string, files?: string[]): string[] {
  if (files !== undefined && files.length > 0) return files;
  return FILE_GLOBS[language] ?? [];
}

export async function discoverFiles(
  cwd: string,
  language: string,
  options: DiscoverOptions = {},
): Promise<string[]> {
  const globs = globsFor(language, options.files);
  if (globs.length === 0) return [];
  const ignore = ['**/node_modules/**', '**/dist/**', '**/coverage/**', ...(options.exclude ?? [])];
  return fg(globs, { cwd, absolute: true, ignore, dot: false });
}
