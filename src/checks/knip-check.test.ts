import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { chmodSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createKnipCheck, knipCheck } from './knip-check.js';
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

  it('warns loudly and returns [] when knip exits 0 with stderr only', async () => {
    const { main, foo } = writeProject(dir);
    const stub = join(dir, 'stub-knip.js');
    writeFileSync(
      stub,
      `#!/usr/bin/env node\nprocess.stderr.write('ERROR: Invalid issue type: classMembers\\n');\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    const check = createKnipCheck({ resolveBin: () => stub });
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true);
    try {
      const violations = await check.run([main, foo], [RULE], dir);
      expect(violations).toEqual([]);
      const warnings = spy.mock.calls
        .map((c) => String(c[0]))
        .filter((s) => s.includes('habit-hooks: knip:unused-class-members'));
      expect(warnings.length).toBeGreaterThan(0);
      expect(warnings[0]).toContain(dir);
      expect(warnings[0]).toContain('ERROR: Invalid issue type: classMembers');
    } finally {
      spy.mockRestore();
    }
  });

  it('warns loudly and returns [] when knip exits non-zero', async () => {
    const { main, foo } = writeProject(dir);
    const stub = join(dir, 'stub-knip.js');
    writeFileSync(
      stub,
      `#!/usr/bin/env node\nprocess.stderr.write('boom: knip blew up\\n');\nprocess.exit(2);\n`,
    );
    chmodSync(stub, 0o755);
    const check = createKnipCheck({ resolveBin: () => stub });
    const spy = vi.spyOn(process.stderr, 'write').mockImplementation(() => true);
    try {
      const violations = await check.run([main, foo], [RULE], dir);
      expect(violations).toEqual([]);
      const warnings = spy.mock.calls
        .map((c) => String(c[0]))
        .filter((s) => s.includes('habit-hooks: knip:unused-class-members'));
      expect(warnings.length).toBeGreaterThan(0);
      expect(warnings[0]).toContain(dir);
      expect(warnings[0]).toContain('boom: knip blew up');
    } finally {
      spy.mockRestore();
    }
  });
});
