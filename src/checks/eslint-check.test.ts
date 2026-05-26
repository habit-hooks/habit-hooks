import { describe, expect, it } from 'vitest';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { eslintCheck } from './eslint-check.js';
import { getRules } from '../rules/registry.js';

const here = dirname(fileURLToPath(import.meta.url));
const fixturesDir = join(here, '..', '..', 'tests', 'fixtures');

describe('eslintCheck', () => {
  it('flags a max-params violation in a fixture file', async () => {
    const file = join(fixturesDir, 'max-params.ts');
    const violations = await eslintCheck.run([file], getRules());
    const maxParams = violations.filter((v) => v.ruleId === 'eslint:max-params');
    expect(maxParams.length).toBe(1);
    expect(maxParams[0]?.file).toBe(file);
    expect(maxParams[0]?.line).toBe(1);
  });

  it('returns no violations for a clean fixture', async () => {
    const file = join(fixturesDir, 'clean.ts');
    const violations = await eslintCheck.run([file], getRules());
    expect(violations).toEqual([]);
  });

  it('returns empty when no files supplied', async () => {
    const violations = await eslintCheck.run([], getRules());
    expect(violations).toEqual([]);
  });
});
