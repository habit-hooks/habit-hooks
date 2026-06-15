import { describe, expect, it } from 'vitest';
import { buildRules } from './registry.js';
import { DEFAULT_COMMENT_CHECK_THRESHOLDS } from '../checks/comment-check.js';

const COMMENT_RULE_ID = 'non-essential-comment';

describe('buildRules', () => {
  it('attaches default commentCheck thresholds when config.commentCheck is missing', () => {
    const rules = buildRules({}, process.cwd());
    const commentRule = rules.find((r) => r.id === COMMENT_RULE_ID);
    expect(commentRule?.commentCheck).toEqual(DEFAULT_COMMENT_CHECK_THRESHOLDS);
  });

  it('propagates custom commentCheck thresholds onto the comment rule', () => {
    const rules = buildRules(
      { commentCheck: { maxSingleLineChars: 42, maxBlockChars: 99 } },
      process.cwd(),
    );
    const commentRule = rules.find((r) => r.id === COMMENT_RULE_ID);
    expect(commentRule?.commentCheck).toEqual({ maxSingleLineChars: 42, maxBlockChars: 99 });
  });

  it('falls back to defaults for partial commentCheck overrides', () => {
    const rules = buildRules({ commentCheck: { maxSingleLineChars: 25 } }, process.cwd());
    const commentRule = rules.find((r) => r.id === COMMENT_RULE_ID);
    expect(commentRule?.commentCheck).toEqual({
      maxSingleLineChars: 25,
      maxBlockChars: DEFAULT_COMMENT_CHECK_THRESHOLDS.maxBlockChars,
    });
  });

  it('applies a smells override and carries the fix field onto the rule', () => {
    const config = { smells: { 'too-many-parameters': { severity: 'suggested' as const, fix: 'shared/style.md' } } };
    const rule = buildRules(config, process.cwd()).find((r) => r.id === 'too-many-parameters');
    expect(rule?.severity).toBe('suggested');
    expect(rule?.fix).toBe('shared/style.md');
  });

  it('lets smells take precedence over the rules alias for the same key', () => {
    const config = {
      rules: { 'too-many-parameters': { severity: 'suggested' as const } },
      smells: { 'too-many-parameters': { severity: 'enforced' as const } },
    };
    expect(buildRules(config, process.cwd()).find((r) => r.id === 'too-many-parameters')?.severity).toBe('enforced');
  });
});
