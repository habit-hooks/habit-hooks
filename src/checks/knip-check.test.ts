import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { knipCheck } from './knip-check.js';
import type { Rule } from '../types.js';

const RULE: Rule = {
  id: 'knip:unused-class-members',
  source: 'knip',
  severity: 'enforced',
  changedFilesOnly: false,
  title: 'Unused class member',
  description: '',
};

function writeProject(dir: string): { main: string; foo: string } {
  mkdirSync(join(dir, 'src'), { recursive: true });
  writeFileSync(
    join(dir, 'package.json'),
    JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }),
  );
  writeFileSync(
    join(dir, 'knip.json'),
    JSON.stringify({ entry: ['src/main.ts'], project: ['src/**/*.ts'] }),
  );
  const main = join(dir, 'src', 'main.ts');
  const foo = join(dir, 'src', 'foo.ts');
  writeFileSync(
    main,
    `import { Foo } from './foo.ts';\nconst foo = new Foo();\nconsole.log(foo.used());\n`,
  );
  writeFileSync(
    foo,
    `export class Foo {\n  used(): number {\n    return 1;\n  }\n  unused(): number {\n    return 2;\n  }\n}\n`,
  );
  return { main, foo };
}

describe('knipCheck', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-knip-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  it('reports exactly one violation on the unused class member', async () => {
    const { main, foo } = writeProject(dir);
    const violations = await knipCheck.run([main, foo], [RULE], dir);
    expect(violations).toHaveLength(1);
    expect(violations[0]?.file).toBe(foo);
    expect(violations[0]?.message).toContain('Foo.unused');
  }, 30_000);

  it('returns empty when no files supplied', async () => {
    const violations = await knipCheck.run([], [RULE], dir);
    expect(violations).toEqual([]);
  });
});
