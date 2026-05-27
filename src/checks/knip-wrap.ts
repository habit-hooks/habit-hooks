import { createRequire } from 'node:module';
import { existsSync, readFileSync } from 'node:fs';
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

const KNIP_BASE_ARGS = ['--reporter', 'json', '--no-exit-code'];

const KNIP_CONFIG_FILES = ['knip.json', 'knip.jsonc', 'knip.ts', 'knip.js'];

interface KnipLocation {
  name: string;
  line?: number;
  col?: number;
}

type KnipMemberMap = Record<string, KnipLocation[]>;

interface KnipIssue {
  file: string;
  files?: KnipLocation[];
  dependencies?: KnipLocation[];
  devDependencies?: KnipLocation[];
  optionalPeerDependencies?: KnipLocation[];
  unlisted?: KnipLocation[];
  binaries?: KnipLocation[];
  unresolved?: KnipLocation[];
  exports?: KnipLocation[];
  nsExports?: KnipLocation[];
  types?: KnipLocation[];
  nsTypes?: KnipLocation[];
  duplicates?: KnipLocation[][];
  enumMembers?: KnipMemberMap;
  classMembers?: KnipMemberMap;
  namespaceMembers?: KnipMemberMap;
  catalog?: KnipLocation[];
}

interface KnipReport {
  files?: string[];
  issues?: KnipIssue[];
}

const LOCATION_KEYS: (keyof KnipIssue)[] = [
  'files',
  'dependencies',
  'devDependencies',
  'optionalPeerDependencies',
  'unlisted',
  'binaries',
  'unresolved',
  'exports',
  'nsExports',
  'types',
  'nsTypes',
  'catalog',
];

const MEMBER_KEYS: (keyof KnipIssue)[] = ['enumMembers', 'classMembers', 'namespaceMembers'];

const STRUCTURAL_KEYS = new Set<string>(['file']);
const SPECIAL_KEYS = new Set<string>(['duplicates']);
const KNOWN_KEYS = new Set<string>([
  ...STRUCTURAL_KEYS,
  ...SPECIAL_KEYS,
  ...(LOCATION_KEYS as string[]),
  ...(MEMBER_KEYS as string[]),
]);

function bundledKnipDir(): string {
  const main = require.resolve('knip');
  return join(dirname(main), '..');
}

function bundledKnipBin(): string {
  return join(bundledKnipDir(), 'bin', 'knip.js');
}

export function resolveKnipBin(cwd: string): BinResolution {
  const detected = detectTool(cwd, 'knip');
  if (detected !== null) return { binPath: detected.binPath, isFallback: false };
  return { binPath: bundledKnipBin(), isFallback: true };
}

function readMajorFromPackageJson(path: string): number | null {
  try {
    const pkg = JSON.parse(readFileSync(path, 'utf8')) as { version?: unknown };
    if (typeof pkg.version !== 'string') return null;
    const major = Number.parseInt(pkg.version.split('.')[0] ?? '', 10);
    return Number.isFinite(major) ? major : null;
  } catch {
    return null;
  }
}

export function consumerKnipMajor(cwd: string): number | null {
  return readMajorFromPackageJson(join(cwd, 'node_modules', 'knip', 'package.json'));
}

function bundledKnipMajor(): number | null {
  return readMajorFromPackageJson(join(bundledKnipDir(), 'package.json'));
}

function effectiveKnipMajor(resolution: BinResolution, cwd: string): number | null {
  if (resolution.isFallback) return bundledKnipMajor();
  return consumerKnipMajor(cwd);
}

export function buildKnipArgs(resolution: BinResolution, cwd: string): string[] {
  const major = effectiveKnipMajor(resolution, cwd);
  if (major !== null && major >= 6) return [...KNIP_BASE_ARGS];
  return [...KNIP_BASE_ARGS, '--include', 'classMembers'];
}

function exitFailureWarning(cwd: string, code: number, stderr: string): string {
  const detail = firstLine(stderr);
  const suffix = detail.length > 0 ? `: ${detail}` : '';
  return `habit-hooks: knip skipped in ${cwd} (exit ${code})${suffix}`;
}

function tryParseReport(stdout: string): KnipReport | null {
  const trimmed = stdout.trim();
  if (trimmed.length === 0 || !trimmed.startsWith('{')) return null;
  try {
    return JSON.parse(trimmed) as KnipReport;
  } catch {
    return null;
  }
}

interface IssueContext {
  cwd: string;
  issueType: string;
  issueFile: string;
}

function buildViolation(ruleId: string, file: string, message: string, loc: KnipLocation): Violation {
  return { ruleId, file, line: loc.line ?? 1, column: loc.col, message };
}

function locationToViolation(ctx: IssueContext, loc: KnipLocation): Violation {
  const ruleId = `knip:${ctx.issueType}`;
  return buildViolation(ruleId, absolutize(ctx.cwd, ctx.issueFile), loc.name, loc);
}

