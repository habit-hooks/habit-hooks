import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { hasPackageJsonKey } from '../detect/package-json.js';
import { absolutize, emptyOutcome, firstLine, noticesFor, type BinResolution } from '../wrap/notices.js';
import { isSpawnSkip, parseJsonStdout, skipOutcome, spawnWrapped } from '../wrap/run.js';
import { KNIP_SMELL_MAP } from '../config/tool-smells.js';
import { buildKnipArgs, consumerKnipMajor, resolveKnipBin } from './knip-resolve.js';
import {
  KNOWN_KEYS,
  LOCATION_KEYS,
  MEMBER_KEYS,
  type KnipIssue,
  type KnipLocation,
  type KnipMemberMap,
  type KnipReport,
} from './knip-schema.js';
import type { Check, CheckOutcome, Violation } from '../types.js';

export { buildKnipArgs, consumerKnipMajor, resolveKnipBin };

const KNIP_CONFIG_FILES = ['knip.json', 'knip.jsonc', 'knip.ts', 'knip.js'];

function exitFailureWarning(cwd: string, code: number, stderr: string): string {
  const detail = firstLine(stderr);
  const suffix = detail.length > 0 ? `: ${detail}` : '';
  return `habit-hooks: knip skipped in ${cwd} (exit ${code})${suffix}`;
}

interface IssueContext {
  cwd: string;
  issueType: string;
  issueFile: string;
}

function knipSmell(issueType: string): string {
  return KNIP_SMELL_MAP[issueType] ?? issueType;
}

interface BuildViolationArgs {
  ruleId: string;
  source: string;
  file: string;
  message: string;
  loc: KnipLocation;
}

function buildViolation(args: BuildViolationArgs): Violation {
  const { ruleId, source, file, message, loc } = args;
  return { ruleId, source, file, line: loc.line ?? 1, column: loc.col, message };
}

function locationToViolation(ctx: IssueContext, loc: KnipLocation): Violation {
  const ruleId = knipSmell(ctx.issueType);
  const source = `knip:${ctx.issueType}`;
  return buildViolation({ ruleId, source, file: absolutize(ctx.cwd, ctx.issueFile), message: loc.name, loc });
}

function memberToViolation(ctx: IssueContext, owner: string, loc: KnipLocation): Violation {
  const ruleId = knipSmell(ctx.issueType);
  const source = `knip:${ctx.issueType}`;
  const file = absolutize(ctx.cwd, ctx.issueFile);
  return buildViolation({ ruleId, source, file, message: `${owner}.${loc.name}`, loc });
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
  const ruleId = knipSmell(key);
  const source = `knip:${key}`;
  const file = absolutize(cwd, issue.file);
  const message = 'unrecognised knip issue type';
  return { ruleId, source, file, line: 1, message };
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
  const source = 'knip:files';
  return { ruleId: knipSmell('files'), source, file: absolutize(cwd, file), line: 1, message: file };
}

function reportToViolations(report: KnipReport, cwd: string): Violation[] {
  const filesViolations = (report.files ?? []).map((f) => fileEntryToViolation(cwd, f));
  const issuesViolations = (report.issues ?? []).flatMap((i) => issueToViolations(i, cwd));
  return [...filesViolations, ...issuesViolations];
}

function hasPackageJson(cwd: string): boolean {
  return existsSync(join(cwd, 'package.json'));
}

function hasKnipConfig(cwd: string): boolean {
  if (KNIP_CONFIG_FILES.some((name) => existsSync(join(cwd, name)))) return true;
  return hasPackageJsonKey(cwd, 'knip');
}

async function runKnip(resolution: BinResolution, cwd: string, notices: string[]): Promise<CheckOutcome> {
  const result = await spawnWrapped({ tool: 'knip', resolution, cwd, args: buildKnipArgs(resolution, cwd) });
  if (isSpawnSkip(result)) return skipOutcome(result, notices);
  const report = parseJsonStdout<KnipReport>(result.stdout, '{');
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
