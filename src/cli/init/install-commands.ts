import { existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
import type { ToolName } from '../../detect/tool.js';

type PackageManager = 'pnpm' | 'yarn' | 'bun' | 'npm';

type LockfilePm = Exclude<PackageManager, 'npm'>;

const LOCKFILES: Record<LockfilePm, readonly string[]> = {
  pnpm: ['pnpm-lock.yaml'],
  yarn: ['yarn.lock'],
  bun: ['bun.lock', 'bun.lockb'],
};

interface LockfileHit {
  pm: LockfilePm;
  path: string;
  mtimeMs: number;
}

function lockfileHitsFor(cwd: string, pm: LockfilePm): LockfileHit[] {
  const hits: LockfileHit[] = [];
  for (const file of LOCKFILES[pm]) {
    const path = join(cwd, file);
    if (existsSync(path)) hits.push({ pm, path, mtimeMs: statSync(path).mtimeMs });
  }
  return hits;
}

function findAllLockfileHits(cwd: string): LockfileHit[] {
  const all: LockfileHit[] = [];
  for (const pm of Object.keys(LOCKFILES) as LockfilePm[]) {
    all.push(...lockfileHitsFor(cwd, pm));
  }
  return all;
}

function pickNewest(hits: LockfileHit[]): LockfileHit {
  const sorted = [...hits].sort((a, b) => b.mtimeMs - a.mtimeMs);
  const newest = sorted[0];
  if (newest === undefined) throw new Error('pickNewest requires at least one hit');
  return newest;
}

export function detectPackageManager(cwd: string): PackageManager {
  const hits = findAllLockfileHits(cwd);
  if (hits.length === 0) return 'npm';
  return pickNewest(hits).pm;
}

const ADD_FLAGS: Record<PackageManager, string[]> = {
  pnpm: ['add', '-D'],
  yarn: ['add', '-D'],
  bun: ['add', '-d'],
  npm: ['install', '--save-dev'],
};

export function buildInstallCommand(pm: PackageManager, packages: string[]): string {
  return [pm, ...ADD_FLAGS[pm], ...packages].join(' ');
}

export function runScriptCommand(pm: PackageManager, script: string): string {
  return `${pm} run ${script}`;
}

const ESLINT_PACKAGES = ['eslint', '@eslint/js', 'typescript-eslint'];

export function packagesFor(tool: ToolName): string[] {
  if (tool === 'eslint') return ESLINT_PACKAGES;
  return [tool];
}

type Ecosystem = 'node' | 'pip';

const ECOSYSTEM: Record<ToolName, Ecosystem> = {
  eslint: 'node',
  knip: 'node',
  jscpd: 'node',
  ruff: 'pip',
  deptry: 'pip',
};

function toolsInEcosystem(tools: ToolName[], ecosystem: Ecosystem): ToolName[] {
  return tools.filter((tool) => ECOSYSTEM[tool] === ecosystem);
}

function nodeInstallCommand(cwd: string, tools: ToolName[]): string | null {
  if (tools.length === 0) return null;
  const packages = tools.flatMap((tool) => packagesFor(tool));
  return buildInstallCommand(detectPackageManager(cwd), packages);
}

function pipInstallCommand(tools: ToolName[]): string | null {
  if (tools.length === 0) return null;
  const packages = tools.flatMap((tool) => packagesFor(tool));
  return `pip install ${packages.join(' ')}`;
}

export function installCommandsFor(cwd: string, missingTools: ToolName[]): string[] {
  const node = nodeInstallCommand(cwd, toolsInEcosystem(missingTools, 'node'));
  const pip = pipInstallCommand(toolsInEcosystem(missingTools, 'pip'));
  return [node, pip].filter((command): command is string => command !== null);
}
