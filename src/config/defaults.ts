import type { Rule } from '../types.js';
import type { HabitHooksConfig } from './schema.js';

const tier1Rules: Rule[] = [
  {
    id: 'oversized-function',
    source: 'eslint',
    sourceRuleId: 'max-lines-per-function',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'Oversized function',
    description: 'Functions over 12 lines tend to bundle multiple responsibilities.',
  },
  {
    id: 'too-many-parameters',
    source: 'eslint',
    sourceRuleId: 'max-params',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Too many parameters',
    description: 'Functions with many parameters violate single responsibility.',
  },
  {
    id: 'high-complexity',
    source: 'eslint',
    sourceRuleId: 'complexity',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'High cyclomatic complexity',
    description: 'Complex functions are harder to understand, test, and maintain.',
  },
  {
    id: 'oversized-file',
    source: 'eslint',
    sourceRuleId: 'max-lines',
    severity: 'enforced',
    changedFilesOnly: true,
    title: 'Oversized file',
    description: 'Files over 200 lines are extremely difficult to maintain.',
  },
];

const tier2Rules: Rule[] = [
  {
    id: 'unused-variable',
    source: 'eslint',
    sourceRuleId: 'no-unused-vars',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Unused variable',
    description: 'Unused bindings are dead weight; remove them or rename with a leading underscore if intentional.',
  },
  {
    id: 'loose-equality',
    source: 'eslint',
    sourceRuleId: 'eqeqeq',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Loose equality',
    description: 'Use === / !== to avoid silent coercion bugs.',
  },
  {
    id: 'var-declaration',
    source: 'eslint',
    sourceRuleId: 'no-var',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'var declaration',
    description: 'Use let or const; var hoists in surprising ways.',
  },
  {
    id: 'non-const-binding',
    source: 'eslint',
    sourceRuleId: 'prefer-const',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Reassignable binding never reassigned',
    description: 'A let that is never reassigned should be const.',
  },
  {
    id: 'duplicate-import',
    source: 'eslint',
    sourceRuleId: 'no-duplicate-imports',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Duplicate import',
    description: 'Merge multiple imports from the same module into a single statement.',
  },
  {
    id: 'warning-comment',
    source: 'eslint',
    sourceRuleId: 'no-warning-comments',
    severity: 'suggested',
    changedFilesOnly: false,
    title: 'Warning comment',
    description: 'TODO / FIXME / XXX / HACK markers are unfinished work in the codebase.',
  },
];

const tier3Rules: Rule[] = [
  {
    id: 'explicit-any',
    source: 'eslint',
    sourceRuleId: '@typescript-eslint/no-explicit-any',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Explicit any',
    description: 'any disables the type checker; prefer a precise type or unknown plus a narrow.',
  },
  {
    id: 'non-null-assertion',
    source: 'eslint',
    sourceRuleId: '@typescript-eslint/no-non-null-assertion',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Non-null assertion',
    description: 'The ! operator silences the type system; prove the value is present with a check.',
  },
  {
    id: 'redundant-type-annotation',
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
    id: 'non-essential-comment',
    source: 'custom',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Comment found',
    description: 'Comments indicate code that is not self-documenting.',
  },
];

const jscpdRules: Rule[] = [
  {
    id: 'duplicated-code',
    source: 'jscpd',
    severity: 'suggested',
    changedFilesOnly: true,
    title: 'Duplicated code',
    description: 'Repeated blocks usually want a shared abstraction, not a copy-paste.',
  },
];

const knipRules: Rule[] = [
  {
    id: 'unused-class-member',
    source: 'knip',
    severity: 'enforced',
    changedFilesOnly: false,
    title: 'Unused class member',
    description: 'Class methods or properties not referenced anywhere are dead weight.',
  },
];

export const defaultRules: Rule[] = [
  ...tier1Rules,
  ...tier2Rules,
  ...tier3Rules,
  ...customRules,
  ...jscpdRules,
  ...knipRules,
];

const TEST_FILE_EXCLUDE = ['**/*.test.ts', '**/*.spec.ts', 'tests/**'];

const CONFIG_FILE_EXCLUDE = ['habit-hooks.config.*'];

export const defaultConfig: HabitHooksConfig = {
  smells: {
    'oversized-function': { exclude: TEST_FILE_EXCLUDE },
    'oversized-file': { exclude: TEST_FILE_EXCLUDE },
    'duplicated-code': { exclude: TEST_FILE_EXCLUDE },
    'non-essential-comment': { exclude: CONFIG_FILE_EXCLUDE },
  },
};
