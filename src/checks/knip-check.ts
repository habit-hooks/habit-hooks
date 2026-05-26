import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { existsSync } from 'node:fs';
import type { Check, Violation } from '../types.js';

const require = createRequire(import.meta.url);

const RULE_ID = 'knip:unused-class-members';
const KNIP_ARGS = ['--no-exit-code', '--reporter', 'json', '--include', 'classMembers'];

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

function binFromMain(mainPath: string): string | null {
  const candidate = join(dirname(mainPath), '..', 'bin', 'knip.js');
  return existsSync(candidate) ? candidate : null;
}

function resolveFromCwd(cwd: string): string | null {
  try {
    const localRequire = createRequire(`${cwd}/__noop.js`);
    return binFromMain(localRequire.resolve('knip'));
  } catch {
    return null;
  }
}

function resolveFromPackage(): string | null {
  try {
    return binFromMain(require.resolve('knip'));
  } catch {
    return null;
  }
}

function resolveKnipBin(cwd: string): string | null {
  return resolveFromCwd(cwd) ?? resolveFromPackage();
}

function collectStdout(child: ReturnType<typeof spawn>, onDone: (stdout: string) => void): void {
  let stdout = '';
  child.stdout?.on('data', (chunk: Buffer) => {
    stdout += chunk.toString('utf8');
  });
  child.stderr?.on('data', () => {});
  child.on('close', () => onDone(stdout));
}

function runKnipProcess(binPath: string, cwd: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [binPath, ...KNIP_ARGS], { cwd });
    child.on('error', reject);
    collectStdout(child, resolve);
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

async function detectViolations(binPath: string, cwd: string, files: string[]): Promise<Violation[]> {
  const stdout = await runKnipProcess(binPath, cwd);
  const report = parseReport(stdout);
  if (report === null) return [];
  return reportToViolations(report, cwd, files);
}

export const knipCheck: Check = {
  id: 'knip',
  async run(files, _rules, cwd) {
    if (files.length === 0) return [];
    const runCwd = cwd ?? process.cwd();
    if (!hasPackageJson(runCwd)) return [];
    const binPath = resolveKnipBin(runCwd);
    if (binPath === null) {
      warnMissing(runCwd);
      return [];
    }
    return detectViolations(binPath, runCwd, files);
  },
};
