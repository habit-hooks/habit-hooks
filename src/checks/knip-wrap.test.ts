import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { chmodSync, mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildKnipArgs, consumerKnipMajor, knipWrap, resolveKnipBin } from './knip-wrap.js';
import type { CheckOutcome, Rule } from '../types.js';

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = join(here, '..', '..');
const repoNodeModules = join(repoRoot, 'node_modules');

const RULES: Rule[] = [];

function makeTempDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-knip-wrap-'));
}

function linkNodeModules(cwd: string): void {
  symlinkSync(repoNodeModules, join(cwd, 'node_modules'), 'dir');
}

function writeFile(cwd: string, rel: string, contents: string): string {
  const full = join(cwd, rel);
  mkdirSync(dirname(full), { recursive: true });
  writeFileSync(full, contents);
  return full;
}

function writeKnipProject(cwd: string): { main: string; foo: string } {
  writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
  writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/main.ts'], project: ['src/**/*.ts'] }));
  const main = writeFile(
    cwd,
    'src/main.ts',
    "import { Foo } from './foo.ts';\nconst foo = new Foo();\nconsole.log(foo.used());\n",
  );
  const foo = writeFile(
    cwd,
    'src/foo.ts',
    'export class Foo {\n  used(): number {\n    return 1;\n  }\n  unused(): number {\n    return 2;\n  }\n}\n',
  );
  return { main, foo };
}

function asOutcome(result: Awaited<ReturnType<typeof knipWrap.run>>): CheckOutcome {
  if (Array.isArray(result)) return { violations: result, stderr: [] };
  return result;
}

async function runWrap(cwd: string, files: string[]): Promise<CheckOutcome> {
  return asOutcome(await knipWrap.run(files, RULES, cwd));
}

