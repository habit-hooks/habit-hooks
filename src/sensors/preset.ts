import { eslintWrap } from '../checks/eslint-wrap.js';
import { commentCheck } from '../checks/comment-check.js';
import { jscpdWrap } from '../checks/jscpd-wrap.js';
import { knipWrap } from '../checks/knip-wrap.js';
import type { Check, CheckOutcome, Rule, Violation } from '../types.js';
import type { Issue, Sensor } from './types.js';

// Smell keys each preset sensor can emit (docs/smell-vocabulary.md). Informational
// for dependency resolution; leaf sensors may also pass unmapped raw keys through.
const ESLINT_PRODUCES = [
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
  'parse-error',
];
const KNIP_PRODUCES = ['unused-class-member', 'unused-file', 'unused-export', 'unused-dependency'];

export function violationToIssue(v: Violation): Issue {
  const details: Record<string, unknown> = { file: v.file, line: v.line, message: v.message };
  if (v.column !== undefined) details.column = v.column;
  if (v.source !== undefined) details.source = v.source;
  return { smell: v.ruleId, details };
}

export function issueToViolation(issue: Issue): Violation {
  const d = issue.details;
  const column = typeof d.column === 'number' ? d.column : undefined;
  const source = typeof d.source === 'string' ? d.source : undefined;
  return { ruleId: issue.smell, file: String(d.file), line: Number(d.line), column, message: String(d.message), source };
}

function normalizeOutcome(result: Violation[] | CheckOutcome): CheckOutcome {
  return Array.isArray(result) ? { violations: result } : result;
}

interface LeafSpec {
  check: Check;
  produces: string[];
  notices: string[];
  rules?: Rule[];
}

function checkLeafSensor(spec: LeafSpec): Sensor {
  return {
    id: spec.check.id,
    produces: spec.produces,
    async run(ctx) {
      const outcome = normalizeOutcome(await spec.check.run(ctx.files, spec.rules ?? [], ctx.cwd));
      if (outcome.stderr) spec.notices.push(...outcome.stderr);
      return outcome.violations.map(violationToIssue);
    },
  };
}

export interface PresetInput {
  notices: string[];
  commentRule?: Rule;
}

// commentRule carries the resolved comment thresholds the ts-morph scan needs.
function commentSensor(input: PresetInput): Sensor {
  const rules = input.commentRule ? [input.commentRule] : [];
  return checkLeafSensor({ check: commentCheck, produces: ['non-essential-comment'], notices: input.notices, rules });
}

// The TypeScript/JavaScript preset: four leaf sensors over eslint, ts-morph
// comments, jscpd, and knip.
export function buildPresetSensors(input: PresetInput): Sensor[] {
  const { notices } = input;
  return [
    checkLeafSensor({ check: eslintWrap, produces: ESLINT_PRODUCES, notices }),
    commentSensor(input),
    checkLeafSensor({ check: jscpdWrap, produces: ['duplicated-code'], notices }),
    checkLeafSensor({ check: knipWrap, produces: KNIP_PRODUCES, notices }),
  ];
}
