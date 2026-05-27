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
