import { afterEach, describe, expect, it } from 'vitest';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { run } from './runner.js';

const here = dirname(fileURLToPath(import.meta.url));
const pythonProject = join(here, '..', 'tests', 'fixtures', 'python-project');

// The Python preset shells out to ruff and deptry; skip the e2e where the Python
// toolchain is absent (CI without it) so the suite stays green everywhere.
const PY_TOOLS =
  spawnSync('ruff', ['--version']).status === 0 && spawnSync('deptry', ['--version']).status === 0;

interface ExpectedCount {
  ruleId: string;
  count: number;
}

// Proves one mapper/guide vocabulary serves Python by swapping only the sensor
// layer: ruff -> complexity/params/unused-var/unused-import, jscpd -> duplicated
// code on .py, deptry -> unused-dependency.
const EXPECTED: ExpectedCount[] = [
  { ruleId: 'too-many-parameters', count: 1 },
  { ruleId: 'high-complexity', count: 1 },
  { ruleId: 'unused-variable', count: 1 },
  { ruleId: 'unused-import', count: 1 },
  { ruleId: 'duplicated-code', count: 2 },
  { ruleId: 'unused-dependency', count: 1 },
];

function countBy(violations: { ruleId: string }[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const v of violations) counts.set(v.ruleId, (counts.get(v.ruleId) ?? 0) + 1);
  return counts;
}

describe.skipIf(!PY_TOOLS)('acceptance: python preset on python-project fixture', () => {
  it('fires each expected python smell exactly once (duplicated-code twice)', async () => {
    const result = await run(pythonProject);
    const counts = countBy(result.violations);
    for (const { ruleId, count } of EXPECTED) {
      expect(counts.get(ruleId) ?? 0, `smell ${ruleId}`).toBe(count);
    }
  }, 30_000);

  it('exits non-zero because enforced python smells are present', async () => {
    expect((await run(pythonProject)).exitCode).toBe(1);
  }, 30_000);
});

// oversized-file is a pure line count (no ruff rule), so this runs without the
// Python toolchain — the ruff/deptry sensors simply find nothing.
describe('python oversized-file (line-count sensor)', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  function pythonProjectAt(maxModuleLines?: number): void {
    dir = mkdtempSync(join(tmpdir(), 'hh-py-oversized-'));
    writeFileSync(join(dir, 'habit-hooks.config.json'), JSON.stringify({ language: 'python' }));
    if (maxModuleLines !== undefined) {
      writeFileSync(join(dir, 'pyproject.toml'), `[tool.habit-hooks]\nmax-module-lines = ${String(maxModuleLines)}\n`);
    }
  }

  it('fires for a .py file over the configured max-module-lines threshold', async () => {
    pythonProjectAt(5);
    writeFileSync(join(dir, 'big.py'), `${Array.from({ length: 12 }, (_, i) => `a${String(i)} = ${String(i)}`).join('\n')}\n`);

    const result = await run(dir);

    expect(result.violations.some((v) => v.ruleId === 'oversized-file')).toBe(true);
  }, 30_000);

  it('does not fire for a small .py file at the default threshold', async () => {
    pythonProjectAt();
    writeFileSync(join(dir, 'small.py'), 'a = 1\nb = 2\n');

    const result = await run(dir);

    expect(result.violations.some((v) => v.ruleId === 'oversized-file')).toBe(false);
  }, 30_000);
});

const PY_BLOCK = `def NAME(order):
    tax = order.total * 0.1
    shipping = 0 if order.total > 100 else 10
    return order.total + tax + shipping
`;

// needs-extraction is a composite over oversized-file (line-count) + duplicated-code
// (jscpd). Both Python inputs run without ruff/deptry, so this needs no Python
// toolchain. Mirrors the TS needs-extraction end-to-end test.
describe('python needs-extraction (composite sensor)', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  function pythonProject(config?: unknown): void {
    dir = mkdtempSync(join(tmpdir(), 'hh-py-needs-extraction-'));
    writeFileSync(join(dir, 'habit-hooks.config.json'), JSON.stringify({ language: 'python', ...(config ?? {}) }));
    writeFileSync(join(dir, 'pyproject.toml'), '[tool.habit-hooks]\nmax-module-lines = 6\n');
    writeFileSync(join(dir, '.jscpd.json'), JSON.stringify({ minTokens: 20, minLines: 2 }));
    writeFileSync(join(dir, 'big.py'), PY_BLOCK.replace('NAME', 'alpha') + PY_BLOCK.replace('NAME', 'beta'));
  }

  function smellsOf(violations: { ruleId: string }[]): Set<string> {
    return new Set(violations.map((v) => v.ruleId));
  }

  it('fires needs-extraction through the real runner and augments by default', async () => {
    pythonProject();

    const smells = smellsOf((await run(dir)).violations);

    expect(smells.has('needs-extraction')).toBe(true);
    expect(smells.has('oversized-file')).toBe(true);
    expect(smells.has('duplicated-code')).toBe(true);
  }, 30_000);

  it('replace mode suppresses the input smells for the combined file', async () => {
    pythonProject({ needsExtraction: { replace: true } });

    const violations = (await run(dir)).violations;

    expect(violations.filter((v) => v.ruleId === 'needs-extraction').length).toBeGreaterThan(0);
    expect(violations.filter((v) => v.ruleId === 'oversized-file')).toEqual([]);
    expect(violations.filter((v) => v.ruleId === 'duplicated-code')).toEqual([]);
  }, 30_000);
});
