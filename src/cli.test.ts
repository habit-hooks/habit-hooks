import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { existsSync } from 'node:fs';
import { beforeAll, describe, expect, it } from 'vitest';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const cliPath = join(repoRoot, 'dist', 'cli.js');

describe('cli', () => {
  beforeAll(() => {
    if (!existsSync(cliPath)) {
      const build = spawnSync('npm', ['run', 'build'], { cwd: repoRoot, encoding: 'utf8' });
      if (build.status !== 0) {
        throw new Error(`build failed: ${build.stderr}`);
      }
    }
  }, 60_000);

  it('prints version with --version', () => {
    const result = spawnSync('node', [cliPath, '--version'], { encoding: 'utf8' });
    expect(result.status).toBe(0);
    expect(result.stdout.trim()).toMatch(/^habit-hooks v0\.0\.0$/);
  });
});
