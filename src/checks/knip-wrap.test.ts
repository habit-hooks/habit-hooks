import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { chmodSync, existsSync, mkdtempSync, mkdirSync, readFileSync, rmSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { knipWrap } from './knip-wrap.js';
import { buildKnipArgs, resolveKnipBin } from './knip-resolve.js';
import { combineProductionPass, type DefaultRun, type KnipPass } from './knip-merge.js';
import type { CheckOutcome, Rule, Violation } from '../types.js';

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

    expect(outcome.violations.some((v) => v.ruleId === 'unused-class-member' && v.file === foo)).toBe(true);
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

    expect(outcome.violations.some((v) => v.ruleId === 'unused-class-member')).toBe(true);
  }, 30_000);

  it('skips invocation entirely when file list is empty', async () => {
    linkNodeModules(cwd);
    writeKnipProject(cwd);

    const outcome = await runWrap(cwd, []);

    expect(outcome).toEqual({ violations: [], stderr: [] });
  });

  it('emits an unused-file violation for top-level report.files entries', async () => {
    linkNodeModules(cwd);
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/main.ts'], project: ['src/**/*.ts'] }));
    const main = writeFile(cwd, 'src/main.ts', "console.log('hi');\n");
    const orphan = writeFile(cwd, 'src/orphan.ts', 'export const orphan = 1;\n');

    const outcome = await runWrap(cwd, [main, orphan]);

    const filesViolation = outcome.violations.find((v) => v.ruleId === 'unused-file');
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
    const [v] = outcome.violations;
    if (v === undefined) throw new Error('expected one violation');
    expect(v.ruleId).toBe('unlistedPeerDependencies');
    expect(v.source).toBe('knip:unlistedPeerDependencies');
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
    const [v] = outcome.violations;
    if (v === undefined) throw new Error('expected one violation');
    expect(v.ruleId).toBe('someFutureMemberMap');
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
    expect(ruleIds).toEqual(['someFutureType', 'unlistedPeerDependencies']);
  });

  it('surfaces an unknown knip issue type as a bare-key smell with knip provenance', async () => {
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

    expect(outcome.violations).toHaveLength(1);
    const [v] = outcome.violations;
    if (v === undefined) throw new Error('expected one violation');
    expect(v.ruleId).toBe('newKnipIssueType');
    expect(v.source).toBe('knip:newKnipIssueType');
  });

  it('emits an unused-file violation for per-issue files entries (knip 6 shape)', async () => {
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
    const [v] = outcome.violations;
    if (v === undefined) throw new Error('expected one violation');
    expect(v.ruleId).toBe('unused-file');
    expect(v.source).toBe('knip:files');
    expect(v.message).toContain('src/walk.ts');
    expect(v.message).not.toContain('unrecognised');
  });

  it('emits namespaceMembers violations for namespace member maps (knip 6 shape)', async () => {
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
    const [v] = outcome.violations;
    if (v === undefined) throw new Error('expected one violation');
    expect(v.ruleId).toBe('namespaceMembers');
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

  it('does not skip when a knip.js config file exists', async () => {
    const argvFile = installArgvRecorderKnip('6.0.0');
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.js', 'export default { entry: ["src/a.ts"], project: ["src/**/*.ts"] };\n');
    const file = writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');

    const outcome = await runWrap(cwd, [file]);

    expect(outcome.stderr?.some((s) => s.includes('no knip config'))).toBe(false);
    expect(existsSync(argvFile)).toBe(true);
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

    expect(outcome.violations.some((v) => v.ruleId === 'unused-class-member')).toBe(true);
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

  // Records the argv knip receives via a .bin/knip shim, so the consumer knip
  // bin resolves regardless of what its own package.json says. This lets us
  // exercise consumer-version detection (consumerKnipMajor, reached transitively
  // via knipWrap -> buildKnipArgs) through the public entry point while
  // controlling node_modules/knip/package.json independently of the bin.
  function installBinShimRecorder(): string {
    const argvFile = join(cwd, 'argv.json');
    const stub = writeFile(
      cwd,
      'node_modules/.bin/knip',
      `#!/usr/bin/env node\nimport { writeFileSync } from 'node:fs';\nwriteFileSync(${JSON.stringify(argvFile)}, JSON.stringify(process.argv.slice(2)));\nprocess.stdout.write('{"files":[],"issues":[]}');\nprocess.exit(0);\n`,
    );
    chmodSync(stub, 0o755);
    return argvFile;
  }

  function writeConsumerProject(): string {
    writeFile(cwd, 'package.json', JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module' }));
    writeFile(cwd, 'knip.json', JSON.stringify({ entry: ['src/a.ts'], project: ['src/**/*.ts'] }));
    return writeFile(cwd, 'src/a.ts', 'export const a = 1;\n');
  }

  function writeConsumerKnipPackageJson(contents: string): void {
    const knipDir = join(cwd, 'node_modules', 'knip');
    mkdirSync(knipDir, { recursive: true });
    writeFileSync(join(knipDir, 'package.json'), contents);
  }

  it('detects consumer knip major version (omits classMembers for v6) via the wrap', async () => {
    const argvFile = installBinShimRecorder();
    writeConsumerKnipPackageJson(JSON.stringify({ name: 'knip', version: '6.4.2' }));
    const file = writeConsumerProject();

    await runWrap(cwd, [file]);

    const argv = JSON.parse(readFileSync(argvFile, 'utf8')) as string[];
    expect(argv).not.toContain('classMembers');
  });

  it('treats a missing consumer knip package.json as v5 (adds classMembers) via the wrap', async () => {
    const argvFile = installBinShimRecorder();
    const file = writeConsumerProject();

    await runWrap(cwd, [file]);

    const argv = JSON.parse(readFileSync(argvFile, 'utf8')) as string[];
    expect(argv).toContain('classMembers');
  });

  it('treats an unparseable consumer knip package.json as v5 (adds classMembers) via the wrap', async () => {
    const argvFile = installBinShimRecorder();
    writeConsumerKnipPackageJson('{not valid json');
    const file = writeConsumerProject();

    await runWrap(cwd, [file]);

    const argv = JSON.parse(readFileSync(argvFile, 'utf8')) as string[];
    expect(argv).toContain('classMembers');
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

  function writeProductionFixture(dir: string): void {
    writeFile(
      dir,
      'package.json',
      JSON.stringify({ name: 'fixture', version: '0.0.0', type: 'module', devDependencies: { 'is-odd': '^3.0.0' } }),
    );
    writeFile(
      dir,
      'knip.json',
      JSON.stringify({ entry: ['src/index.ts!', 'tests/**/*.test.ts'], project: ['src/**/*.ts!', 'tests/**/*.ts'] }),
    );
    writeFile(
      dir,
      'src/lib.ts',
      'export const usedByProd = 1;\nexport const usedByTestOnly = 2;\nexport const trulyDead = 3;\n',
    );
    writeFile(dir, 'src/index.ts', "import { usedByProd } from './lib.ts';\nconsole.log(usedByProd);\n");
    writeFile(dir, 'tests/helpers.ts', 'export const makeFoo = () => 1;\nexport const deadHelper = () => 2;\n');
    writeFile(
      dir,
      'tests/lib.test.ts',
      "import { usedByTestOnly } from '../src/lib.ts';\nimport { makeFoo } from './helpers.ts';\nconsole.log(usedByTestOnly, makeFoo());\n",
    );
  }

  function hasUnusedExport(violations: Violation[], file: string, name: string): boolean {
    return violations.some((v) => v.source === 'knip:exports' && v.file === file && v.message === name);
  }

  it('merges production-pass dead-code findings while keeping default-run dependency findings', async () => {
    linkNodeModules(cwd);
    writeProductionFixture(cwd);
    const lib = join(cwd, 'src/lib.ts');
    const helpers = join(cwd, 'tests/helpers.ts');

    const outcome = await runWrap(cwd, [join(cwd, 'src/index.ts')]);

    expect(hasUnusedExport(outcome.violations, lib, 'usedByTestOnly')).toBe(true);
    expect(hasUnusedExport(outcome.violations, lib, 'trulyDead')).toBe(true);
    expect(hasUnusedExport(outcome.violations, helpers, 'deadHelper')).toBe(true);
    expect(outcome.violations.some((v) => v.source === 'knip:devDependencies' && v.message === 'is-odd')).toBe(true);

    const trulyDeadCount = outcome.violations.filter(
      (v) => v.source === 'knip:exports' && v.file === lib && v.message === 'trulyDead',
    ).length;
    expect(trulyDeadCount).toBe(1);
  }, 60_000);
});

function okPass(violations: Violation[]): KnipPass {
  return { kind: 'ok', violations };
}

function emptyBase(): DefaultRun {
  return { notices: [], violations: [] };
}

function mergedViolations(base: DefaultRun, productionViolations: Violation[]): Violation[] {
  return combineProductionPass(base, okPass(productionViolations)).violations;
}

describe('combineProductionPass dedupe behaviour', () => {
  const codeFinding: Violation = {
    ruleId: 'unused-export',
    source: 'knip:exports',
    file: '/a.ts',
    line: 3,
    message: 'foo',
  };

  it('collapses a production finding identical to a base violation into one', () => {
    const base: DefaultRun = { notices: [], violations: [codeFinding] };
    expect(mergedViolations(base, [{ ...codeFinding }])).toEqual([codeFinding]);
  });

  it('preserves distinct findings differing only by message', () => {
    const other: Violation = { ...codeFinding, message: 'bar' };
    expect(mergedViolations(emptyBase(), [codeFinding, other])).toEqual([codeFinding, other]);
  });

  it('treats a differing column as distinct', () => {
    const noCol: Violation = { ...codeFinding };
    const withCol: Violation = { ...codeFinding, column: 5 };
    expect(mergedViolations(emptyBase(), [noCol, withCol])).toEqual([noCol, withCol]);
  });
});

describe('combineProductionPass dead-code filtering', () => {
  function violation(source: string): Violation {
    return { ruleId: 'r', source, file: '/a.ts', line: 1, message: 'm' };
  }

  it('drops dependency findings from a production pass', () => {
    const deps = [violation('knip:dependencies'), violation('knip:devDependencies')];
    expect(mergedViolations(emptyBase(), deps)).toEqual([]);
  });

  it('keeps export and file dead-code findings', () => {
    const exportV = violation('knip:exports');
    const fileV = violation('knip:files');
    expect(mergedViolations(emptyBase(), [exportV, fileV])).toEqual([exportV, fileV]);
  });
});

describe('combineProductionPass', () => {
  function exportViolation(message: string): Violation {
    return { ruleId: 'unused-export', source: 'knip:exports', file: '/src/lib.ts', line: 1, message };
  }

  const base: DefaultRun = {
    notices: ['habit-hooks: using bundled knip'],
    violations: [exportViolation('defaultDead')],
  };

  it('returns the default run unchanged when the production pass skips', () => {
    const pass: KnipPass = { kind: 'skip', result: { skipWarning: 'knip skipped' } };

    const outcome = combineProductionPass(base, pass);

    expect(outcome.violations).toEqual(base.violations);
    expect(outcome.stderr).toEqual(base.notices);
  });

  it('keeps default violations and appends the warning when the production pass fails', () => {
    const pass: KnipPass = { kind: 'fail', warning: 'habit-hooks: knip skipped (exit 2)' };

    const outcome = combineProductionPass(base, pass);

    expect(outcome.violations).toEqual(base.violations);
    expect(outcome.stderr).toEqual([...base.notices, 'habit-hooks: knip skipped (exit 2)']);
  });

  it('drops dependency findings, keeps code findings, and never duplicates default violations', () => {
    const depFinding: Violation = {
      ruleId: 'r',
      source: 'knip:dependencies',
      file: '/src/lib.ts',
      line: 1,
      message: 'left-pad',
    };
    const codeFinding = exportViolation('prodOnlyDead');
    const duplicateOfDefault = exportViolation('defaultDead');
    const pass: KnipPass = { kind: 'ok', violations: [depFinding, codeFinding, duplicateOfDefault] };

    const outcome = combineProductionPass(base, pass);

    expect(outcome.violations).toEqual([exportViolation('defaultDead'), codeFinding]);
    expect(outcome.violations).not.toContainEqual(depFinding);
    expect(outcome.stderr).toEqual(base.notices);
  });
});
