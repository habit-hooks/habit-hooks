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
