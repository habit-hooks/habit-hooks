import { readFileSync } from 'node:fs';
import fg from 'fast-glob';
import { describe, test } from 'vitest';
import { parseSpec, type Example } from '../../tests/helpers/spec-md/parser.js';
import { checkUnit, runUnit } from '../../tests/helpers/spec-md/runner.js';

const cwd = process.cwd();
const specFiles = fg.sync('docs/**/*.spec.md', { cwd });

function registerExample(file: string, example: Example): void {
  if (example.units.length === 0) return;
  test(`${file} › ${example.title}`, async ({ expect }) => {
    for (const unit of example.units) {
      const result = await runUnit(unit, { cwd });
      const check = checkUnit(unit, result);
      expect(check.ok, check.ok ? '' : check.message).toBe(true);
    }
  });
}

for (const file of specFiles) {
  const examples = parseSpec(readFileSync(file, 'utf8'));
  describe(file, () => {
    for (const example of examples) registerExample(file, example);
  });
}
