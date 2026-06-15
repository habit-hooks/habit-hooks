import { describe, expect, it } from 'vitest';
import { defaultRules, defaultConfig } from './defaults.js';
import { mergeRules } from './merge.js';

describe('defaults', () => {
  it('includes every locked v1 rule id', () => {
    const ids = new Set(defaultRules.map((r) => r.id));
    const expected = [
      'oversized-function',
      'too-many-parameters',
      'high-complexity',
      'oversized-file',
      'unused-variable',
      'loose-equality',
      'var-declaration',
      'non-const-binding',
      'duplicate-import',
      'warning-comment',
      'explicit-any',
      'non-null-assertion',
      'redundant-type-annotation',
      'non-essential-comment',
    ];
    for (const id of expected) {
      expect(ids.has(id), `missing ${id}`).toBe(true);
    }
  });

  it('survives the merge with an empty user config', () => {
    const merged = mergeRules(defaultRules, defaultConfig.smells, {});
    expect(merged.length).toBe(defaultRules.length);
  });

  it('applies the test-file exclude from defaultConfig', () => {
    const merged = mergeRules(defaultRules, defaultConfig.smells);
    const fnRule = merged.find((r) => r.id === 'oversized-function');
    expect(fnRule?.exclude).toEqual(['**/*.test.ts', '**/*.spec.ts', 'tests/**']);
  });

  it('marks the comment rule as custom source', () => {
    const rule = defaultRules.find((r) => r.id === 'non-essential-comment');
    expect(rule?.source).toBe('custom');
  });
});
