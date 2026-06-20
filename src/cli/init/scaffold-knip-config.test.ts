import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scaffoldKnipConfig } from './scaffold-knip-config.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-knip-scaffold-'));
}

describe('scaffoldKnipConfig', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('writes knip.json when no config exists', () => {
    const result = scaffoldKnipConfig(cwd);
    expect(result.created).toBe(true);
    expect(existsSync(join(cwd, 'knip.json'))).toBe(true);
  });

  it('parses as JSON with an entry and project field', () => {
    scaffoldKnipConfig(cwd);
    const parsed = JSON.parse(readFileSync(join(cwd, 'knip.json'), 'utf8')) as {
      entry?: string[];
      project?: string[];
    };
    expect(parsed.entry).toBeDefined();
    expect(parsed.project).toBeDefined();
  });

  it('marks src entries as production but keeps the test entry unmarked', () => {
    scaffoldKnipConfig(cwd);
    const parsed = JSON.parse(readFileSync(join(cwd, 'knip.json'), 'utf8')) as {
      entry: string[];
    };
    const srcEntries = parsed.entry.filter((pattern) => pattern.startsWith('src/'));
    expect(srcEntries.every((pattern) => pattern.endsWith('!'))).toBe(true);
    expect(parsed.entry).toContain('tests/**/*.test.ts');
    expect(parsed.entry).not.toContain('tests/**/*.test.ts!');
  });

  it('marks the src project glob as production but keeps tests unmarked', () => {
    scaffoldKnipConfig(cwd);
    const parsed = JSON.parse(readFileSync(join(cwd, 'knip.json'), 'utf8')) as {
      project: string[];
    };
    expect(parsed.project).toContain('src/**/*.ts!');
    expect(parsed.project).toContain('tests/**/*.ts');
  });

  it('does not overwrite an existing knip.json', () => {
    const path = join(cwd, 'knip.json');
    writeFileSync(path, '{"existing":true}');
    const result = scaffoldKnipConfig(cwd);
    expect(result.created).toBe(false);
    expect(readFileSync(path, 'utf8')).toBe('{"existing":true}');
  });

  it('does not overwrite an existing knip.ts', () => {
    const path = join(cwd, 'knip.ts');
    writeFileSync(path, 'export default {};\n');
    const result = scaffoldKnipConfig(cwd);
    expect(result.created).toBe(false);
    expect(result.path).toBe(path);
  });
});
