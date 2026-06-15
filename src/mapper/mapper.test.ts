import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { mapIssues, resolveFix, type RoutingLookup } from './mapper.js';
import type { Issue } from '../sensors/types.js';

function issue(smell: string, file: string): Issue {
  return { smell, details: { file } };
}

describe('resolveFix', () => {
  let packagedDir: string;
  let overrideDir: string;

  beforeEach(() => {
    packagedDir = mkdtempSync(join(tmpdir(), 'hh-pkg-'));
    overrideDir = mkdtempSync(join(tmpdir(), 'hh-ovr-'));
  });
  afterEach(() => {
    rmSync(packagedDir, { recursive: true, force: true });
    rmSync(overrideDir, { recursive: true, force: true });
  });

  it('resolves <smell>.md from the packaged dir as a prompt', () => {
    writeFileSync(join(packagedDir, 'too-many-parameters.md'), 'PROMPT');
    const fix = resolveFix('too-many-parameters', undefined, { packagedDir });
    expect(fix).toEqual({ kind: 'prompt', templatePath: join(packagedDir, 'too-many-parameters.md') });
  });

  it('prefers the override dir over the packaged dir', () => {
    writeFileSync(join(packagedDir, 'duplicated-code.md'), 'PKG');
    writeFileSync(join(overrideDir, 'duplicated-code.md'), 'OVERRIDE');
    const fix = resolveFix('duplicated-code', undefined, { overrideDir, packagedDir });
    expect(fix).toEqual({ kind: 'prompt', templatePath: join(overrideDir, 'duplicated-code.md') });
  });

  it('falls back to a <smell> script as a command when no markdown exists', () => {
    writeFileSync(join(packagedDir, 'oversized-file'), '#!/bin/sh\n');
    const fix = resolveFix('oversized-file', undefined, { packagedDir });
    expect(fix).toEqual({ kind: 'command', scriptPath: join(packagedDir, 'oversized-file') });
  });

  it('returns null (uncoached) when nothing resolves', () => {
    expect(resolveFix('unknown-smell', undefined, { packagedDir })).toBeNull();
  });

  it('honours an explicit fix setting pointing at a markdown template', () => {
    mkdirSync(join(overrideDir, 'shared'));
    writeFileSync(join(overrideDir, 'shared', 'style.md'), 'SHARED');
    const fix = resolveFix('redundant-type-annotation', 'shared/style.md', { overrideDir, packagedDir });
    expect(fix).toEqual({ kind: 'prompt', templatePath: join(overrideDir, 'shared', 'style.md') });
  });

  it('treats a non-markdown fix setting as a command', () => {
    writeFileSync(join(packagedDir, 'fixit.sh'), '#!/bin/sh\n');
    const fix = resolveFix('any', 'fixit.sh', { packagedDir });
    expect(fix).toEqual({ kind: 'command', scriptPath: join(packagedDir, 'fixit.sh') });
  });

  it('throws a config error when an explicit fix names a missing file', () => {
    expect(() => resolveFix('any', 'nope.md', { packagedDir })).toThrow(/fix file not found: nope\.md/);
  });
});

describe('mapIssues', () => {
  let packagedDir: string;

  beforeEach(() => {
    packagedDir = mkdtempSync(join(tmpdir(), 'hh-map-'));
    writeFileSync(join(packagedDir, 'too-many-parameters.md'), 'PROMPT');
  });
  afterEach(() => {
    rmSync(packagedDir, { recursive: true, force: true });
  });

  const routing: RoutingLookup = (smell) =>
    smell === 'too-many-parameters' ? { severity: 'enforced' } : undefined;

  it('groups issues by smell and builds one action per coached smell', () => {
    const issues = [issue('too-many-parameters', '/a.ts'), issue('too-many-parameters', '/b.ts')];
    const result = mapIssues(issues, routing, { packagedDir });
    expect(result.actions).toHaveLength(1);
    expect(result.actions[0]?.smell).toBe('too-many-parameters');
    expect(result.actions[0]?.severity).toBe('enforced');
    expect(result.actions[0]?.issues.map((i) => i.details.file)).toEqual(['/a.ts', '/b.ts']);
    expect(result.actions[0]?.action).toEqual({ kind: 'prompt', templatePath: join(packagedDir, 'too-many-parameters.md') });
    expect(result.uncoached).toEqual([]);
  });

  it('routes a smell with no resolvable fix into the uncoached bucket', () => {
    const issues = [issue('mystery-smell', '/x.ts')];
    const result = mapIssues(issues, routing, { packagedDir });
    expect(result.actions).toEqual([]);
    expect(result.uncoached).toEqual(issues);
  });

  it('defaults severity to suggested when routing is absent but a template exists', () => {
    writeFileSync(join(packagedDir, 'duplicated-code.md'), 'PROMPT');
    const result = mapIssues([issue('duplicated-code', '/a.ts')], routing, { packagedDir });
    expect(result.actions[0]?.severity).toBe('suggested');
  });
});
