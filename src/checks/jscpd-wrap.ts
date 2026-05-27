import { createRequire } from 'node:module';
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { runTool, type ShellResult } from '../wrap/shell.js';
import { detectTool } from '../detect/tool.js';
import {
  absolutize,
  emptyOutcome,
  firstLine,
  isSpawnFailure,
  noticesFor,
  spawnFailureWarning,
  type BinResolution,
} from '../wrap/notices.js';
import { spawnTarget } from '../wrap/resolve.js';
import type { Check, CheckOutcome, Violation } from '../types.js';

const require = createRequire(import.meta.url);

const RULE_ID = 'jscpd:duplication';
const REPORT_FILENAME = 'jscpd-report.json';

const JSCPD_CONFIG_FILES = ['.jscpd.json', 'jscpd.json'];

interface JscpdLocation {
  name: string;
  startLoc: { line: number; column?: number };
  endLoc: { line: number; column?: number };
}

interface JscpdClone {
  firstFile: JscpdLocation;
  secondFile: JscpdLocation;
}

interface JscpdReport {
  duplicates?: JscpdClone[];
}

function findPackageRoot(start: string): string {
  let dir = start;
  while (dir !== dirname(dir)) {
    if (existsSync(join(dir, 'package.json'))) return dir;
    dir = dirname(dir);
  }
  throw new Error(`Could not find package.json from ${start}`);
}

export function bundledJscpdBin(): string {
  const main = require.resolve('jscpd');
  const pkgRoot = findPackageRoot(dirname(main));
  const pkg = JSON.parse(readFileSync(join(pkgRoot, 'package.json'), 'utf8')) as { bin?: { jscpd?: string } | string };
  const binRel = typeof pkg.bin === 'string' ? pkg.bin : pkg.bin?.jscpd ?? 'bin/jscpd';
  return join(pkgRoot, binRel);
}

export function tryBundledJscpdBin(resolver: () => string = bundledJscpdBin): string | null {
  try {
    return resolver();
  } catch {
    return null;
  }
}

export function resolveJscpdBin(cwd: string, fallbackResolver: () => string = bundledJscpdBin): BinResolution | null {
  const detected = detectTool(cwd, 'jscpd');
  if (detected !== null) return { binPath: detected.binPath, isFallback: false };
  const fallback = tryBundledJscpdBin(fallbackResolver);
  if (fallback === null) return null;
  return { binPath: fallback, isFallback: true };
}

function reportMissingWarning(cwd: string, code: number, stderr: string): string {
  const detail = firstLine(stderr);
  const suffix = detail.length > 0 ? `: ${detail}` : '';
  return `habit-hooks: jscpd skipped in ${cwd} (exit ${code}, no report)${suffix}`;
}

function parseFailureWarning(cwd: string): string {
  return `habit-hooks: jscpd skipped in ${cwd} (unparseable report)`;
}

function unresolvedBinWarning(cwd: string): string {
  return `habit-hooks: jscpd skipped in ${cwd} (could not locate bundled bin)`;
}

function locationDescription(loc: JscpdLocation, cwd: string): string {
  return `${absolutize(cwd, loc.name)}:${loc.startLoc.line}-${loc.endLoc.line}`;
}

function buildViolation(self: JscpdLocation, partner: JscpdLocation, cwd: string): Violation {
  return {
    ruleId: RULE_ID,
    file: absolutize(cwd, self.name),
    line: self.startLoc.line,
    column: self.startLoc.column,
    message: `duplicates ${locationDescription(partner, cwd)}`,
  };
}

function isInScope(loc: JscpdLocation, scope: Set<string>, cwd: string): boolean {
  return scope.has(absolutize(cwd, loc.name));
}

function cloneToViolations(clone: JscpdClone, scope: Set<string>, cwd: string): Violation[] {
  const violations: Violation[] = [];
  if (isInScope(clone.firstFile, scope, cwd)) {
    violations.push(buildViolation(clone.firstFile, clone.secondFile, cwd));
  }
  if (isInScope(clone.secondFile, scope, cwd)) {
    violations.push(buildViolation(clone.secondFile, clone.firstFile, cwd));
  }
  return violations;
}

