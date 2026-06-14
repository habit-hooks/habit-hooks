import { describe, expect, it } from 'vitest';
import { report } from './reporter.js';
import { loadGuidance } from './prompts/loader.js';
import type { Rule, Violation } from './types.js';

const enforcedRule: Rule = {
  id: 'eslint:max-params',
  source: 'eslint',
  sourceRuleId: 'max-params',
  severity: 'enforced',
  changedFilesOnly: false,
  title: 'Too many parameters',
  description: 'Functions should accept at most 3 parameters.',
};

const suggestedRule: Rule = {
  id: 'eslint:complexity',
  source: 'eslint',
  sourceRuleId: 'complexity',
  severity: 'suggested',
  changedFilesOnly: false,
  title: 'Function complexity is high',
  description: 'Cyclomatic complexity should stay at or below 10.',
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
    expect(result.stdout).toContain('Habit Hooks: automated checks passed.');
    expect(result.stdout).toContain('Habit Hooks catches structural smells');
    expect(result.stdout).toContain('reviewer sub-agent');
    expect(result.stdout).not.toContain('Violations:');
    expect(result.stdout).not.toContain('Uncoached rules');
  });

  it('returns exit 1 and renders group with guidance for enforced violation', () => {
    const result = report([makeViolation('eslint:max-params', 4)], rules);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Habit Hooks: 1 violation');
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('Functions should accept at most 3 parameters.');
    expect(result.stdout).toMatch(/parameters/i);
    expect(result.stdout).toContain('/abs/path/file.ts:4 - issue at line 4');
    expect(result.stdout).not.toContain('Uncoached rules');
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

  it('renders the Uncoached section for a violation whose rule id has no prompt', () => {
    const v = makeViolation('eslint:no-console', 3);
    const result = report([v], []);
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Uncoached rules');
    expect(result.stdout).toContain('eslint:no-console');
    expect(result.stdout).toContain('/abs/path/file.ts:3');
    expect(result.stdout).toContain('issue at line 3');
  });

  it('mixes coached and uncoached violations in one report', () => {
    const coached = makeViolation('eslint:max-params', 4);
    const uncoached = makeViolation('eslint:no-console', 9);
    const result = report([coached, uncoached], rules);
    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('Uncoached rules');
    expect(result.stdout).toContain('eslint:no-console');
    const uncoachedIdx = result.stdout.indexOf('Uncoached rules');
    const coachedIdx = result.stdout.indexOf('Too many parameters');
    expect(uncoachedIdx).toBeGreaterThan(coachedIdx);
  });

  it('does not render Uncoached section when all violations are coached', () => {
    const result = report([makeViolation('eslint:max-params', 1)], rules);
    expect(result.stdout).not.toContain('Uncoached rules');
  });

  it('coaches a violation whose rule id has a supplemental prompt but no Rule entry', () => {
    const v = makeViolation('eslint:fatal', 1);
    const result = report([v], []);
    expect(result.stdout).toContain('ESLint fatal parse/config error');
    expect(result.stdout).not.toContain('Uncoached rules');
  });

  it('falls back to the uncoached prompt text for a known rule with no tuned markdown', () => {
    const demotedRule: Rule = {
      id: 'eslint:no-var',
      source: 'eslint',
      sourceRuleId: 'no-var',
      severity: 'enforced',
      changedFilesOnly: false,
      title: 'var declaration',
      description: 'Use let or const; var hoists in surprising ways.',
    };
    const uncoachedText = loadGuidance('uncoached');
    if (uncoachedText === null) throw new Error('expected uncoached guidance to exist');
    const result = report([makeViolation('eslint:no-var', 5)], [demotedRule]);
    expect(result.stdout).toContain('var declaration');
    expect(result.stdout).toContain(uncoachedText);
    expect(result.stdout).not.toContain('Uncoached rules');
  });

  it('uncoached violations do not escalate exit code even alongside coached suggested rules', () => {
    const result = report(
      [makeViolation('eslint:no-console', 1), makeViolation('eslint:complexity', 2)],
      rules,
    );
    expect(result.exitCode).toBe(0);
    expect(result.stdout).toContain('Uncoached rules');
  });

  it('promotes supplemental prompts alongside enforced rules and isolates the truly uncoached', () => {
    const enforced = makeViolation('eslint:max-params', 4);
    const supplemental = makeViolation('eslint:fatal', 1);
    const uncoached = makeViolation('eslint:no-console', 9);

    const result = report([enforced, supplemental, uncoached], rules);

    expect(result.exitCode).toBe(1);
    expect(result.stdout).toContain('Too many parameters');
    expect(result.stdout).toContain('ESLint fatal parse/config error');
    expect(result.stdout).toContain('Uncoached rules');
    expect(result.stdout).toContain('eslint:no-console');

    const uncoachedIdx = result.stdout.indexOf('Uncoached rules');
    const supplementalIdx = result.stdout.indexOf('ESLint fatal parse/config error');
    expect(supplementalIdx).toBeGreaterThan(-1);
    expect(supplementalIdx).toBeLessThan(uncoachedIdx);

    const uncoachedTail = result.stdout.slice(uncoachedIdx);
    expect(uncoachedTail).not.toContain('eslint:fatal');
  });
});