function memberToViolation(ctx: IssueContext, owner: string, loc: KnipLocation): Violation {
  const ruleId = `knip:${ctx.issueType}`;
  return buildViolation(ruleId, absolutize(ctx.cwd, ctx.issueFile), `${owner}.${loc.name}`, loc);
}

function flattenMemberMap(ctx: IssueContext, members: KnipMemberMap): Violation[] {
  return Object.entries(members).flatMap(([owner, list]) =>
    list.map((loc) => memberToViolation(ctx, owner, loc)),
  );
}

function buildIssueContext(cwd: string, issue: KnipIssue, key: keyof KnipIssue): IssueContext {
  return { cwd, issueType: key, issueFile: issue.file };
}

function locationsForKey(issue: KnipIssue, key: keyof KnipIssue, cwd: string): Violation[] {
  const value = issue[key];
  if (!Array.isArray(value) || value.length === 0) return [];
  const ctx = buildIssueContext(cwd, issue, key);
  return (value as KnipLocation[]).map((loc) => locationToViolation(ctx, loc));
}

function membersForKey(issue: KnipIssue, key: keyof KnipIssue, cwd: string): Violation[] {
  const value = issue[key];
  if (value === undefined || value === null || Array.isArray(value)) return [];
  return flattenMemberMap(buildIssueContext(cwd, issue, key), value as KnipMemberMap);
}

function warnDuplicatesIfPresent(issue: KnipIssue, cwd: string): void {
  if (issue.duplicates === undefined || issue.duplicates.length === 0) return;
  const file = absolutize(cwd, issue.file);
  process.stderr.write(`habit-hooks: knip duplicates issue ignored in ${file} (not yet supported)\n`);
}

function isPopulated(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'object') return Object.keys(value).length > 0;
  return true;
}

function unknownKeyToViolation(cwd: string, issue: KnipIssue, key: string): Violation {
  const ruleId = `knip:${key}`;
  const file = absolutize(cwd, issue.file);
  const message = 'unrecognised knip issue type';
  return { ruleId, file, line: 1, message };
}

function unknownKeysForIssue(issue: KnipIssue, cwd: string): Violation[] {
  const record = issue as unknown as Record<string, unknown>;
  return Object.keys(record)
    .filter((k) => !KNOWN_KEYS.has(k) && isPopulated(record[k]))
    .map((k) => unknownKeyToViolation(cwd, issue, k));
}

function issueToViolations(issue: KnipIssue, cwd: string): Violation[] {
  warnDuplicatesIfPresent(issue, cwd);
  const fromLocations = LOCATION_KEYS.flatMap((k) => locationsForKey(issue, k, cwd));
  const fromMembers = MEMBER_KEYS.flatMap((k) => membersForKey(issue, k, cwd));
  const fromUnknown = unknownKeysForIssue(issue, cwd);
  return [...fromLocations, ...fromMembers, ...fromUnknown];
}

function fileEntryToViolation(cwd: string, file: string): Violation {
  const ruleId = 'knip:files';
  return { ruleId, file: absolutize(cwd, file), line: 1, message: file };
}

function reportToViolations(report: KnipReport, cwd: string): Violation[] {
  const filesViolations = (report.files ?? []).map((f) => fileEntryToViolation(cwd, f));
  const issuesViolations = (report.issues ?? []).flatMap((i) => issueToViolations(i, cwd));
  return [...filesViolations, ...issuesViolations];
}

async function executeKnip(resolution: BinResolution, cwd: string): Promise<ShellResult> {
  const args = buildKnipArgs(resolution, cwd);
  const target = spawnTarget(resolution.binPath, args);
  return runTool({ bin: target.bin, args: target.args, cwd });
}

function hasPackageJson(cwd: string): boolean {
  return existsSync(join(cwd, 'package.json'));
}

function hasKnipPackageJsonKey(cwd: string): boolean {
  const path = join(cwd, 'package.json');
  if (!existsSync(path)) return false;
  try {
    const pkg = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
    return pkg.knip !== undefined;
  } catch {
    return false;
  }
}

function hasKnipConfig(cwd: string): boolean {
  if (KNIP_CONFIG_FILES.some((name) => existsSync(join(cwd, name)))) return true;
  return hasKnipPackageJsonKey(cwd);
}

async function runKnip(resolution: BinResolution, cwd: string, notices: string[]): Promise<CheckOutcome> {
  const result = await executeKnip(resolution, cwd);
  if (isSpawnFailure(result)) return emptyOutcome([...notices, spawnFailureWarning('knip', cwd, result.warnings)]);
  const report = tryParseReport(result.stdout);
  if (report === null) return emptyOutcome([...notices, exitFailureWarning(cwd, result.exitCode, result.stderr)]);
  return { violations: reportToViolations(report, cwd), stderr: notices };
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
