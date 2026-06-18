import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { eslintWrap } from '../checks/eslint-wrap.js';
import { commentCheck } from '../checks/comment-check.js';
import { jscpdWrap } from '../checks/jscpd-wrap.js';
import { knipWrap } from '../checks/knip-wrap.js';
import { TOOL_CONFIG_FILENAMES } from '../detect/tool.js';
import type { SensorSink } from '../wrap/notices.js';
import {
  COMMENT_SMELL,
  ESLINT_PRODUCES,
  JSCPD_SMELL,
  KNIP_PRODUCES,
  RUFF_SPEC,
} from '../config/tool-smells.js';
import { declarativeSensor } from './adapter.js';
import { checkLeafSensor } from './leaf.js';
import { deptrySensor } from './deptry-sensor.js';
import { DEFAULT_MAX_FILE_LINES, lineCountSensor } from './line-count-sensor.js';
import { needsExtractionSensor } from './needs-extraction.js';
import type { Sensor } from './types.js';
import type { Rule } from '../types.js';

// The single source of truth for code-backed (built-in) sensors: every preset is
// a list of ids resolved through this registry, so a sensor is constructed in
// exactly one place (issue #16).

export interface SensorFactoryInput {
  sink: SensorSink;
  cwd: string;
  rulesById: Map<string, Rule>;
}

export type SensorFactory = (_input: SensorFactoryInput) => Sensor;

function readTextOrEmpty(path: string): string {
  return existsSync(path) ? readFileSync(path, 'utf8') : '';
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

const registry = new Map<string, SensorFactory>([
  ['eslint', ({ sink }) => checkLeafSensor({ check: eslintWrap, produces: ESLINT_PRODUCES, sink })],
  [
    'comment',
    ({ sink, rulesById }) => {
      const rule = rulesById.get(COMMENT_SMELL);
      return checkLeafSensor({ check: commentCheck, produces: [COMMENT_SMELL], sink, rules: rule ? [rule] : [] });
    },
  ],
  ['jscpd', ({ sink }) => checkLeafSensor({ check: jscpdWrap, produces: [JSCPD_SMELL], sink })],
  ['knip', ({ sink }) => checkLeafSensor({ check: knipWrap, produces: KNIP_PRODUCES, sink })],
  ['ruff', ({ sink }) => declarativeSensor(RUFF_SPEC, sink)],
  ['deptry', ({ sink }) => deptrySensor(sink)],
  ['line-count', ({ cwd }) => lineCountSensor(readMaxModuleLines(cwd))],
  ['needs-extraction', () => needsExtractionSensor()],
]);

const DEFAULT_SENSOR_IDS: Record<string, string[]> = {
  typescript: ['eslint', 'comment', 'jscpd', 'knip', 'needs-extraction'],
  python: ['ruff', 'jscpd', 'deptry', 'line-count', 'needs-extraction'],
};

export function defaultSensorIds(language: string): string[] {
  return DEFAULT_SENSOR_IDS[language] ?? [];
}

export function buildDefaultSensors(language: string, input: SensorFactoryInput): Sensor[] {
  return defaultSensorIds(language).map((id) => {
    const factory = registry.get(id);
    if (!factory) throw new Error(`No sensor factory registered for id "${id}"`);
    return factory(input);
  });
}
