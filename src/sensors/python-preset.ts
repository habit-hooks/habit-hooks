import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { jscpdWrap } from '../checks/jscpd-wrap.js';
import { TOOL_CONFIG_FILENAMES } from '../detect/tool.js';
import type { SensorSink } from '../wrap/notices.js';
import { JSCPD_SMELL, RUFF_SPEC } from '../config/tool-smells.js';
import { declarativeSensor } from './adapter.js';
import { checkLeafSensor } from './preset.js';
import { deptrySensor } from './deptry-sensor.js';
import { DEFAULT_MAX_FILE_LINES, lineCountSensor } from './line-count-sensor.js';
import type { Sensor } from './types.js';

// The Python preset: ruff (declarative adapter) + jscpd on .py + deptry + line-count.
// Ruff/deptry specs and smell ids come from config/tool-smells.ts; this only wires them.
export interface PythonPresetInput {
  sink: SensorSink;
  cwd: string;
}

// `oversized-file` has no ruff rule (ruff 0.15 has no C0302 port and rejects an
// unknown `max-module-lines` key under `[tool.ruff]`), so the threshold is read
// from the consumer's config text by the same no-TOML-parser approach the init
// drift-check uses; defaults to 200, matching the TS `max-lines`.
function readMaxModuleLines(cwd: string): number {
  const sources = [...TOOL_CONFIG_FILENAMES.ruff, 'pyproject.toml'];
  const text = sources.map((name) => readTextOrEmpty(join(cwd, name))).join('\n');
  const match = text.match(/max-module-lines\s*=\s*(\d+)/);
  return match ? Number(match[1]) : DEFAULT_MAX_FILE_LINES;
}

function readTextOrEmpty(path: string): string {
  return existsSync(path) ? readFileSync(path, 'utf8') : '';
}

export function buildPythonPresetSensors(input: PythonPresetInput): Sensor[] {
  const { sink, cwd } = input;
  return [
    declarativeSensor(RUFF_SPEC, sink),
    checkLeafSensor({ check: jscpdWrap, produces: [JSCPD_SMELL], sink }),
    deptrySensor(sink),
    lineCountSensor(readMaxModuleLines(cwd)),
  ];
}
