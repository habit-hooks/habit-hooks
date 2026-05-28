import { describe, expect, it } from 'vitest';
import { tmpdir } from 'node:os';
import { isSpawnSkip, parseJsonStdout, spawnWrapped } from './run.js';

describe('spawnWrapped', () => {
  it('returns the ShellResult when the tool runs to completion', async () => {
    const result = await spawnWrapped('echo', { binPath: '/bin/echo', isFallback: false }, tmpdir(), ['hi']);
    expect(isSpawnSkip(result)).toBe(false);
    if (isSpawnSkip(result)) return;
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('hi');
  });

  it('returns a skipWarning when the binary cannot be spawned', async () => {
    const result = await spawnWrapped(
      'ghost',
      { binPath: '/definitely/not/here/ghost-bin', isFallback: false },
      tmpdir(),
      [],
    );
    expect(isSpawnSkip(result)).toBe(true);
    if (!isSpawnSkip(result)) return;
    expect(result.skipWarning).toContain('habit-hooks: ghost skipped');
    expect(result.skipWarning).toContain('ghost-bin');
  });

  it('passes through tool non-zero exits as a ShellResult, not a skip', async () => {
    const result = await spawnWrapped(
      'node',
      { binPath: process.execPath, isFallback: false },
      tmpdir(),
      ['-e', 'process.exit(2)'],
    );
    expect(isSpawnSkip(result)).toBe(false);
    if (isSpawnSkip(result)) return;
    expect(result.exitCode).toBe(2);
  });
});

describe('parseJsonStdout', () => {
  it('parses a valid object when startsWith is {', () => {
    expect(parseJsonStdout<{ a: number }>('  {"a":1}  ', '{')).toEqual({ a: 1 });
  });

  it('parses a valid array when startsWith is [', () => {
    expect(parseJsonStdout<number[]>('[1,2,3]', '[')).toEqual([1, 2, 3]);
  });

  it('returns null when stdout is empty', () => {
    expect(parseJsonStdout('', '{')).toBeNull();
    expect(parseJsonStdout('   ', '[')).toBeNull();
  });

  it('returns null when stdout does not start with the expected delimiter', () => {
    expect(parseJsonStdout('plain text', '{')).toBeNull();
    expect(parseJsonStdout('{"a":1}', '[')).toBeNull();
    expect(parseJsonStdout('[1,2]', '{')).toBeNull();
  });

  it('returns null when stdout starts correctly but fails to parse', () => {
    expect(parseJsonStdout('{not json', '{')).toBeNull();
    expect(parseJsonStdout('[1,2,', '[')).toBeNull();
  });
});
