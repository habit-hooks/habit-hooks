import { buildDefaultSensors } from './registry.js';
import type { SensorSink } from '../wrap/notices.js';
import type { Rule } from '../types.js';
import type { Sensor } from './types.js';

// The Python preset: ruff (declarative adapter) + jscpd on .py + deptry + line-count,
// plus the needs-extraction composite over oversized-file (line-count) + duplicated-code (jscpd).
// The sensors are constructed by the registry (src/sensors/registry.ts); this only
// adapts the legacy signature.
export interface PythonPresetInput {
  sink: SensorSink;
  cwd: string;
}

export function buildPythonPresetSensors(input: PythonPresetInput): Sensor[] {
  return buildDefaultSensors('python', { sink: input.sink, cwd: input.cwd, rulesById: new Map<string, Rule>() });
}