function reportToViolations(report: JscpdReport, scope: Set<string>, cwd: string): Violation[] {
  return (report.duplicates ?? []).flatMap((c) => cloneToViolations(c, scope, cwd));
}

function tryReadReport(reportDir: string): JscpdReport | null {
  const path = join(reportDir, REPORT_FILENAME);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, 'utf8')) as JscpdReport;
  } catch {
    return null;
  }
}

function buildArgs(reportDir: string): string[] {
  return ['-r', 'json', '-o', reportDir, '--silent', '--noTips', '-n', '.'];
}

async function executeJscpd(resolution: BinResolution, cwd: string, reportDir: string): Promise<ShellResult> {
  const target = spawnTarget(resolution.binPath, buildArgs(reportDir));
  return runTool({ bin: target.bin, args: target.args, cwd });
}

function makeReportDir(): string {
  return mkdtempSync(join(tmpdir(), 'hh-jscpd-'));
}

function removeReportDir(reportDir: string): void {
  rmSync(reportDir, { recursive: true, force: true });
}

interface RunInputs {
  resolution: BinResolution;
  cwd: string;
  scope: Set<string>;
  notices: string[];
}

function missingReportOutcome(inputs: RunInputs, result: ShellResult): CheckOutcome {
  if (result.exitCode !== 0) {
    return emptyOutcome([...inputs.notices, reportMissingWarning(inputs.cwd, result.exitCode, result.stderr)]);
  }
  return emptyOutcome([...inputs.notices, parseFailureWarning(inputs.cwd)]);
}

async function runOnce(inputs: RunInputs, reportDir: string): Promise<CheckOutcome> {
  const result = await executeJscpd(inputs.resolution, inputs.cwd, reportDir);
  if (isSpawnFailure(result)) return emptyOutcome([...inputs.notices, spawnFailureWarning('jscpd', inputs.cwd, result.warnings)]);
  const report = tryReadReport(reportDir);
  if (report === null) return missingReportOutcome(inputs, result);
  return { violations: reportToViolations(report, inputs.scope, inputs.cwd), stderr: inputs.notices };
}

async function runJscpd(inputs: RunInputs): Promise<CheckOutcome> {
  const reportDir = makeReportDir();
  try {
    return await runOnce(inputs, reportDir);
  } finally {
    removeReportDir(reportDir);
  }
}

function hasJscpdPackageJsonKey(cwd: string): boolean {
  const path = join(cwd, 'package.json');
  if (!existsSync(path)) return false;
  try {
    const pkg = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
    return pkg.jscpd !== undefined;
  } catch {
    return false;
  }
}

function hasJscpdConfig(cwd: string): boolean {
  if (JSCPD_CONFIG_FILES.some((name) => existsSync(join(cwd, name)))) return true;
  return hasJscpdPackageJsonKey(cwd);
}

function noConfigOutcome(cwd: string, notices: string[]): CheckOutcome {
  return emptyOutcome([...notices, `habit-hooks: jscpd skipped in ${cwd} (no jscpd config)`]);
}

function noBinOutcome(cwd: string): CheckOutcome {
  return emptyOutcome([unresolvedBinWarning(cwd)]);
}

export async function runJscpdWrap(
  files: string[],
  cwd: string,
  resolution: BinResolution | null,
): Promise<CheckOutcome> {
  if (files.length === 0) return { violations: [], stderr: [] };
  if (resolution === null) return noBinOutcome(cwd);
  const notices = noticesFor('jscpd', resolution, cwd);
  if (!hasJscpdConfig(cwd)) return noConfigOutcome(cwd, notices);
  return runJscpd({ resolution, cwd, scope: new Set(files), notices });
}

export const jscpdWrap: Check = {
  id: 'jscpd',
  async run(files, _rules, cwd) {
    const runCwd = cwd ?? process.cwd();
    return runJscpdWrap(files, runCwd, resolveJscpdBin(runCwd));
  },
};
