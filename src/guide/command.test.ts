import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runFixCommand } from './command.js';
import type { GuideAction } from '../mapper/mapper.js';

function action(severity: 'enforced' | 'suggested'): GuideAction {
  return {
    smell: 'broken-config',
    severity,
    title: 'Broken config',
    description: '',
    issues: [{ smell: 'broken-config', details: { file: '/a.ts', line: 1, message: 'x' } }],
    action: { kind: 'command', scriptPath: '' },
  };
}

describe('runFixCommand', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-command-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  function script(body: string): string {
    const path = join(dir, 'fixer');
    writeFileSync(path, body);
    chmodSync(path, 0o755);
    return path;
  }

  it('passes the smell bag as JSON on stdin and shows the script output to the agent', async () => {
    const path = script('#!/usr/bin/env bash\ncat\n');
    const run = await runFixCommand(action('enforced'), path, dir);
    expect(run.output).toContain('broken-config');
    expect(run.output).toContain('/a.ts');
  });

  it('does not block when the script exits 0, even for an enforced smell', async () => {
    const path = script('#!/usr/bin/env bash\nexit 0\n');
    const run = await runFixCommand(action('enforced'), path, dir);
    expect(run.blocks).toBe(false);
  });

  it('blocks an enforced smell when the script exits non-zero', async () => {
    const path = script('#!/usr/bin/env bash\nexit 3\n');
    const run = await runFixCommand(action('enforced'), path, dir);
    expect(run.blocks).toBe(true);
  });

  it('does not block a suggested smell when the script exits non-zero', async () => {
    const path = script('#!/usr/bin/env bash\nexit 3\n');
    const run = await runFixCommand(action('suggested'), path, dir);
    expect(run.blocks).toBe(false);
  });

  it('hard-fails (blocks) with a notice when the script cannot spawn', async () => {
    const run = await runFixCommand(action('suggested'), join(dir, 'does-not-exist'), dir);
    expect(run.blocks).toBe(true);
    expect(run.output).toContain('could not run');
  });
});
