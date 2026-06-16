import { existsSync } from 'node:fs';
import { delimiter, join } from 'node:path';

const WINDOWS_EXTENSIONS = ['.exe', '.cmd'];

function candidateNames(name: string): string[] {
  return [name, ...WINDOWS_EXTENSIONS.map((ext) => `${name}${ext}`)];
}

function existsInDir(dir: string, name: string): boolean {
  return candidateNames(name).some((candidate) => existsSync(join(dir, candidate)));
}

export function isOnPath(name: string): boolean {
  const dirs = (process.env.PATH ?? '').split(delimiter).filter((dir) => dir.length > 0);
  return dirs.some((dir) => existsInDir(dir, name));
}
