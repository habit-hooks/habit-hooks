import type { SensorSink } from '../wrap/notices.js';
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
