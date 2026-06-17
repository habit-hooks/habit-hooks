import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { buildPythonPresetSensors } from './python-preset.js';

// The live ruff test needs ruff on PATH; skip where it is not installed (CI
// without the Python toolchain) so the suite stays green everywhere.
const RUFF_AVAILABLE = spawnSync('ruff', ['--version']).status === 0;

const SAMPLE = `def handler(a, b, c, d, e, f):
    unused = 42
    return a + b + c + d + e + f
`;

describe('python preset', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-py-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  it('registers ruff, jscpd, deptry, line-count, and needs-extraction sensors with their smell keys', () => {
    const sensors = buildPythonPresetSensors({ sink: { notices: [], failures: [] }, cwd: dir });
    expect(sensors.map((s) => s.id)).toEqual(['ruff', 'jscpd', 'deptry', 'line-count', 'needs-extraction']);
    expect(sensors[0]?.produces).toContain('too-many-parameters');
    expect(sensors[2]?.produces).toEqual(['unused-dependency']);
    expect(sensors[3]?.produces).toEqual(['oversized-file']);
    expect(sensors[4]?.produces).toEqual(['needs-extraction']);
    expect(sensors[4]?.dependsOn).toEqual(['oversized-file', 'duplicated-code']);
  });

  it.skipIf(!RUFF_AVAILABLE)('runs ruff and maps PLR0913/F841 to canonical smells with provenance', async () => {
    const file = join(dir, 'sample.py');
    writeFileSync(file, SAMPLE);
    const ruff = buildPythonPresetSensors({ sink: { notices: [], failures: [] }, cwd: dir })[0];
    if (ruff === undefined) throw new Error('expected ruff sensor');

    const issues = await ruff.run({ files: [file], cwd: dir, deps: [] });

    const smells = new Set(issues.map((i) => i.smell));
    expect(smells.has('too-many-parameters')).toBe(true);
    expect(smells.has('unused-variable')).toBe(true);
    const params = issues.find((i) => i.smell === 'too-many-parameters');
    expect(params?.details.source).toBe('ruff:PLR0913');
    expect(params?.details.file).toBe(file);
  }, 30_000);

  it('records a failure and a notice (zero issues) when ruff cannot spawn', async () => {
    const sink = { notices: [] as string[], failures: [] as string[] };
    const ruff = buildPythonPresetSensors({ sink, cwd: dir })[0];
    if (ruff === undefined) throw new Error('expected ruff sensor');
    const file = join(dir, 'a.py');
    writeFileSync(file, 'x = 1\n');

    const issues = await ruff.run({ files: [file], cwd: '/nonexistent-path-xyz', deps: [] });

    expect(issues).toEqual([]);
    expect(sink.failures).toHaveLength(1);
    expect(sink.failures[0]).toContain('ruff');
    expect(sink.notices).toContain(sink.failures[0]);
  }, 30_000);
});
