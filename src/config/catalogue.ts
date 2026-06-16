import type { Rule } from '../types.js';

// The canonical, tool-independent smell catalogue (docs/smell-vocabulary.md):
// default severity, title, and description per smell. Sensors translate raw tool
// output into these keys; a rule here makes the smell coached and lets its
// producing sensor activate. `source`/`sourceRuleId` are legacy provenance hints.

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
    title: 'Unused variable',
    description: 'Unused bindings are dead weight; remove them or rename with a leading underscore if intentional.',
  },
  {
    id: 'loose-equality',
    source: 'eslint',
    sourceRuleId: 'eqeqeq',
    severity: 'enforced',
    title: 'Loose equality',
    description: 'Use === / !== to avoid silent coercion bugs.',
  },
  {
    id: 'var-declaration',
    source: 'eslint',
    sourceRuleId: 'no-var',
    severity: 'enforced',
    title: '`var` declaration',
    description: 'Use let or const; var hoists in surprising ways.',
  },
  {
    id: 'non-const-binding',
    source: 'eslint',
    sourceRuleId: 'prefer-const',
    severity: 'enforced',
    title: 'Reassignable binding never reassigned',
    description: 'A let that is never reassigned should be const.',
  },
  {
    id: 'duplicate-import',
    source: 'eslint',
    sourceRuleId: 'no-duplicate-imports',
    severity: 'enforced',
    title: 'Duplicate import',
    description: 'Merge multiple imports from the same module into a single statement.',
  },
  {
    id: 'warning-comment',
    source: 'eslint',
    sourceRuleId: 'no-warning-comments',
    severity: 'suggested',
    title: 'Warning comment (TODO/FIXME/…)',
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
    title: 'Explicit `any`',
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
    title: 'Non-essential comment',
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

// The "unused" family: knip emits these for TypeScript; deptry emits
// unused-dependency and ruff emits unused-import for Python.
const unusedRules: Rule[] = [
  {
    id: 'unused-class-member',
    source: 'knip',
    severity: 'enforced',
    title: 'Unused class member',
    description: 'Class methods or properties not referenced anywhere are dead weight.',
  },
  {
    id: 'unused-file',
    source: 'knip',
    severity: 'enforced',
    title: 'Unused file',
    description: 'Files not referenced anywhere are dead weight; remove them.',
  },
  {
    id: 'unused-export',
    source: 'knip',
    severity: 'enforced',
    title: 'Unused export',
    description: 'Exports not imported anywhere are dead weight; drop the export or the symbol.',
  },
  {
    id: 'unused-dependency',
    source: 'knip',
    severity: 'enforced',
    title: 'Unused dependency',
    description: 'Dependencies declared but never used should be removed from the manifest.',
  },
  {
    id: 'unused-import',
    source: 'eslint',
    severity: 'enforced',
    title: 'Unused import',
    description: 'Imports that are never used should be removed.',
  },
];

export const defaultRules: Rule[] = [
  ...tier1Rules,
  ...tier2Rules,
  ...tier3Rules,
  ...customRules,
  ...jscpdRules,
  ...unusedRules,
];
