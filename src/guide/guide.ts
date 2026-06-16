import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Environment } from 'nunjucks';
import { createEnv, renderTemplate } from './render.js';
import { runFixCommand, type CommandRun } from './command.js';
import type { GuideAction, MapperDirs, MapResult } from '../mapper/mapper.js';
import type { Issue } from '../sensors/types.js';

// The guide coaches the fix and signals pass/fail (docs/guide.md). It composes
// each smell's section — the title header + a body (the rendered prompt
// template, or the rule description as a fallback when a smell ships no tuned
// prompt) + the issue list — lists the uncoached bucket, and computes the exit
// code. A smell may ship a `<smell>.issues.njk` partial to group its issues its
// own way; otherwise a flat default list is rendered. Everything renders through
// Nunjucks (a static template is the degenerate case).

export interface GuideResult {
  stdout: string;
  exitCode: 0 | 1;
}

export interface GuideInput {
  result: MapResult;
  dirs: MapperDirs;
  cwd: string;
}

interface PreparedAction {
  action: GuideAction;
  command: CommandRun | null;
}

const CLEAN_BANNER =
  '✅ Habit Hooks: automated checks passed.\n\nHabit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.';

const DEFAULT_ISSUES_TEMPLATE =
  'Violations:\n{% for i in issues %}- {{ i.details.file }}:{{ i.details.line }} - {{ i.details.message }}\n{% endfor %}';

function searchPathsFor(dirs: MapperDirs): string[] {
  return dirs.overrideDir !== undefined ? [dirs.overrideDir, dirs.packagedDir] : [dirs.packagedDir];
}

function findInDirs(name: string, dirs: MapperDirs): string | null {
  for (const dir of searchPathsFor(dirs)) {
    const path = join(dir, name);
    if (existsSync(path)) return path;
  }
  return null;
}

function issuesTemplate(smell: string, dirs: MapperDirs): string {
  const custom = findInDirs(`${smell}.issues.njk`, dirs);
  return custom !== null ? readFileSync(custom, 'utf8') : DEFAULT_ISSUES_TEMPLATE;
}

function renderIssues(env: Environment, action: GuideAction, dirs: MapperDirs): string {
  const source = issuesTemplate(action.smell, dirs);
  return env.renderString(source, { smell: action.smell, issues: action.issues }).trimEnd();
}

function renderProse(env: Environment, action: GuideAction): string {
  if (action.action.kind !== 'prompt') return '';
  return renderTemplate(env, action.action.templatePath, { smell: action.smell, issues: action.issues });
}

function composeSection(env: Environment, prepared: PreparedAction, dirs: MapperDirs): string {
  const { action, command } = prepared;
  const prose = renderProse(env, action);
  const body = prose.length > 0 ? prose : action.description;
  const head = [`❌ ${action.title}`, body].filter((part) => part.length > 0).join('\n\n');
  const base = `${head}\n\n${renderIssues(env, action, dirs)}`;
  return command !== null && command.output.length > 0 ? `${base}\n\n${command.output}` : base;
}

function totalIssues(result: MapResult): number {
  return result.actions.reduce((sum, a) => sum + a.issues.length, 0) + result.uncoached.length;
}

function header(total: number): string {
  return `❌ Habit Hooks: ${total} ${total === 1 ? 'violation' : 'violations'}`;
}

function uncoachedLine(issue: Issue): string {
  const { file, line, message, source } = issue.details;
  return `- ${source ?? issue.smell}: ${message} (${file}:${line})`;
}

function renderUncoached(issues: Issue[]): string {
  if (issues.length === 0) return '';
  return `⚠️ Uncoached smells\n\n${issues.map(uncoachedLine).join('\n')}`;
}

function actionBlocks(prepared: PreparedAction): boolean {
  const { action, command } = prepared;
  if (command !== null) return command.blocks;
  return action.severity === 'enforced' && action.issues.length > 0;
}

function exitFor(prepared: PreparedAction[]): 0 | 1 {
  return prepared.some(actionBlocks) ? 1 : 0;
}

function prepareAction(action: GuideAction, cwd: string): Promise<PreparedAction> {
  const fix = action.action;
  if (fix.kind !== 'command' || action.issues.length === 0) {
    return Promise.resolve({ action, command: null });
  }
  return runFixCommand(action, fix.scriptPath, cwd).then((command) => ({ action, command }));
}

export async function guide(input: GuideInput): Promise<GuideResult> {
  const { result, dirs, cwd } = input;
  const total = totalIssues(result);
  if (total === 0) return { stdout: `${CLEAN_BANNER}\n\n`, exitCode: 0 };
  const env = createEnv(searchPathsFor(dirs));
  const prepared = await Promise.all(result.actions.map((action) => prepareAction(action, cwd)));
  const bodies = prepared.map((p) => composeSection(env, p, dirs));
  const sections = [header(total), ...bodies, renderUncoached(result.uncoached)];
  const stdout = `${sections.filter((s) => s.length > 0).join('\n\n\n\n')}\n\n`;
  return { stdout, exitCode: exitFor(prepared) };
}
