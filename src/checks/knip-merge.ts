import { absolutize } from '../wrap/notices.js';
import { KNIP_SMELL_MAP } from '../config/tool-smells.js';
import {
  CODE_KEYS,
  KNOWN_KEYS,
  LOCATION_KEYS,
  MEMBER_KEYS,
  type KnipIssue,
  type KnipLocation,
  type KnipMemberMap,
  type KnipReport,
} from './knip-schema.js';
import type { Violation } from '../types.js';

const PRODUCTION_PASS_SOURCES = new Set<string>(['knip:files', ...CODE_KEYS.map((k) => `knip:${k}`)]);

interface IssueContext {
  cwd: string;
  issueType: string;
  issueFile: string;
}

interface BuildViolationArgs {
  ruleId: string;
  source: string;
  file: string;
  message: string;
  loc: KnipLocation;
}

function knipSmell(issueType: string): string {
  return Object.hasOwn(KNIP_SMELL_MAP, issueType) ? KNIP_SMELL_MAP[issueType] : issueType;
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
  return Object.entries(members).flatMap(([owner, list]) => list.map((loc) => memberToViolation(ctx, owner, loc)));
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

export function reportToViolations(report: KnipReport, cwd: string): Violation[] {
  const filesViolations = (report.files ?? []).map((f) => fileEntryToViolation(cwd, f));
  const issuesViolations = (report.issues ?? []).flatMap((i) => issueToViolations(i, cwd));
  return [...filesViolations, ...issuesViolations];
}

function violationKey(v: Violation): string {
  return `${v.source}|${v.file}|${String(v.line)}|${String(v.column)}|${v.message}`;
}

export function dedupeViolations(violations: Violation[]): Violation[] {
  const seen = new Set<string>();
  const keep: Violation[] = [];
  for (const v of violations) {
    const key = violationKey(v);
    if (seen.has(key)) continue;
    seen.add(key);
    keep.push(v);
  }
  return keep;
}

export function deadCodeViolations(violations: Violation[]): Violation[] {
  return violations.filter((v) => v.source !== undefined && PRODUCTION_PASS_SOURCES.has(v.source));
}
