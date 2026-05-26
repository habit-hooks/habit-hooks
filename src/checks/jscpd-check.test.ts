import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { jscpdCheck } from './jscpd-check.js';
import type { Rule } from '../types.js';

const RULE: Rule = {
  id: 'jscpd:duplication',
  source: 'jscpd',
  severity: 'suggested',
  changedFilesOnly: false,
  title: 'Duplicated code',
  description: '',
  eslintOptions: { minTokens: 20, minLines: 2 },
};

const DUPLICATE = `export function processOrder(order: { id: number; total: number }): number {
  const tax = order.total * 0.1;
  const shipping = order.total > 100 ? 0 : 10;
  const discount = order.total > 500 ? order.total * 0.05 : 0;
  return order.total + tax + shipping - discount;
}
`;

const CLEAN = `export function add(a: number, b: number): number {
  return a + b;
}
`;

function write(dir: string, name: string, content: string): string {
  const path = join(dir, name);
  writeFileSync(path, content);
  return path;
}

describe('jscpdCheck', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-jscpd-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  it('flags two near-identical files with violations naming partner locations', async () => {
    const a = write(dir, 'a.ts', DUPLICATE);
    const b = write(dir, 'b.ts', DUPLICATE);
    const violations = await jscpdCheck.run([a, b], [RULE]);
    expect(violations.length).toBeGreaterThanOrEqual(2);
    const aHit = violations.find((v) => v.file === a);
    const bHit = violations.find((v) => v.file === b);
    expect(aHit?.message).toContain(b);
    expect(bHit?.message).toContain(a);
  });

  it('returns no violations for a clean fixture', async () => {
    const a = write(dir, 'a.ts', CLEAN);
    const b = write(dir, 'b.ts', `export const x = 1;\n`);
    const violations = await jscpdCheck.run([a, b], [RULE]);
    expect(violations).toEqual([]);
  });

  it('returns empty when no files supplied', async () => {
    const violations = await jscpdCheck.run([], [RULE]);
    expect(violations).toEqual([]);
  });
});
