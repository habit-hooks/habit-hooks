import { eslintWrap } from '../checks/eslint-wrap.js';
import { commentCheck } from '../checks/comment-check.js';
import { jscpdWrap } from '../checks/jscpd-wrap.js';
import { knipWrap } from '../checks/knip-wrap.js';
import type { SensorSink } from '../wrap/notices.js';
import { COMMENT_SMELL, ESLINT_PRODUCES, JSCPD_SMELL, KNIP_PRODUCES } from '../config/tool-smells.js';
import { needsExtractionSensor } from './needs-extraction.js';
import type { Check, CheckOutcome, Rule, Violation } from '../types.js';
import type { Issue, Sensor } from './types.js';

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
  const line = typeof d.line === 'number' ? d.line : 1;
  return { ruleId: issue.smell, file: String(d.file), line, column, message: String(d.message), source };
}

function normalizeOutcome(result: Violation[] | CheckOutcome): CheckOutcome {
  return Array.isArray(result) ? { violations: result } : result;
}

export interface LeafSpec {
  check: Check;
  produces: string[];
  sink: SensorSink;
  rules?: Rule[];
}

export function checkLeafSensor(spec: LeafSpec): Sensor {
  return {
    id: spec.check.id,
    produces: spec.produces,
    async run(ctx) {
      const outcome = normalizeOutcome(await spec.check.run(ctx.files, spec.rules ?? [], ctx.cwd));
      if (outcome.stderr) spec.sink.notices.push(...outcome.stderr);
      if (outcome.failures) spec.sink.failures.push(...outcome.failures);
      return outcome.violations.map(violationToIssue);
    },
  };
}

export interface PresetInput {
  sink: SensorSink;
  commentRule?: Rule;
}

// commentRule carries the resolved comment thresholds the ts-morph scan needs.
function commentSensor(input: PresetInput): Sensor {
  const rules = input.commentRule ? [input.commentRule] : [];
  return checkLeafSensor({ check: commentCheck, produces: [COMMENT_SMELL], sink: input.sink, rules });
}

// The TypeScript/JavaScript preset: leaf sensors over eslint, ts-morph comments,
// jscpd, and knip, plus the needs-extraction composite over oversized-file +
// duplicated-code.
export function buildPresetSensors(input: PresetInput): Sensor[] {
  const { sink } = input;
  return [
    checkLeafSensor({ check: eslintWrap, produces: ESLINT_PRODUCES, sink }),
    commentSensor(input),
    checkLeafSensor({ check: jscpdWrap, produces: [JSCPD_SMELL], sink }),
    checkLeafSensor({ check: knipWrap, produces: KNIP_PRODUCES, sink }),
    needsExtractionSensor(),
  ];
}
