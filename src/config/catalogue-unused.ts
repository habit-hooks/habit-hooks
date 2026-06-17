import type { Rule } from '../types.js';

// The "unused" family: knip (TS), deptry (unused-dependency), ruff (unused-import).
export const unusedRules: Rule[] = [
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
