import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, relative } from 'node:path';
import { discoverFiles } from './discover.js';

function write(dir: string, rel: string): void {
  const path = join(dir, rel);
  mkdirSync(join(path, '..'), { recursive: true });
  writeFileSync(path, 'export const x = 1;\n');
}

describe('discoverFiles', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = mkdtempSync(join(tmpdir(), 'hh-discover-'));
    write(cwd, 'a.ts');
    write(cwd, 'sub/b.ts');
    write(cwd, 'fixtures/bad.ts');
    write(cwd, 'node_modules/dep/c.ts');
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('ignores the built-in set and keeps everything else by default', async () => {
    const files = await discoverFiles(cwd, 'typescript');
    expect(files.map((file) => relative(cwd, file)).sort()).toEqual([
      'a.ts',
      'fixtures/bad.ts',
      'sub/b.ts',
    ]);
  });

  it('also skips paths matched by scope.exclude', async () => {
    const files = await discoverFiles(cwd, 'typescript', ['fixtures/**']);
    expect(files.map((file) => relative(cwd, file)).sort()).toEqual(['a.ts', 'sub/b.ts']);
  });
});
