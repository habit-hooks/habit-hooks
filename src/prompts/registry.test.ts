import { describe, expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { listPrompts, lookupPrompt } from './registry.js';

describe('lookupPrompt', () => {
  it('returns a populated CoachingPrompt for a known rule id', () => {
    const prompt = lookupPrompt('eslint:max-params');

    expect(prompt).not.toBeNull();
    expect(prompt?.id).toBe('eslint:max-params');
    expect(prompt?.title).toMatch(/parameters/i);
    expect(prompt?.description.length).toBeGreaterThan(0);
    expect(prompt?.severity).toBe('enforced');
    expect(prompt?.guidancePath).toMatch(/eslint-max-params\.md$/);
    expect(existsSync(prompt?.guidancePath ?? '')).toBe(true);
  });

  it('preserves plugin-namespaced ids verbatim', () => {
    const prompt = lookupPrompt('eslint:@typescript-eslint/no-non-null-assertion');
    expect(prompt?.id).toBe('eslint:@typescript-eslint/no-non-null-assertion');
    expect(prompt?.guidancePath).toMatch(/eslint-typescript-eslint-no-non-null-assertion\.md$/);
  });

  it('returns null for an unknown rule id', () => {
    expect(lookupPrompt('eslint:does-not-exist')).toBeNull();
  });

  it('defaults severity to suggested when not explicitly set', () => {
    const prompt = lookupPrompt('comment:non-essential');
    expect(prompt?.severity).toBe('suggested');
  });

  it('registers the eslint:fatal supplemental prompt with a tuned markdown file', () => {
    const prompt = lookupPrompt('eslint:fatal');
    expect(prompt, 'missing supplemental prompt eslint:fatal').not.toBeNull();
    expect(existsSync(prompt?.guidancePath ?? '')).toBe(true);
    expect(prompt?.severity).toBe('enforced');
  });

  it('does not register demoted supplemental prompts (they fall through to uncoached)', () => {
    const demoted = [
      'eslint:boundaries/dependencies',
      'knip:files',
      'knip:exports',
      'knip:types',
      'knip:dependencies',
    ];
    for (const id of demoted) {
      expect(lookupPrompt(id), `unexpected supplemental prompt ${id}`).toBeNull();
    }
  });
});

describe('listPrompts', () => {
  it('returns the full set with no duplicates by id', () => {
    const prompts = listPrompts();
    const ids = prompts.map((p) => p.id);
    expect(ids.length).toBeGreaterThan(0);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('includes every source family', () => {
    const ids = listPrompts().map((p) => p.id);
    expect(ids).toContain('eslint:max-params');
    expect(ids).toContain('jscpd:duplication');
    expect(ids).toContain('knip:classMembers');
    expect(ids).toContain('comment:non-essential');
  });
});
