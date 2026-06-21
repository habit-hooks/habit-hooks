import { describe, expect, it } from 'vitest';
import { defaultRules } from './catalogue.js';
import {
  COMMENT_SMELL,
  ESLINT_PRODUCES,
  ESLINT_SMELL_MAP,
  JSCPD_SMELL,
  PARSE_ERROR_SMELL,
} from './tool-smells.js';

// These prove the sensor/check layer's smell knowledge is DERIVED from the
// catalogue: adding a smell there auto-wires its translation and produces with
// zero edits to runner/sensor/check code (issue #24; deep-nesting is the live
// demonstrator).
describe('tool-smells derivation', () => {
  it('derives the eslint raw->smell map from every catalogue eslint rule with a sourceRuleId', () => {
    for (const rule of defaultRules) {
      if (rule.source === 'eslint' && rule.sourceRuleId !== undefined) {
        expect(ESLINT_SMELL_MAP[rule.sourceRuleId], rule.id).toBe(rule.id);
      }
    }
  });

  it('eslint produces every catalogue eslint smell plus the supplemental parse-error', () => {
    for (const rule of defaultRules.filter((r) => r.source === 'eslint')) {
      expect(ESLINT_PRODUCES).toContain(rule.id);
    }
    expect(ESLINT_PRODUCES).toContain(PARSE_ERROR_SMELL);
  });

  it('jscpd and comment smells are the catalogue rules for those sources', () => {
    expect(JSCPD_SMELL).toBe(defaultRules.find((r) => r.source === 'jscpd')?.id);
    expect(COMMENT_SMELL).toBe(defaultRules.find((r) => r.source === 'custom')?.id);
  });
});

// Concrete value pins: a catalogue rename or typo fails the suite immediately.
// Keep alongside the derivation tests above so both the derivation logic AND
// the actual string values are guarded.
describe('tool-smells concrete values', () => {
  it('JSCPD_SMELL is duplicated-code', () => {
    expect(JSCPD_SMELL).toBe('duplicated-code');
  });

  it('COMMENT_SMELL is non-essential-comment', () => {
    expect(COMMENT_SMELL).toBe('non-essential-comment');
  });

  it('PARSE_ERROR_SMELL is parse-error', () => {
    expect(PARSE_ERROR_SMELL).toBe('parse-error');
  });
});

// JSCPD_SMELL is built by a single-pick guard over the 'jscpd' source: it must
// resolve to exactly one rule, so a future catalogue that adds a second jscpd
// rule fails module load loudly instead of silently picking [0]. We exercise
// that guard through the const production actually consumes.
describe('JSCPD_SMELL single-pick', () => {
  it('is the sole jscpd catalogue rule', () => {
    const jscpdRules = defaultRules.filter((r) => r.source === 'jscpd');
    expect(jscpdRules).toHaveLength(1);
    expect(JSCPD_SMELL).toBe(jscpdRules[0].id);
  });
});

// COMMENT_SMELL is built by an identity guard rather than source order: the
// 'custom' source holds two rules (non-essential-comment + needs-extraction),
// so a position-based pick would silently flip on reorder. The const is pinned
// by rule id, and that id must match exactly one catalogue rule.
describe('COMMENT_SMELL identity-pick', () => {
  it('matches exactly one catalogue rule by id, independent of source order', () => {
    const matches = defaultRules.filter((r) => r.id === COMMENT_SMELL);
    expect(matches).toHaveLength(1);
    expect(matches[0].source).toBe('custom');
    expect(defaultRules.filter((r) => r.source === 'custom').length).toBeGreaterThan(1);
  });
});
