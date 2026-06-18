import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { defaultSensorIds } from '../sensors/registry.js';

// Guards docs/sensors.md against drift from the implemented config shapes
// (issue #16, acceptance criterion 3): no documented-but-missing config fields,
// and no documented `use` id that is not a real built-in sensor.
const docPath = join(dirname(fileURLToPath(import.meta.url)), '../../docs/sensors.md');
const doc = readFileSync(docPath, 'utf8');

// The real built-in sensor ids, sourced from the registry rather than hardcoded
// here so adding/removing a built-in only needs the registry edited.
const builtinIds = new Set([...defaultSensorIds('typescript'), ...defaultSensorIds('python')]);

// The real config fields on HabitHooksConfig + the SensorSpec union (schema.ts).
// TS types cannot be reflected at runtime, so this list mirrors them by hand;
// keep it in sync with src/config/schema.ts.
const realConfigFields = [
  'sensors',
  'files',
  'language',
  'smells',
  'use',
  'command',
  'produces',
  'dependsOn',
  'items',
  'fields',
  'group',
  'map',
];

// Field names that never existed / were removed — a doc edit reintroducing one
// is the exact drift this test catches.
const phantomFields = ['checks', 'tools', 'sensorList', 'detectors', 'plugins', 'globs', 'patterns'];

// True when the doc mentions the field name inside backticks, either bare
// (`files`) or as the head of a config path (`smells.<smell>`, `sensors.<id>`).
function mentionsField(field: string): boolean {
  const pattern = new RegExp('`' + field + '(?:\\b|\\.)', 'i');
  return pattern.test(doc);
}

function backtickedUseIds(): string[] {
  const ids = new Set<string>();
  const useEntry = /"use":\s*"([^"]+)"/g;
  for (const match of doc.matchAll(useEntry)) ids.add(match[1]);
  return [...ids];
}

describe('docs/sensors.md honesty', () => {
  it('only references real built-in sensor ids in `use` entries', () => {
    for (const id of backtickedUseIds()) {
      expect(builtinIds, `doc references unknown built-in sensor id "${id}"`).toContain(id);
    }
  });

  it('documents every real config field name', () => {
    for (const field of realConfigFields) {
      expect(mentionsField(field), `doc no longer mentions config field "${field}"`).toBe(true);
    }
  });

  it('does not reintroduce phantom config fields', () => {
    for (const field of phantomFields) {
      expect(doc, `doc reintroduced a phantom config field "${field}"`).not.toContain(`\`${field}\``);
    }
  });

  it('lists the full preset id set so a consumer can copy a complete default block', () => {
    for (const id of builtinIds) {
      expect(doc, `preset block missing built-in sensor "${id}"`).toContain(`"use": "${id}"`);
    }
  });
});
