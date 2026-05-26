import type { Rule } from '../types.js';

const RULES: Rule[] = [
  {
    id: 'eslint:max-params',
    source: 'eslint',
    sourceRuleId: 'max-params',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Too many parameters',
    description: 'Functions should accept at most 3 parameters.',
    eslintOptions: [3],
  },
  {
    id: 'eslint:max-lines-per-function',
    source: 'eslint',
    sourceRuleId: 'max-lines-per-function',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Function too long',
    description: 'Functions should fit in 15 lines (blank lines and comments excluded).',
    eslintOptions: [{ max: 15, skipBlankLines: true, skipComments: true }],
  },
  {
    id: 'eslint:complexity',
    source: 'eslint',
    sourceRuleId: 'complexity',
    severity: 'suggested',
    changedFilesOnly: false,
    title: 'Function complexity is high',
    description: 'Cyclomatic complexity should stay at or below 10.',
    eslintOptions: [10],
  },
];

export function getRules(): Rule[] {
  return RULES;
}
