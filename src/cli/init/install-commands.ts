import { existsSync, statSync } from 'node:fs';
import { join } from 'node:path';

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
  return [...hits].sort((a, b) => b.mtimeMs - a.mtimeMs)[0]!;
}

export function detectPackageManager(cwd: string): PackageManager {
  const hits = findAllLockfileHits(cwd);
  if (hits.length === 0) return 'npm';
  if (hits.length === 1) return hits[0]!.pm;
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

export function packagesFor(tool: 'eslint' | 'knip' | 'jscpd'): string[] {
  if (tool === 'eslint') return ESLINT_PACKAGES;
  return [tool];
}
