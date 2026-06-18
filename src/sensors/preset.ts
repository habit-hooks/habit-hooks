import { COMMENT_SMELL } from '../config/tool-smells.js';
import { buildDefaultSensors } from './registry.js';
import type { SensorSink } from '../wrap/notices.js';
import type { Rule } from '../types.js';
import type { Sensor } from './types.js';

export { checkLeafSensor, issueToViolation, violationToIssue } from './leaf.js';
export type { LeafSpec } from './leaf.js';

export interface PresetInput {
  sink: SensorSink;
  commentRule?: Rule;
}

// The TypeScript/JavaScript preset: leaf sensors over eslint, ts-morph comments,
// jscpd, and knip, plus the needs-extraction composite over oversized-file +
// duplicated-code. The sensors are constructed by the registry (src/sensors/registry.ts);
// this adapts the legacy signature by carrying the resolved comment rule.
export function buildPresetSensors(input: PresetInput): Sensor[] {
  const rulesById = input.commentRule ? new Map([[COMMENT_SMELL, input.commentRule]]) : new Map<string, Rule>();
  return buildDefaultSensors('typescript', { sink: input.sink, cwd: '', rulesById });
}
