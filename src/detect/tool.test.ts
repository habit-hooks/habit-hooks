import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, chmodSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { detectTool } from './tool.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-detect-'));
}

function installFakeTool(cwd: string, name: string, opts: { withBin?: boolean } = {}): void {
  const pkgDir = join(cwd, 'node_modules', name);
  mkdirSync(pkgDir, { recursive: true });
  const pkg: Record<string, unknown> = { name, version: '0.0.0' };
  if (opts.withBin !== false) {
    pkg.bin = { [name]: `./bin/${name}.js` };
    const binDir = join(pkgDir, 'bin');
    mkdirSync(binDir, { recursive: true });
    const binFile = join(binDir, `${name}.js`);
    writeFileSync(binFile, '#!/usr/bin/env node\n');
    chmodSync(binFile, 0o755);
  }
  writeFileSync(join(pkgDir, 'package.json'), JSON.stringify(pkg));
}

describe('detectTool', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('returns populated detection when bin and config file are present', () => {
    installFakeTool(cwd, 'eslint');
    writeFileSync(join(cwd, 'eslint.config.js'), 'export default [];\n');

    const result = detectTool(cwd, 'eslint');

    expect(result).not.toBeNull();
    expect(result?.binPath).toMatch(/node_modules\/eslint\/bin\/eslint\.js$/);
    expect(result?.configPath).toMatch(/eslint\.config\.js$/);
  });

  it('detects package.json#eslintConfig as a config source', () => {
    installFakeTool(cwd, 'eslint');
    writeFileSync(
      join(cwd, 'package.json'),
      JSON.stringify({ name: 'consumer', eslintConfig: { rules: {} } }),
    );

    const result = detectTool(cwd, 'eslint');

    expect(result?.configPath).toMatch(/package\.json$/);
  });

  it('returns null when binary is missing but config is present', () => {
    writeFileSync(join(cwd, 'eslint.config.js'), 'export default [];\n');

    const result = detectTool(cwd, 'eslint');

    expect(result).toBeNull();
  });

  it('returns null when neither bin nor config is present', () => {
    const result = detectTool(cwd, 'eslint');
    expect(result).toBeNull();
  });

  it('detects via node_modules/.bin fallback when package.json#bin is absent', () => {
    const pkgDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(pkgDir, { recursive: true });
    writeFileSync(join(pkgDir, 'package.json'), JSON.stringify({ name: 'knip' }));
    const binDir = join(cwd, 'node_modules', '.bin');
    mkdirSync(binDir, { recursive: true });
    const binFile = join(binDir, 'knip');
    writeFileSync(binFile, '#!/usr/bin/env node\n');
    chmodSync(binFile, 0o755);
    writeFileSync(join(cwd, 'knip.json'), '{}');

    const result = detectTool(cwd, 'knip');

    expect(result?.binPath).toMatch(/node_modules\/\.bin\/knip$/);
    expect(result?.configPath).toMatch(/knip\.json$/);
  });

  it('finds jscpd config in either .jscpd.json or jscpd.json', () => {
    installFakeTool(cwd, 'jscpd');
    writeFileSync(join(cwd, '.jscpd.json'), '{}');

    const result = detectTool(cwd, 'jscpd');
    expect(result?.configPath).toMatch(/\.jscpd\.json$/);
  });

  it('returns detection with configPath null when only the binary is present', () => {
    installFakeTool(cwd, 'eslint');

    const result = detectTool(cwd, 'eslint');

    expect(result).not.toBeNull();
    expect(result?.configPath).toBeNull();
  });
});