describe('knipWrap', () => {
  let cwd: string;

  beforeEach(() => {
    cwd = makeTempDir();
  });
  afterEach(() => {
    rmSync(cwd, { recursive: true, force: true });
  });

  it('returns knip-prefixed violations when consumer knip reports issues', async () => {
    linkNodeModules(cwd);
    const { main, foo } = writeKnipProject(cwd);

    const outcome = await runWrap(cwd, [main, foo]);

    expect(outcome.violations.some((v) => v.ruleId === 'knip:classMembers' && v.file === foo)).toBe(true);
    expect(outcome.stderr).toEqual([]);
  }, 30_000);

  it('emits a single fallback stderr notice when no consumer knip is installed', async () => {
    const { main, foo } = writeKnipProject(cwd);

    const outcome = await runWrap(cwd, [main, foo]);

    expect(outcome.stderr?.[0]).toContain('using bundled knip');
    expect(outcome.violations.length).toBeGreaterThan(0);
  }, 30_000);

  it('warns and returns no violations when no package.json is present', async () => {
    linkNodeModules(cwd);
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toEqual([]);
    expect(outcome.stderr?.some((s) => s.includes('no package.json'))).toBe(true);
  });

  it('runs whole-project when any files are given and reports all violations', async () => {
    linkNodeModules(cwd);
    const { main } = writeKnipProject(cwd);

    const outcome = await runWrap(cwd, [main]);

    expect(outcome.violations.some((v) => v.ruleId === 'knip:classMembers')).toBe(true);
  }, 30_000);

  it('skips invocation entirely when file list is empty', async () => {
    linkNodeModules(cwd);
    writeKnipProject(cwd);

    const outcome = await runWrap(cwd, []);

    expect(outcome).toEqual({ violations: [], stderr: [] });
  });

  it('emits a knip:files violation for top-level report.files entries', async () => {
    linkNodeModules(cwd);
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/main.ts'], project: ['src/**/*.ts'] }));
    const main = writeFile(cwd, 'src/main.ts', "console.log('hi');\n");
    const orphan = writeFile(cwd, 'src/orphan.ts', 'export const orphan = 1;\n');

    const outcome = await runWrap(cwd, [main, orphan]);

    const filesViolation = outcome.violations.find((v) => v.ruleId === 'knip:files');
    expect(filesViolation).toBeDefined();
    expect(filesViolation?.file).toBe(orphan);
  }, 30_000);

  it('surfaces unknown knip issue types as uncoached violations (forward-compat)', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = {
      files: [],
      issues: [{ file: 'src/a.ts', unlistedPeerDependencies: [{ name: 'left-pad', line: 3 }] }],
    };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toHaveLength(1);
    const v = outcome.violations[0]!;
    expect(v.ruleId).toBe('knip:unlistedPeerDependencies');
    expect(v.file).toBe(file);
    expect(v.message).toBe('unrecognised knip issue type');
    expect(outcome.stderr).toEqual([]);
  });

  it('ignores empty unknown keys to avoid noise', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = { files: [], issues: [{ file: 'src/a.ts', newEmptyKey: [], anotherEmpty: {} }] };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toEqual([]);
  });

  it('produces a violation when an unknown key holds a populated record (member-map shape)', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = {
      files: [],
      issues: [{ file: 'src/a.ts', someFutureMemberMap: { Foo: [{ name: 'bar', line: 2 }] } }],
    };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toHaveLength(1);
    const v = outcome.violations[0]!;
    expect(v.ruleId).toBe('knip:someFutureMemberMap');
    expect(v.file).toBe(file);
    expect(v.message).toBe('unrecognised knip issue type');
  });

  it('emits one violation per unknown key when an issue has multiple', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = {
      files: [],
      issues: [
        {
          file: 'src/a.ts',
          unlistedPeerDependencies: [{ name: 'left-pad', line: 3 }],
          someFutureType: [{ name: 'other', line: 5 }],
        },
      ],
    };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toHaveLength(2);
    const ruleIds = outcome.violations.map((v) => v.ruleId).sort();
    expect(ruleIds).toEqual(['knip:someFutureType', 'knip:unlistedPeerDependencies']);
  });

  it('unknown knip issue types flow through reporter as uncoached', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = {
      files: [],
      issues: [{ file: 'src/a.ts', newKnipIssueType: [{ name: 'thing', line: 5 }] }],
    };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);
    const { report } = await import('../reporter.js');
    const reported = report(outcome.violations, []);

    expect(reported.stdout).toContain('Uncoached rules');
    expect(reported.stdout).toContain('knip:newKnipIssueType');
    expect(reported.exitCode).toBe(0);
  });

  it('emits a knip:files violation for per-issue files entries (knip 6 shape)', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = { files: [], issues: [{ file: 'src/walk.ts', files: [{ name: 'src/walk.ts' }] }] };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/walk.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/walk.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toHaveLength(1);
    const v = outcome.violations[0]!;
    expect(v.ruleId).toBe('knip:files');
    expect(v.message).toContain('src/walk.ts');
    expect(v.message).not.toContain('unrecognised');
  });

  it('emits knip:namespaceMembers violations for namespace member maps (knip 6 shape)', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const payload = {
      files: [],
      issues: [{ file: 'src/foo.ts', namespaceMembers: { Mod: [{ name: 'unused', line: 2 }] } }],
    };
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nprocess.stdout.write(${JSON.stringify(JSON.stringify(payload))});\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'stub.js' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/foo.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/foo.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toHaveLength(1);
    const v = outcome.violations[0]!;
    expect(v.ruleId).toBe('knip:namespaceMembers');
    expect(v.message).toContain('Mod.unused');
  });

  it('emits a spawn-failure stderr notice when the knip binary cannot be executed', async () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    const fakeBin = writeFile(cwd, 'node_modules/knip/knip-broken', 'not-executable');
    chmodSync(fakeBin, 0o644);
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ bin: { knip: 'knip-broken' } }));
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toEqual([]);
    expect(outcome.stderr?.some((s) => s.includes('knip skipped') && /EACCES|spawn/i.test(s))).toBe(true);
  });

  it('emits a skip stderr notice when no knip config file exists', async () => {
    linkNodeModules(cwd);
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.violations).toEqual([]);
    expect(outcome.stderr?.some((s) => s.includes('no knip config'))).toBe(true);
  });

  it('runs when knip config is supplied via package.json#knip', async () => {
    linkNodeModules(cwd);
    const pkg = {
      name: 'fixture',
      version: '0.0.0',
      type: 'module',
      knip: { entry: ['src/main.ts'], project: ['src/**/*.ts'] },
    };
    writeFile(cwd, 'package.json', JSON.stringify(pkg));
    const main = writeFile(
      cwd,
      'src/main.ts',
      "import { Foo } from './foo.ts';\nconst foo = new Foo();\nconsole.log(foo.used());\n",
    );
    const foo = writeFile(
      cwd,
      'src/foo.ts',
      'export class Foo {\n  used(): number {\n    return 1;\n  }\n  unused(): number {\n    return 2;\n  }\n}\n',
    );

    const outcome = await runWrap(cwd, [main, foo]);

    expect(outcome.violations.some((v) => v.ruleId === 'knip:classMembers')).toBe(true);
  }, 30_000);

  function installFakeKnip(version: string): void {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    writeFileSync(join(knipDir, 'package.json'), JSON.stringify({ name: 'knip', version, bin: { knip: 'stub.js' } }));
  }

  function installArgvRecorderKnip(version: string): string {
    installFakeKnip(version);
    const argvFile = join(cwd, 'argv.json');
    const stub = writeFile(
      cwd,
      'node_modules/knip/stub.js',
      `#!/usr/bin/env node\nimport { writeFileSync } from 'node:fs';\nwriteFileSync(${JSON.stringify(argvFile)}, JSON.stringify(process.argv.slice(2)));\nprocess.stdout.write('{"files":[],"issues":[]}');\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    return argvFile;
  }

  it('consumerKnipMajor returns the major version when package.json is valid', () => {
    installFakeKnip('6.4.2');
    expect(consumerKnipMajor(cwd)).toBe(6);
  });

  it('consumerKnipMajor returns null when the file is missing', () => {
    expect(consumerKnipMajor(cwd)).toBeNull();
  });

  it('consumerKnipMajor returns null when the file is unparseable JSON', () => {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    writeFileSync(join(knipDir, 'package.json'), '{not valid json');
    expect(consumerKnipMajor(cwd)).toBeNull();
  });

  it('omits --include classMembers when consumer knip is v6+', async () => {
    const argvFile = installArgvRecorderKnip('6.0.0');
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    await runWrap(cwd, [file]);

    const argv = JSON.parse(readFileSync(argvFile, 'utf8')) as string[];
    expect(argv).not.toContain('classMembers');
    expect(argv).toEqual(['--reporter', 'json', '--no-exit-code']);
  });

  it('includes --include classMembers when consumer knip is v5', async () => {
    const argvFile = installArgvRecorderKnip('5.88.1');
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    await runWrap(cwd, [file]);

    const argv = JSON.parse(readFileSync(argvFile, 'utf8')) as string[];
    expect(argv).toEqual(['--reporter', 'json', '--no-exit-code', '--include', 'classMembers']);
  });

  it('falls back to bundled knip version when no consumer knip is installed', () => {
    const resolution = resolveKnipBin(cwd);
    const args = buildKnipArgs(resolution, cwd);
    expect(resolution.isFallback).toBe(true);
    expect(args).toContain('classMembers');
  });
});
