import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scaffoldEslintConfig } from './scaffold-eslint-config.js';
import { TEST_FILE_EXCLUDE } from '../../config/defaults.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-eslint-scaffold-'));
}

describe('scaffoldEslintConfig', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('writes eslint.config.js when no config exists', () => {
    const result = scaffoldEslintConfig(cwd);
    expect(result.created).toBe(true);
    expect(existsSync(join(cwd, 'eslint.config.js'))).toBe(true);
  });

  it('embeds the v1 default rule values in the template', () => {
    scaffoldEslintConfig(cwd);
    const contents = readFileSync(join(cwd, 'eslint.config.js'), 'utf8');
    expect(contents).toContain("'max-lines-per-function'");
    expect(contents).toContain('max: 12');
    expect(contents).toContain("'max-params'");
    expect(contents).toContain('max: 3');
    expect(contents).toContain("'complexity'");
    expect(contents).toContain('max: 10');
    expect(contents).toContain("'max-depth'");
    expect(contents).toContain('max: 4');
    expect(contents).toContain("'max-lines'");
    expect(contents).toContain('max: 200');
  });

  it('exempts test files from the size rules, matching TEST_FILE_EXCLUDE', () => {
    scaffoldEslintConfig(cwd);
    const contents = readFileSync(join(cwd, 'eslint.config.js'), 'utf8');
    expect(contents).toContain("files: ['**/*.test.ts', '**/*.spec.ts', 'tests/**']");
    expect(contents).toContain("'max-lines-per-function': 'off'");
    expect(contents).toContain("'max-lines': 'off'");
  });

  it('derives the test-file glob list from TEST_FILE_EXCLUDE', () => {
    scaffoldEslintConfig(cwd);
    const contents = readFileSync(join(cwd, 'eslint.config.js'), 'utf8');
    const derivedGlobs = TEST_FILE_EXCLUDE.map((glob) => `'${glob}'`).join(', ');
    expect(contents).toContain(`files: [${derivedGlobs}]`);
  });

  it('does not overwrite an existing eslint.config.mjs', () => {
    const path = join(cwd, 'eslint.config.mjs');
    writeFileSync(path, 'export default [];\n');
    const result = scaffoldEslintConfig(cwd);
    expect(result.created).toBe(false);
    expect(result.path).toBe(path);
    expect(readFileSync(path, 'utf8')).toBe('export default [];\n');
  });

  it('does not overwrite an existing eslint.config.js', () => {
    const path = join(cwd, 'eslint.config.js');
    writeFileSync(path, '// existing\n');
    const result = scaffoldEslintConfig(cwd);
    expect(result.created).toBe(false);
    expect(readFileSync(path, 'utf8')).toBe('// existing\n');
  });
});
