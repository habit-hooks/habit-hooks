import type { SensorSink } from '../wrap/notices.js';
import type { Rule } from '../types.js';

export { checkLeafSensor, issueToViolation, violationToIssue } from './leaf.js';
export type { LeafSpec } from './leaf.js';

export interface PresetInput {
  sink: SensorSink;
  commentRule?: Rule;
}
