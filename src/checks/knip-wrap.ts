import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { hasPackageJsonKey } from '../detect/package-json.js';
import { TOOL_CONFIG_FILENAMES } from '../detect/tool.js';
import { emptyOutcome, firstLine, noticesFor, type BinResolution } from '../wrap/notices.js';
import { isSpawnSkip, parseJsonStdout, skipOutcome, spawnWrapped, type SpawnSkip } from '../wrap/run.js';
import {
  buildKnipArgs,
  buildKnipProductionArgs,
  consumerKnipMajor,
  knipConfigMarksProduction,
  resolveKnipBin,
} from './knip-resolve.js';
import { type KnipReport } from './knip-schema.js';
import { deadCodeViolations, dedupeViolations, reportToViolations } from './knip-merge.js';
import type { Check, CheckOutcome, Violation } from '../types.js';

export { buildKnipArgs, buildKnipProductionArgs, consumerKnipMajor, resolveKnipBin };
export { deadCodeViolations, dedupeViolations };

function exitFailureWarning(cwd: string, code: number, stderr: string): string {
  const detail = firstLine(stderr);
  const suffix = detail.length > 0 ? `: ${detail}` : '';
  return `habit-hooks: knip skipped in ${cwd} (exit ${code})${suffix}`;
}

function hasPackageJson(cwd: string): boolean {
  return existsSync(join(cwd, 'package.json'));
}

function hasKnipConfig(cwd: string): boolean {
  if (TOOL_CONFIG_FILENAMES.knip.some((name) => existsSync(join(cwd, name)))) return true;
  return hasPackageJsonKey(cwd, 'knip');
}

export type KnipPass =
  | { kind: 'skip'; result: SpawnSkip }
  | { kind: 'fail'; warning: string }
  | { kind: 'ok'; violations: Violation[] };

async function runKnipPass(resolution: BinResolution, cwd: string, args: string[]): Promise<KnipPass> {
  const result = await spawnWrapped({ tool: 'knip', resolution, cwd, args });
  if (isSpawnSkip(result)) return { kind: 'skip', result };
  const report = parseJsonStdout<KnipReport>(result.stdout, '{');
  if (report === null) return { kind: 'fail', warning: exitFailureWarning(cwd, result.exitCode, result.stderr) };
  return { kind: 'ok', violations: reportToViolations(report, cwd) };
}

export interface DefaultRun {
  notices: string[];
  violations: Violation[];
}

export function combineProductionPass(base: DefaultRun, pass: KnipPass): CheckOutcome {
  const { notices, violations } = base;
  if (pass.kind === 'skip') return { violations, stderr: notices };
  if (pass.kind === 'fail') return { violations, stderr: [...notices, pass.warning] };
  const merged = dedupeViolations([...violations, ...deadCodeViolations(pass.violations)]);
  return { violations: merged, stderr: notices };
}

async function mergeProductionDeadCode(resolution: BinResolution, cwd: string, base: DefaultRun): Promise<CheckOutcome> {
  const pass = await runKnipPass(resolution, cwd, buildKnipProductionArgs(resolution, cwd));
  return combineProductionPass(base, pass);
}

async function runKnip(resolution: BinResolution, cwd: string, notices: string[]): Promise<CheckOutcome> {
  const defaultPass = await runKnipPass(resolution, cwd, buildKnipArgs(resolution, cwd));
  if (defaultPass.kind === 'skip') return skipOutcome(defaultPass.result, notices);
  if (defaultPass.kind === 'fail') return emptyOutcome([...notices, defaultPass.warning]);
  const violations = defaultPass.violations;
  if (!knipConfigMarksProduction(cwd)) return { violations, stderr: notices };
  return mergeProductionDeadCode(resolution, cwd, { notices, violations });
}

function noPackageJsonOutcome(cwd: string, notices: string[]): CheckOutcome {
  return emptyOutcome([...notices, `habit-hooks: knip skipped in ${cwd} (no package.json)`]);
}

function noConfigOutcome(cwd: string, notices: string[]): CheckOutcome {
  return emptyOutcome([...notices, `habit-hooks: knip skipped in ${cwd} (no knip config)`]);
}

export const knipWrap: Check = {
  id: 'knip',
  async run(files, _rules, cwd) {
    const runCwd = cwd ?? process.cwd();
    if (files.length === 0) return { violations: [], stderr: [] };
    const resolution = resolveKnipBin(runCwd);
    const notices = noticesFor('knip', resolution, runCwd);
    if (!hasPackageJson(runCwd)) return noPackageJsonOutcome(runCwd, notices);
    if (!hasKnipConfig(runCwd)) return noConfigOutcome(runCwd, notices);
    return runKnip(resolution, runCwd, notices);
  },
};
