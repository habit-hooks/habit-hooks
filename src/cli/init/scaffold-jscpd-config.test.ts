import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { scaffoldJscpdConfig } from './scaffold-jscpd-config.js';

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-jscpd-scaffold-'));
}

describe('scaffoldJscpdConfig', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });

  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('writes .jscpd.json when no config exists', () => {
    const result = scaffoldJscpdConfig(cwd);
    expect(result.created).toBe(true);
    expect(existsSync(join(cwd, '.jscpd.json'))).toBe(true);
  });

  it('encodes v1 default minTokens/minLines', () => {
    scaffoldJscpdConfig(cwd);
    const parsed = JSON.parse(readFileSync(join(cwd, '.jscpd.json'), 'utf8')) as {
      minTokens?: number;
      minLines?: number;
    };
    expect(parsed.minTokens).toBe(50);
    expect(parsed.minLines).toBe(5);
  });

  it('does not overwrite an existing jscpd.json', () => {
    const path = join(cwd, 'jscpd.json');
    writeFileSync(path, '{"existing":true}');
    const result = scaffoldJscpdConfig(cwd);
    expect(result.created).toBe(false);
    expect(readFileSync(path, 'utf8')).toBe('{"existing":true}');
  });
});
