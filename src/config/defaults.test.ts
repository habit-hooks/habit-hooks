import { describe, expect, it } from 'vitest';
import { defaultRules, defaultConfig } from './defaults.js';
import { mergeRules } from './merge.js';

describe('defaults', () => {
  it('includes every locked v1 rule id', () => {
    const ids = new Set(defaultRules.map((r) => r.id));
    const expected = [
      'eslint:max-lines-per-function',
      'eslint:max-params',
      'eslint:complexity',
      'eslint:max-lines',
      'eslint:no-unused-vars',
      'eslint:eqeqeq',
      'eslint:no-var',
      'eslint:prefer-const',
      'eslint:no-duplicate-imports',
      'eslint:no-warning-comments',
      'eslint:@typescript-eslint/no-explicit-any',
      'eslint:@typescript-eslint/no-non-null-assertion',
      'eslint:@typescript-eslint/no-inferrable-types',
      'comment:non-essential',
    ];
    for (const id of expected) {
      expect(ids.has(id), `missing ${id}`).toBe(true);
    }
  });

  it('survives the merge with an empty user config', () => {
    const merged = mergeRules(defaultRules, defaultConfig.rules, {});
    expect(merged.length).toBe(defaultRules.length);
  });

  it('applies the test-file exclude from defaultConfig', () => {
    const merged = mergeRules(defaultRules, defaultConfig.rules);
    const fnRule = merged.find((r) => r.id === 'eslint:max-lines-per-function');
    expect(fnRule?.exclude).toEqual(['**/*.test.ts', '**/*.spec.ts', 'tests/**']);
  });

  it('marks the comment rule as custom source', () => {
    const rule = defaultRules.find((r) => r.id === 'comment:non-essential');
    expect(rule?.source).toBe('custom');
  });
});
