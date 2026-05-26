import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { run } from './runner.js';

const here = dirname(fileURLToPath(import.meta.url));
const sampleProject = join(here, '..', 'tests', 'fixtures', 'sample-project');

interface ExpectedCount {
  ruleId: string;
  count: number;
}

const EXPECTED: ExpectedCount[] = [
  { ruleId: 'eslint:max-lines-per-function', count: 1 },
  { ruleId: 'eslint:max-params', count: 1 },
  { ruleId: 'eslint:complexity', count: 1 },
  { ruleId: 'eslint:max-lines', count: 1 },
  { ruleId: 'eslint:no-unused-vars', count: 1 },
  { ruleId: 'eslint:eqeqeq', count: 1 },
  { ruleId: 'eslint:no-var', count: 1 },
  { ruleId: 'eslint:prefer-const', count: 1 },
  { ruleId: 'eslint:no-duplicate-imports', count: 1 },
  { ruleId: 'eslint:no-warning-comments', count: 1 },
  { ruleId: 'eslint:@typescript-eslint/no-explicit-any', count: 1 },
  { ruleId: 'eslint:@typescript-eslint/no-non-null-assertion', count: 1 },
  { ruleId: 'eslint:@typescript-eslint/no-inferrable-types', count: 1 },
  { ruleId: 'comment:non-essential', count: 1 },
  { ruleId: 'jscpd:duplication', count: 2 },
  { ruleId: 'knip:unused-class-members', count: 1 },
];

function countBy(violations: { ruleId: string }[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const v of violations) {
    counts.set(v.ruleId, (counts.get(v.ruleId) ?? 0) + 1);
  }
  return counts;
}

describe('acceptance: default rule set on sample-project fixture', () => {
  it('every default rule fires the expected number of times', async () => {
    const result = await run(sampleProject);
    const counts = countBy(result.violations);
    for (const { ruleId, count } of EXPECTED) {
      expect(counts.get(ruleId) ?? 0, `rule ${ruleId}`).toBe(count);
    }
  });

  it('exits non-zero because enforced violations are present', async () => {
    const result = await run(sampleProject);
    expect(result.exitCode).toBe(1);
  });
});
