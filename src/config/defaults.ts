import type { Rule } from '../types.js';
import type { HabitHooksConfig } from './schema.js';

const tier1Rules: Rule[] = [
  {
    id: 'eslint:max-lines-per-function',
    source: 'eslint',
    sourceRuleId: 'max-lines-per-function',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'Oversized function',
    description: 'Functions over 12 lines tend to bundle multiple responsibilities.',
    eslintOptions: [
      { max: 12, skipBlankLines: false, skipComments: false, IIFEs: true },
    ],
  },
  {
    id: 'eslint:max-params',
    source: 'eslint',
    sourceRuleId: 'max-params',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Too many parameters',
    description: 'Functions with many parameters violate single responsibility.',
    eslintOptions: [{ max: 3 }],
  },
  {
    id: 'eslint:complexity',
    source: 'eslint',
    sourceRuleId: 'complexity',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'High cyclomatic complexity',
    description: 'Complex functions are harder to understand, test, and maintain.',
    eslintOptions: [{ max: 10 }],
  },
  {
    id: 'eslint:max-lines',
    source: 'eslint',
    sourceRuleId: 'max-lines',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'Oversized file',
    description: 'Files over 200 lines are extremely difficult to maintain.',
    eslintOptions: [{ max: 200, skipBlankLines: false, skipComments: false }],
  },
];

const tier2Rules: Rule[] = [
  {
    id: 'eslint:no-unused-vars',
    source: 'eslint',
    sourceRuleId: 'no-unused-vars',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Unused variable',
    description: 'Unused bindings are dead weight; remove them or rename with a leading underscore if intentional.',
    eslintOptions: [{ argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
  },
  {
    id: 'eslint:eqeqeq',
    source: 'eslint',
    sourceRuleId: 'eqeqeq',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Loose equality',
    description: 'Use === / !== to avoid silent coercion bugs.',
    eslintOptions: ['always'],
  },
  {
    id: 'eslint:no-var',
    source: 'eslint',
    sourceRuleId: 'no-var',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'var declaration',
    description: 'Use let or const; var hoists in surprising ways.',
  },
  {
    id: 'eslint:prefer-const',
    source: 'eslint',
    sourceRuleId: 'prefer-const',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Reassignable binding never reassigned',
    description: 'A let that is never reassigned should be const.',
  },
  {
    id: 'eslint:no-duplicate-imports',
    source: 'eslint',
    sourceRuleId: 'no-duplicate-imports',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Duplicate import',
    description: 'Merge multiple imports from the same module into a single statement.',
  },
  {
    id: 'eslint:no-warning-comments',
    source: 'eslint',
    sourceRuleId: 'no-warning-comments',
    severity: 'suggested',
    changedFilesOnly: false,
    title: 'Warning comment',
    description: 'TODO / FIXME / XXX / HACK markers are unfinished work in the codebase.',
    eslintOptions: [{ terms: ['todo', 'fixme', 'xxx', 'hack'], location: 'anywhere' }],
  },
];

const tier3Rules: Rule[] = [
  {
    id: 'eslint:@typescript-eslint/no-explicit-any',
    source: 'eslint',
    sourceRuleId: '@typescript-eslint/no-explicit-any',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Explicit any',
    description: 'any disables the type checker; prefer a precise type or unknown plus a narrow.',
  },
  {
    id: 'eslint:@typescript-eslint/no-non-null-assertion',
    source: 'eslint',
    sourceRuleId: '@typescript-eslint/no-non-null-assertion',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Non-null assertion',
    description: 'The ! operator silences the type system; prove the value is present with a check.',
  },
  {
    id: 'eslint:@typescript-eslint/no-inferrable-types',
    source: 'eslint',
    sourceRuleId: '@typescript-eslint/no-inferrable-types',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Redundant type annotation',
    description: 'TypeScript infers obvious types; drop the annotation when it adds no information.',
  },
];

const customRules: Rule[] = [
  {
    id: 'comment:non-essential',
    source: 'custom',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Comment found',
    description: 'Comments indicate code that is not self-documenting.',
  },
];

export const defaultRules: Rule[] = [
  ...tier1Rules,
  ...tier2Rules,
  ...tier3Rules,
  ...customRules,
];

const TEST_FILE_EXCLUDE = ['**/*.test.ts', '**/*.spec.ts', 'tests/**'];

export const defaultConfig: HabitHooksConfig = {
  rules: {
    'eslint:max-lines-per-function': { exclude: TEST_FILE_EXCLUDE },
    'eslint:max-lines': { exclude: TEST_FILE_EXCLUDE },
  },
};
