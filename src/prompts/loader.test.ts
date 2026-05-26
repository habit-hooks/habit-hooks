import { describe, expect, it } from 'vitest';
import { loadGuidance } from './loader.js';

describe('loadGuidance', () => {
  it('loads stub markdown for a known rule id', () => {
    const text = loadGuidance('eslint:max-params');
    expect(text.length).toBeGreaterThan(0);
    expect(text).toMatch(/parameters/i);
  });

  it('throws for an unknown rule id', () => {
    expect(() => loadGuidance('eslint:does-not-exist')).toThrow(/No guidance found/);
  });
});
