import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { runTool, type ShellResult } from '../wrap/shell.js';
import { detectTool } from '../detect/tool.js';
import { lookupPrompt } from '../prompts/registry.js';
import {
  emptyOutcome,
  firstLine,
  isSpawnFailure,
  noticesFor,
  spawnFailureWarning,
  type BinResolution,
} from '../wrap/notices.js';
import { spawnTarget } from '../wrap/resolve.js';
import { parseJsonStdout } from '../wrap/run.js';
import type { Check, CheckOutcome, Violation } from '../types.js';

const require = createRequire(import.meta.url);

interface EslintMessage {
  ruleId: string | null;
  message: string;
  line: number;
  column?: number;
}

interface EslintFileResult {
  filePath: string;
  messages: EslintMessage[];
}

function bundledEslintBin(): string {
  const main = require.resolve('eslint');
  return join(dirname(main), '..', 'bin', 'eslint.js');
}

function resolveEslintBin(cwd: string): BinResolution {
  const detected = detectTool(cwd, 'eslint');
  if (detected !== null) return { binPath: detected.binPath, isFallback: false };
  return { binPath: bundledEslintBin(), isFallback: true };
}

function configWarning(cwd: string, detail: string): string {
  const suffix = detail.length > 0 ? `: ${detail}` : '';
  return `habit-hooks: eslint skipped in ${cwd} (config error)${suffix}`;
}

function tryParseJson(stdout: string): EslintFileResult[] | null {
  return parseJsonStdout<EslintFileResult[]>(stdout, '[');
}

function isConfigError(result: ShellResult, parsed: EslintFileResult[] | null): boolean {
  if (parsed !== null) return false;
  if (isSpawnFailure(result)) return false;
  return result.exitCode !== 0 && result.exitCode !== 1;
}

function messageToViolation(filePath: string, m: EslintMessage): Violation | null {
  if (m.ruleId === null) return null;
  const ruleId = `eslint:${m.ruleId}`;
  const prompt = lookupPrompt(ruleId);
  const title = prompt?.title ?? m.ruleId;
  return { ruleId, file: filePath, line: m.line, column: m.column, message: `${title}: ${m.message}` };
}

function fileResultToViolations(result: EslintFileResult): Violation[] {
  return result.messages
    .map((m) => messageToViolation(result.filePath, m))
    .filter((v): v is Violation => v !== null);
}

function parseEslintJson(stdout: string): Violation[] {
  const parsed = tryParseJson(stdout);
  if (parsed === null) return [];
  return parsed.flatMap(fileResultToViolations);
}

function buildArgs(files: string[]): string[] {
  return ['--format', 'json', ...files];
}

async function executeEslint(resolution: BinResolution, cwd: string, files: string[]): Promise<ShellResult> {
  const target = spawnTarget(resolution.binPath, buildArgs(files));
  return runTool({ bin: target.bin, args: target.args, cwd });
}

function failureNotices(cwd: string, result: ShellResult): string[] {
  const detail = firstLine(result.stderr.length > 0 ? result.stderr : result.stdout);
  return [configWarning(cwd, detail)];
}

async function runEslint(resolution: BinResolution, cwd: string, files: string[]): Promise<CheckOutcome> {
  const notices = noticesFor('eslint', resolution, cwd);
  const result = await executeEslint(resolution, cwd, files);
  const parsed = tryParseJson(result.stdout);
  if (isSpawnFailure(result)) return emptyOutcome([...notices, spawnFailureWarning('eslint', cwd, result.warnings)]);
  if (isConfigError(result, parsed)) return emptyOutcome([...notices, ...failureNotices(cwd, result)]);
  return { violations: parseEslintJson(result.stdout), stderr: notices };
}

export const eslintWrap: Check = {
  id: 'eslint',
  async run(files, _rules, cwd) {
    const runCwd = cwd ?? process.cwd();
    if (files.length === 0) return { violations: [], stderr: [] };
    return runEslint(resolveEslintBin(runCwd), runCwd, files);
  },
};
