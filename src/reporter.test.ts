import { describe, expect, it } from 'vitest';
import { report } from './reporter.js';
import type { Rule, Violation } from './types.js';

const enforcedRule: Rule = {
  id: 'eslint:max-params',
  source: 'eslint',
  sourceRuleId: 'max-params',
  severity: 'enforced',
  changedFilesOnly: false,
  title: 'Too many parameters',
  description: 'Functions should accept at most 3 parameters.',
  eslintOptions: [3],
};

const suggestedRule: Rule = {
  id: 'eslint:complexity',
  source: 'eslint',
  sourceRuleId: 'complexity',
  severity: 'suggested',
  changedFilesOnly: false,
  title: 'Function complexity is high',
  description: 'Cyclomatic complexity should stay at or below 10.',
  eslintOptions: [10],
};

const rules: Rule[] = [enforcedRule, suggestedRule];

function makeViolation(ruleId: string, line: number): Violation {
  return {
    ruleId,
    file: '/abs/path/file.ts',
    line,
    message: `issue at line ${line}`,
  };
}

describe('report', () => {
  it('returns exit 0 and clean header when no violations', () => {
    const result = report([], rules);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Habit Hooks: clean');
    expect(result.stdout).not.toContain('Violations:');
  });

  it('returns exit 1 and renders group with guidance for enforced violation', () => {
    const result = report([makeViolation('eslint:max-params', 4)], rules);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Habit Hooks: 1 violation');
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('Functions should accept at most 3 parameters.');
    expect(result.stdout).toMatch(/parameters/i);
    expect(result.stdout).toContain('/abs/path/file.ts:4 - issue at line 4');
  });

  it('returns exit 0 when only suggested rules have violations', () => {
    const result = report([makeViolation('eslint:complexity', 7)], rules);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Function complexity is high');
    expect(result.stdout).toContain('/abs/path/file.ts:7 - issue at line 7');
  });

  it('truncates groups to 10 entries and reports remaining count', () => {
    const violations = Array.from({ length: 12 }, (_, i) =>
      makeViolation('eslint:max-params', i + 1),
    );
    const result = report(violations, rules);
    expect(result.stdout).toContain('/abs/path/file.ts:10 - issue at line 10');
    expect(result.stdout).not.toContain('issue at line 11');
    expect(result.stdout).toContain('(2 more eslint:max-params violations)');
  });
});
