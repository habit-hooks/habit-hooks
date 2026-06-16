import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { chmodSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { delimiter, join } from 'node:path';
import { tmpdir } from 'node:os';
import { detectToolStates, toolsForLanguage } from './detect.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-init-detect-'));
}

function installFakePathBin(dir: string, name: string): void {
  const file = join(dir, name);
  writeFileSync(file, '#!/usr/bin/env bash\n');
  chmodSync(file, 0o755);
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

describe('toolsForLanguage', () => {
  it('maps python to ruff, deptry and jscpd', () => {
    expect(toolsForLanguage('python')).toEqual(['ruff', 'deptry', 'jscpd']);
  });

  it('maps typescript to eslint, knip and jscpd', () => {
    expect(toolsForLanguage('typescript')).toEqual(['eslint', 'knip', 'jscpd']);
  });
});

describe('detectToolStates for python tools', () => {
  let cwd: string;
  let originalPath: string | undefined;

  beforeEach(() => {
    cwd = makeTempDir();
    originalPath = process.env.PATH;
  });

  afterEach(() => {
    process.env.PATH = originalPath;
    rmSync(cwd, { recursive: true, force: true });
  });

  it('reports ruff installed when it is on PATH', () => {
    const binDir = makeTempDir();
    installFakePathBin(binDir, 'ruff');
    process.env.PATH = `${binDir}${delimiter}${originalPath ?? ''}`;
    expect(detectToolStates(cwd).ruff.installed).toBe(true);
    rmSync(binDir, { recursive: true, force: true });
  });

  it('reports a clearly-absent tool as not installed', () => {
    process.env.PATH = makeTempDir();
    const matrix = detectToolStates(cwd);
    expect(matrix.ruff.installed).toBe(false);
    expect(matrix.deptry.installed).toBe(false);
  });

  it('reports ruff configured via ruff.toml', () => {
    writeFileSync(join(cwd, 'ruff.toml'), 'line-length = 100\n');
    expect(detectToolStates(cwd).ruff.configured).toBe(true);
  });

  it('reports ruff configured via a [tool.ruff.lint.mccabe] section in pyproject.toml', () => {
    writeFileSync(
      join(cwd, 'pyproject.toml'),
      '[project]\nname = "x"\n\n[tool.ruff.lint.mccabe]\nmax-complexity = 10\n',
    );
    expect(detectToolStates(cwd).ruff.configured).toBe(true);
  });

  it('reports ruff not configured when neither config file nor [tool.ruff] is present', () => {
    writeFileSync(join(cwd, 'pyproject.toml'), '[project]\nname = "x"\n');
    expect(detectToolStates(cwd).ruff.configured).toBe(false);
  });

  it('reports deptry configured iff pyproject.toml exists', () => {
    expect(detectToolStates(cwd).deptry.configured).toBe(false);
    writeFileSync(join(cwd, 'pyproject.toml'), '[project]\nname = "x"\n');
    expect(detectToolStates(cwd).deptry.configured).toBe(true);
  });
});
