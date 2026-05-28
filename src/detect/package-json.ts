import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

export function hasPackageJsonKey(cwd: string, key: string): boolean {
  const path = join(cwd, 'package.json');
  if (!existsSync(path)) return false;
  try {
    const pkg = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
    return pkg[key] !== undefined;
  } catch {
    return false;
  }
}
