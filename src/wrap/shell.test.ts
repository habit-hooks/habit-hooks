import { describe, expect, it } from 'vitest';
import { tmpdir } from 'node:os';
import { runTool } from './shell.js';

describe('runTool', () => {
  it('captures stdout from a successful command', async () => {
    const result = await runTool({ bin: 'echo', args: ['hello'], cwd: tmpdir() });
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('hello');
    expect(result.warnings).toEqual([]);
  });

  it('does not throw when the command exits non-zero', async () => {
    const result = await runTool({
      bin: 'node',
      args: ['-e', 'process.stdout.write("oops"); process.exit(1)'],
      cwd: tmpdir(),
    });
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toBe('oops');
    expect(result.warnings).toEqual([]);
  });

  it('captures stderr separately from stdout', async () => {
    const result = await runTool({
      bin: 'node',
      args: ['-e', 'process.stderr.write("warn"); process.stdout.write("out")'],
      cwd: tmpdir(),
    });
    expect(result.stdout).toBe('out');
    expect(result.stderr).toBe('warn');
  });

  it('reports a single warning when the binary is missing', async () => {
    const result = await runTool({
      bin: '/definitely/not/here/please-do-not-exist',
      args: [],
      cwd: tmpdir(),
    });
    expect(result.exitCode).toBe(-1);
    expect(result.stdout).toBe('');
    expect(result.stderr).toBe('');
    expect(result.warnings).toHaveLength(1);
    expect(result.warnings[0]).toContain('please-do-not-exist');
  });

  it('kills the child and warns on timeout', async () => {
    const result = await runTool({
      bin: 'node',
      args: ['-e', 'setInterval(() => {}, 1000)'],
      cwd: tmpdir(),
      timeoutMs: 100,
    });
    expect(result.exitCode).toBe(-1);
    expect(result.warnings).toHaveLength(1);
    expect(result.warnings[0]).toMatch(/timed out/);
  });
});
