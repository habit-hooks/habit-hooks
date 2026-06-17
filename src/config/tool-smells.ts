import type { Rule, RuleSource } from '../types.js';
import type { AdapterSpec, DeclarativeSensorSpec } from '../sensors/adapter.js';
import { defaultRules } from './catalogue.js';

// The single home for tool/smell knowledge (issue #24): the sensor and check
// layers receive these from config and never hardcode a smell id. eslint/jscpd
// data is derived from the catalogue, so adding a smell there auto-wires it.

function rulesFor(source: RuleSource): Rule[] {
  return defaultRules.filter((rule) => rule.source === source);
}

function smellsFor(source: RuleSource): string[] {
  return rulesFor(source).map((rule) => rule.id);
}

export function singleSmellFor(source: RuleSource): string {
  const smells = smellsFor(source);
  if (smells.length !== 1)
    throw new Error(`tool-smells: expected exactly one '${source}' smell, found ${smells.length}`);
  return smells[0];
}

export function catalogueSmell(id: string): string {
  const matches = defaultRules.filter((rule) => rule.id === id);
  if (matches.length !== 1)
    throw new Error(`tool-smells: expected exactly one catalogue rule for '${id}', found ${matches.length}`);
  return matches[0].id;
}

function rawToSmell(source: RuleSource): Record<string, string> {
  const map: Record<string, string> = {};
  for (const rule of rulesFor(source)) {
    if (rule.sourceRuleId !== undefined) map[rule.sourceRuleId] = rule.id;
  }
  return map;
}

// `parse-error` is a supplemental smell (eslint fatal) with no catalogue rule.
export const PARSE_ERROR_SMELL = 'parse-error';

export const ESLINT_SMELL_MAP = rawToSmell('eslint');
export const ESLINT_PRODUCES = [...smellsFor('eslint'), PARSE_ERROR_SMELL];

export const JSCPD_SMELL = singleSmellFor('jscpd');
export const COMMENT_SMELL = catalogueSmell('non-essential-comment');

// knip's raw issue types are tool-specific, not catalogue rule ids, so the
// translation lives here in config.
export const KNIP_SMELL_MAP: Record<string, string> = {
  classMembers: 'unused-class-member',
  files: 'unused-file',
  exports: 'unused-export',
  dependencies: 'unused-dependency',
};
export const KNIP_PRODUCES = Object.values(KNIP_SMELL_MAP);

// Python tool specs (the generalized AdapterSpec model): ruff + deptry.
export const RUFF_SPEC: DeclarativeSensorSpec = {
  id: 'ruff',
  produces: ['high-complexity', 'too-many-parameters', 'oversized-function', 'unused-variable', 'unused-import'],
  command: 'ruff check --output-format=json --select=C901,PLR0913,PLR0915,F841,F401 ${files}',
  items: '[]',
  fields: { smell: 'code', file: 'filename', line: 'location.row', column: 'location.column', message: 'message' },
  map: {
    C901: 'high-complexity',
    PLR0913: 'too-many-parameters',
    PLR0915: 'oversized-function',
    F841: 'unused-variable',
    F401: 'unused-import',
  },
};

export const DEPTRY_SPEC: AdapterSpec = {
  id: 'deptry',
  command: 'deptry . --json-output <report>',
  items: '[]',
  fields: { smell: 'error.code', file: 'location.file', line: 'location.line', message: 'error.message' },
  map: { DEP002: 'unused-dependency' },
};
export const DEPTRY_PRODUCES = Object.values(DEPTRY_SPEC.map ?? {});
