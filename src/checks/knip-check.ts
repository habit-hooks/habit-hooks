import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { existsSync } from 'node:fs';
import type { Check, Violation } from '../types.js';

const require = createRequire(import.meta.url);

const RULE_ID = 'knip:unused-class-members';
const KNIP_ARGS = ['--no-exit-code', '--reporter', 'json', '--include', 'classMembers'];
const STDERR_TRUNCATE = 200;

interface KnipClassMember {
  name: string;
  line?: number;
  col?: number;
}

interface KnipIssue {
  file: string;
  classMembers?: Record<string, KnipClassMember[]>;
}

interface KnipReport {
  issues?: KnipIssue[];
}

interface KnipProcessResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

function binFromMain(mainPath: string): string | null {
  const candidate = join(dirname(mainPath), '..', 'bin', 'knip.js');
  return existsSync(candidate) ? candidate : null;
}

export function resolveBundledKnip(): string | null {
  try {
    return binFromMain(require.resolve('knip'));
  } catch {
    return null;
  }
}

function pipeStream(stream: NodeJS.ReadableStream | null | undefined, onChunk: (s: string) => void): void {
  stream?.on('data', (chunk: Buffer) => onChunk(chunk.toString('utf8')));
}

function collectProcess(
  child: ReturnType<typeof spawn>,
  onDone: (result: KnipProcessResult) => void,
): void {
  const buf = { stdout: '', stderr: '' };
  pipeStream(child.stdout, (s) => (buf.stdout += s));
  pipeStream(child.stderr, (s) => (buf.stderr += s));
  child.on('close', (code) => onDone({ stdout: buf.stdout, stderr: buf.stderr, exitCode: code }));
}

function runKnipProcess(binPath: string, cwd: string): Promise<KnipProcessResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [binPath, ...KNIP_ARGS], { cwd });
    child.on('error', reject);
    collectProcess(child, resolve);
  });
}

function parseReport(stdout: string): KnipReport | null {
  const trimmed = stdout.trim();
  if (trimmed.length === 0 || !trimmed.startsWith('{')) return null;
  try {
    return JSON.parse(trimmed) as KnipReport;
  } catch {
    return null;
  }
}

function memberToViolation(absFile: string, className: string, member: KnipClassMember): Violation {
  return {
    ruleId: RULE_ID,
    file: absFile,
    line: member.line ?? 1,
    column: member.col,
    message: `unused class member ${className}.${member.name}`,
  };
}

function membersToViolations(
  absFile: string,
  members: Record<string, KnipClassMember[]>,
): Violation[] {
  return Object.entries(members).flatMap(([className, list]) =>
    list.map((m) => memberToViolation(absFile, className, m)),
  );
}

function issueToViolations(issue: KnipIssue, cwd: string, allowed: Set<string>): Violation[] {
  if (!issue.classMembers) return [];
  const absFile = join(cwd, issue.file);
  if (!allowed.has(absFile)) return [];
  return membersToViolations(absFile, issue.classMembers);
}

function reportToViolations(report: KnipReport, cwd: string, files: string[]): Violation[] {
  const allowed = new Set(files);
  const issues = report.issues ?? [];
  return issues.flatMap((i) => issueToViolations(i, cwd, allowed));
}

function hasPackageJson(cwd: string): boolean {
  return existsSync(join(cwd, 'package.json'));
}

function warnMissing(cwd: string): void {
  process.stderr.write(
    `habit-hooks: knip not found in ${cwd}; skipping knip:unused-class-members\n`,
  );
}

function firstNonEmptyLine(text: string): string {
  for (const line of text.split('\n')) {
    const trimmed = line.trim();
    if (trimmed.length > 0) return trimmed;
  }
  return '';
}

function truncate(text: string, max: number): string {
  return text.length > max ? text.slice(0, max) : text;
}

function warnFailure(cwd: string, reason: string, stderr: string): void {
  const detail = firstNonEmptyLine(stderr);
  const suffix = detail.length > 0 ? `: ${truncate(detail, STDERR_TRUNCATE)}` : '';
  process.stderr.write(
    `habit-hooks: ${RULE_ID} failed in ${cwd} (${reason})${suffix}\n`,
  );
}

function isFailure(result: KnipProcessResult, report: KnipReport | null): string | null {
  if (result.exitCode !== 0) return `exit ${String(result.exitCode)}`;
  if (result.stderr.trim().length > 0) return 'stderr output';
  if (report === null) return 'unparseable stdout';
  return null;
}

async function detectViolations(binPath: string, cwd: string, files: string[]): Promise<Violation[]> {
  const result = await runKnipProcess(binPath, cwd);
  const report = parseReport(result.stdout);
  const failure = isFailure(result, report);
  if (failure !== null) {
    warnFailure(cwd, failure, result.stderr);
    return [];
  }
  return reportToViolations(report as KnipReport, cwd, files);
}

export interface KnipCheckOptions {
  resolveBin?: () => string | null;
}

async function runWithBin(binPath: string | null, cwd: string, files: string[]): Promise<Violation[]> {
  if (binPath === null) {
    warnMissing(cwd);
    return [];
  }
  return detectViolations(binPath, cwd, files);
}

export function createKnipCheck(options: KnipCheckOptions = {}): Check {
  const resolveBin = options.resolveBin ?? resolveBundledKnip;
  return {
    id: 'knip',
    async run(files, _rules, cwd) {
      if (files.length === 0) return [];
      const runCwd = cwd ?? process.cwd();
      if (!hasPackageJson(runCwd)) return [];
      return runWithBin(resolveBin(), runCwd, files);
    },
  };
}

export const knipCheck: Check = createKnipCheck();
