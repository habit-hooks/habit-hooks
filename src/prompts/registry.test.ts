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
    const prompt = lookupPrompt('eslint:@typescript-eslint/no-explicit-any');
    expect(prompt?.id).toBe('eslint:@typescript-eslint/no-explicit-any');
    expect(prompt?.guidancePath).toMatch(/eslint-typescript-eslint-no-explicit-any\.md$/);
  });

  it('returns null for an unknown rule id', () => {
    expect(lookupPrompt('eslint:does-not-exist')).toBeNull();
  });

  it('defaults severity to suggested when not explicitly set', () => {
    const prompt = lookupPrompt('comment:non-essential');
    expect(prompt?.severity).toBe('suggested');
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
    expect(ids).toContain('knip:unused-class-members');
    expect(ids).toContain('comment:non-essential');
  });
});
