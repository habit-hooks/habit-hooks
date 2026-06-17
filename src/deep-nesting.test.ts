import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run } from './runner.js';

const NESTED = `export function deep(items) {
  for (const a of items) {
    if (a > 0) {
      while (a < 100) {
        if (a % 2 === 0) {
          return a;
        }
      }
    }
  }
  return 0;
}
`;

describe('deep-nesting smell (eslint max-depth)', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  function setup(maxDepth: number): void {
    dir = mkdtempSync(join(tmpdir(), 'hh-deep-nesting-'));
    writeFileSync(
      join(dir, 'eslint.config.js'),
      `export default [{ languageOptions: { sourceType: 'module', ecmaVersion: 2022 }, rules: { 'max-depth': ['error', { max: ${String(maxDepth)} }] } }];\n`,
    );
    writeFileSync(join(dir, 'nested.js'), NESTED);
  }

  it('fires deep-nesting end-to-end when nesting exceeds the configured threshold', async () => {
    setup(2);
    expect((await run(dir)).violations.some((v) => v.ruleId === 'deep-nesting')).toBe(true);
  });

  it('does not fire when nesting is within the configured threshold', async () => {
    setup(6);
    expect((await run(dir)).violations.some((v) => v.ruleId === 'deep-nesting')).toBe(false);
  });
});
