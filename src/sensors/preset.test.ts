import { describe, expect, it } from 'vitest';
import { issueToViolation, violationToIssue } from './preset.js';
import { buildDefaultSensors } from './registry.js';
import { COMMENT_SMELL, JSCPD_SMELL, PARSE_ERROR_SMELL } from '../config/tool-smells.js';
import type { Rule, Violation } from '../types.js';

describe('violationToIssue', () => {
  it('maps the smell key and core fields into the details bag', () => {
    const v: Violation = {
      ruleId: 'too-many-parameters',
      file: '/repo/a.ts',
      line: 4,
      column: 2,
      message: 'Too many parameters',
      source: 'eslint:max-params',
    };
    expect(violationToIssue(v)).toEqual({
      smell: 'too-many-parameters',
      details: { file: '/repo/a.ts', line: 4, column: 2, message: 'Too many parameters', source: 'eslint:max-params' },
    });
  });

  it('omits column and source from details when absent', () => {
    const v: Violation = { ruleId: 'unused-file', file: '/repo/x.ts', line: 1, message: 'x.ts' };
    const issue = violationToIssue(v);
    expect(issue.details).toEqual({ file: '/repo/x.ts', line: 1, message: 'x.ts' });
    expect('column' in issue.details).toBe(false);
    expect('source' in issue.details).toBe(false);
  });
});

describe('issueToViolation', () => {
  it('round-trips a violation through the issue bag', () => {
    const v: Violation = {
      ruleId: 'duplicated-code',
      file: '/repo/a.ts',
      line: 1,
      column: 3,
      message: 'duplicates /repo/b.ts:1-7',
      source: 'jscpd:duplication',
    };
    expect(issueToViolation(violationToIssue(v))).toEqual(v);
  });

  it('round-trips a violation that carries no column or source', () => {
    const v: Violation = { ruleId: 'unused-file', file: '/repo/x.ts', line: 1, message: 'x.ts' };
    expect(issueToViolation(violationToIssue(v))).toEqual(v);
  });
});

describe('typescript preset', () => {
  it('registers the TS preset sensors (incl. the needs-extraction composite) with their smell keys', () => {
    const sensors = buildDefaultSensors('typescript', {
      sink: { notices: [], failures: [] },
      cwd: '',
      rulesById: new Map<string, Rule>(),
    });
    expect(sensors.map((s) => s.id)).toEqual(['eslint', 'comment', 'jscpd', 'knip', 'needs-extraction']);
    const eslint = sensors.find((s) => s.id === 'eslint');
    expect(eslint?.produces).toContain('too-many-parameters');
    expect(eslint?.produces).toContain(PARSE_ERROR_SMELL);
    expect(sensors.find((s) => s.id === 'jscpd')?.produces).toEqual([JSCPD_SMELL]);
    expect(sensors.find((s) => s.id === 'comment')?.produces).toEqual([COMMENT_SMELL]);
    const composite = sensors.find((s) => s.id === 'needs-extraction');
    expect(composite?.produces).toEqual(['needs-extraction']);
    expect(composite?.dependsOn).toEqual(['oversized-file', 'duplicated-code']);
  });
});
