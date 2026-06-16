import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { chmodSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { guide } from './guide.js';
import type { GuideAction, MapResult } from '../mapper/mapper.js';
import type { Issue } from '../sensors/types.js';

function issue(smell: string, file: string, line = 1): Issue {
  return { smell, details: { file, line, message: `issue at ${line}` } };
}

interface ActionSpec {
  smell: string;
  severity: 'enforced' | 'suggested';
  path: string;
  issues: Issue[];
  title?: string;
  description?: string;
}

function promptAction(spec: ActionSpec): GuideAction {
  return {
    smell: spec.smell,
    severity: spec.severity,
    title: spec.title ?? spec.smell,
    description: spec.description ?? '',
    issues: spec.issues,
    action: { kind: 'prompt', templatePath: spec.path },
  };
}

function commandAction(spec: ActionSpec): GuideAction {
  return {
    smell: spec.smell,
    severity: spec.severity,
    title: spec.title ?? spec.smell,
    description: spec.description ?? '',
    issues: spec.issues,
    action: { kind: 'command', scriptPath: spec.path },
  };
}

describe('guide', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-guide-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  function template(name: string, body: string): string {
    const path = join(dir, name);
    writeFileSync(path, body);
    return path;
  }

  function script(name: string, body: string): string {
    const path = template(name, body);
    chmodSync(path, 0o755);
    return path;
  }

  function run(result: MapResult): Promise<{ stdout: string; exitCode: number }> {
    return guide({ result, dirs: { packagedDir: dir }, cwd: dir });
  }

  it('prints the clean banner and exit 0 when there is nothing to coach', async () => {
    const out = await run({ actions: [], uncoached: [] });
    expect(out.exitCode).toBe(0);
    expect(out.stdout).toContain('automated checks passed.');
    expect(out.stdout).toContain('reviewer sub-agent');
    expect(out.stdout.endsWith('\n\n')).toBe(true);
  });

  it('composes a section: title, prose (not the description), and the default issue list', async () => {
    const path = template('too-many-parameters.md', 'Prose for {{ smell }}.');
    const action = promptAction({
      smell: 'too-many-parameters',
      severity: 'enforced',
      path,
      issues: [issue('too-many-parameters', '/a.ts', 4)],
      title: 'Too many parameters',
      description: 'Functions with many parameters violate single responsibility.',
    });

    const out = await run({ actions: [action], uncoached: [] });

    expect(out.stdout).toContain('Habit Hooks: 1 violation');
    expect(out.stdout).toContain('❌ Too many parameters');
    expect(out.stdout).toContain('❌ Too many parameters\n\nProse for too-many-parameters.');
    expect(out.stdout).toContain('Prose for too-many-parameters.');
    expect(out.stdout).not.toContain('Functions with many parameters violate single responsibility.');
    expect(out.stdout).toContain('Violations:');
    expect(out.stdout).toContain('/a.ts:4 - issue at 4');
    expect(out.stdout.endsWith('\n\n')).toBe(true);
    expect(out.exitCode).toBe(1);
  });

  it('runs a command fix, streams its output to the agent, and exit 0 does not block an enforced smell', async () => {
    const path = script('broken-config', '#!/usr/bin/env bash\necho "ran the fixer"\nexit 0\n');
    const action = commandAction({
      smell: 'broken-config',
      severity: 'enforced',
      path,
      issues: [issue('broken-config', '/a.ts', 2)],
      title: 'Broken config',
      description: 'Run the fixer script to repair the config.',
    });

    const out = await run({ actions: [action], uncoached: [] });

    expect(out.stdout).toContain('❌ Broken config');
    expect(out.stdout).toContain('Run the fixer script to repair the config.');
    expect(out.stdout).toContain('/a.ts:2 - issue at 2');
    expect(out.stdout).toContain('ran the fixer');
    expect(out.exitCode).toBe(0);
  });

  it('lets a non-zero command fix block an enforced smell (exit 1)', async () => {
    const path = script('broken-config', '#!/usr/bin/env bash\nexit 1\n');
    const action = commandAction({
      smell: 'broken-config',
      severity: 'enforced',
      path,
      issues: [issue('broken-config', '/a.ts', 2)],
    });

    expect((await run({ actions: [action], uncoached: [] })).exitCode).toBe(1);
  });

  it('hard-fails the run (exit 1) with a notice when the fix command cannot spawn', async () => {
    const action = commandAction({
      smell: 'broken-config',
      severity: 'suggested',
      path: join(dir, 'missing-script'),
      issues: [issue('broken-config', '/a.ts', 2)],
    });

    const out = await run({ actions: [action], uncoached: [] });

    expect(out.exitCode).toBe(1);
    expect(out.stdout).toContain('could not run');
  });

  it('emits no stray blank line when the body is empty', async () => {
    const path = script('empty-body', '#!/usr/bin/env bash\nexit 0\n');
    const action = commandAction({
      smell: 'empty-body',
      severity: 'enforced',
      path,
      issues: [issue('empty-body', '/a.ts', 1)],
      title: 'Empty body',
      description: '',
    });

    const out = await run({ actions: [action], uncoached: [] });

    expect(out.stdout).toContain('❌ Empty body\n\nViolations:');
    expect(out.stdout).not.toContain('❌ Empty body\n\n\n');
  });

  it('separates top-level sections with three blank lines', async () => {
    const path = template('first.md', 'First prose.');
    const second = template('second.md', 'Second prose.');
    const actionA = promptAction({
      smell: 'first',
      severity: 'enforced',
      path,
      issues: [issue('first', '/a.ts', 1)],
      title: 'First',
    });
    const actionB = promptAction({
      smell: 'second',
      severity: 'enforced',
      path: second,
      issues: [issue('second', '/b.ts', 2)],
      title: 'Second',
    });

    const out = await run({ actions: [actionA, actionB], uncoached: [] });

    expect(out.stdout).toContain('/a.ts:1 - issue at 1\n\n\n\n❌ Second');
  });

  it('exits 0 when only suggested smells fired', async () => {
    const path = template('warning-comment.md', 'prose');
    const action = promptAction({
      smell: 'warning-comment',
      severity: 'suggested',
      path,
      issues: [issue('warning-comment', '/a.ts', 2)],
    });
    expect((await run({ actions: [action], uncoached: [] })).exitCode).toBe(0);
  });

  it('uses a per-smell <smell>.issues.njk to group issues by file', async () => {
    const path = template('oversized-function.md', 'prose');
    template(
      'oversized-function.issues.njk',
      '{% for file, group in issues | groupby("details.file") %}{{ file }}: {{ group | length }}\n{% endfor %}',
    );
    const issues = [
      issue('oversized-function', '/a.ts', 1),
      issue('oversized-function', '/a.ts', 9),
      issue('oversized-function', '/b.ts', 1),
    ];
    const action = promptAction({ smell: 'oversized-function', severity: 'enforced', path, issues });

    const out = await run({ actions: [action], uncoached: [] });

    expect(out.stdout).toContain('/a.ts: 2');
    expect(out.stdout).toContain('/b.ts: 1');
    expect(out.stdout).not.toContain('Violations:');
  });

  it('lists the uncoached bucket with provenance and does not escalate the exit code', async () => {
    const uncoached: Issue[] = [
      { smell: 'no-console', details: { file: '/a.ts', line: 3, message: 'x', source: 'eslint:no-console' } },
    ];
    const out = await run({ actions: [], uncoached });
    expect(out.stdout).toContain('Uncoached smells');
    expect(out.stdout).toContain('eslint:no-console');
    expect(out.stdout).toContain('/a.ts:3');
    expect(out.exitCode).toBe(0);
  });
});
