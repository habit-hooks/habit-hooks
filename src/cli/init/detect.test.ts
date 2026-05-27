import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { detectToolStates } from './detect.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-init-detect-'));
}

function installFakeBin(cwd: string, name: string): void {
  const dir = join(cwd, 'node_modules', '.bin');
  mkdirSync(dir, { recursive: true });
  writeFileSync(join(dir, name), '#!/usr/bin/env node\n');
  const pkgDir = join(cwd, 'node_modules', name);
  mkdirSync(pkgDir, { recursive: true });
  writeFileSync(join(pkgDir, 'package.json'), JSON.stringify({ name }));
}

describe('detectToolStates', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('reports absent for every tool in an empty dir', () => {
    const matrix = detectToolStates(cwd);
    expect(matrix.eslint).toEqual({ installed: false, configured: false });
    expect(matrix.knip).toEqual({ installed: false, configured: false });
    expect(matrix.jscpd).toEqual({ installed: false, configured: false });
  });

  it('reports installed when a binary is present', () => {
    installFakeBin(cwd, 'eslint');
    expect(detectToolStates(cwd).eslint.installed).toBe(true);
  });

  it('reports configured when a config file is present even without a binary', () => {
    writeFileSync(join(cwd, 'eslint.config.js'), 'export default [];\n');
    const matrix = detectToolStates(cwd);
    expect(matrix.eslint.configured).toBe(true);
    expect(matrix.eslint.installed).toBe(false);
  });

  it('treats package.json#knip as a knip config', () => {
    writeFileSync(join(cwd, 'package.json'), JSON.stringify({ name: 'x', knip: { entry: [] } }));
    expect(detectToolStates(cwd).knip.configured).toBe(true);
  });

  it('treats .jscpd.json as a jscpd config', () => {
    writeFileSync(join(cwd, '.jscpd.json'), '{}');
    expect(detectToolStates(cwd).jscpd.configured).toBe(true);
  });
});
