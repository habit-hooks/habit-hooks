import { describe, expect, it } from 'vitest';
import { defaultRules } from './catalogue.js';
import {
  COMMENT_SMELL,
  ESLINT_PRODUCES,
  ESLINT_SMELL_MAP,
  JSCPD_SMELL,
  PARSE_ERROR_SMELL,
  catalogueSmell,
  singleSmellFor,
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

// singleSmellFor guards the JSCPD_SMELL single-pick site: a future catalogue
// that adds a second jscpd rule must fail loudly instead of silently picking [0].
describe('singleSmellFor', () => {
  it('returns the one smell for a single-smell source', () => {
    expect(singleSmellFor('jscpd')).toBe('duplicated-code');
  });

  it('throws when a source has no smells', () => {
    expect(() => singleSmellFor('nonexistent-source' as never)).toThrow(
      "tool-smells: expected exactly one 'nonexistent-source' smell, found 0",
    );
  });

  it('throws when a source has more than one smell', () => {
    expect(() => singleSmellFor('custom')).toThrow(/expected exactly one 'custom' smell, found 2/);
  });
});

// catalogueSmell guards COMMENT_SMELL by rule identity rather than source order:
// the 'custom' source now holds two rules (non-essential-comment + needs-extraction),
// so `smellsFor('custom')[0]` would silently flip if the catalogue were reordered.
describe('catalogueSmell', () => {
  it('returns the id when exactly one catalogue rule matches', () => {
    expect(catalogueSmell('non-essential-comment')).toBe('non-essential-comment');
  });

  it('throws when no catalogue rule matches', () => {
    expect(() => catalogueSmell('not-a-real-smell')).toThrow(
      "tool-smells: expected exactly one catalogue rule for 'not-a-real-smell', found 0",
    );
  });
});
