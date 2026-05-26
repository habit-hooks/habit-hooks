import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { scaffoldConfig } from './scaffold-config.js';
import { scaffoldBaseline } from './scaffold-baseline.js';
import {
  addCiScript,
  addHabitHooksScript,
  type ScriptResult,
} from './package-scripts.js';
import { installPreCommitHook, type HookResult } from './git-hook.js';
import { installReviewerSkill, type SkillResult } from './skill.js';
import { AGENT_SNIPPET } from './snippet.js';
import type { Prompter } from './prompts.js';

export interface InitOptions {
  prompter: Prompter;
}

export interface InitResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

interface Lines {
  out: string[];
  err: string[];
  exit: number;
}

function emitConflict(lines: Lines, message: string): void {
  lines.err.push(`habit-hooks: ${message}\n`);
  lines.exit = 2;
}

function writeConfigStep(cwd: string, lines: Lines): boolean {
  const result = scaffoldConfig(cwd);
  if (result.conflict !== null) {
    emitConflict(lines, `refusing to overwrite existing config at ${result.conflict}`);
    return false;
  }
  lines.out.push(`wrote ${result.path}\n`);
  return true;
}

function writeBaselineStep(cwd: string, lines: Lines): void {
  const result = scaffoldBaseline(cwd);
  if (result.created) lines.out.push(`wrote ${result.path}\n`);
  else lines.out.push(`kept existing ${result.path}\n`);
}

function reportScriptResult(name: string, result: ScriptResult, lines: Lines): void {
  if (result.action === 'added') lines.out.push(`added '${name}' to package.json scripts\n`);
  else if (result.action === 'kept') lines.out.push(`'${name}' already set as desired in package.json\n`);
  else if (result.action === 'no-package-json') lines.out.push(`skipped '${name}': no package.json in cwd\n`);
  else if (result.action === 'conflict') {
    emitConflict(
      lines,
      `refusing to replace '${name}' script (currently: ${result.before ?? '<unknown>'})`,
    );
  }
}

async function maybeAddHabitHooksScript(cwd: string, prompter: Prompter, lines: Lines): Promise<void> {
  const yes = await prompter.ask("Add 'habit-hooks' to package.json scripts?", { defaultYes: true });
  if (!yes) return;
  reportScriptResult('habit-hooks', addHabitHooksScript(cwd), lines);
}

async function maybeAddCiScript(cwd: string, prompter: Prompter, lines: Lines): Promise<void> {
  const yes = await prompter.ask("Wire 'npm run ci' as the full quality gate?", { defaultYes: true });
  if (!yes) return;
  reportScriptResult('ci', addCiScript(cwd), lines);
}

function reportHookResult(result: HookResult, lines: Lines): void {
  if (result.action === 'installed') lines.out.push(`installed pre-commit hook at ${result.path}\n`);
  else if (result.action === 'kept') lines.out.push(`pre-commit hook already installed at ${result.path}\n`);
  else if (result.action === 'conflict') {
    lines.out.push(`pre-commit hook already exists at ${result.path} — left untouched\n`);
  } else if (result.action === 'no-git') {
    lines.out.push(`skipped pre-commit hook: no .git directory in cwd\n`);
  }
}

async function maybeInstallHook(cwd: string, prompter: Prompter, lines: Lines): Promise<void> {
  const yes = await prompter.ask('Install a git pre-commit hook?', { defaultYes: false });
  if (!yes) return;
  reportHookResult(installPreCommitHook(cwd), lines);
}

function reportSkillResult(result: SkillResult, lines: Lines): void {
  if (result.action === 'installed') lines.out.push(`installed reviewer skill at ${result.target}\n`);
  else if (result.action === 'kept') lines.out.push(`reviewer skill already at ${result.target}\n`);
  else if (result.action === 'conflict') {
    lines.out.push(`reviewer skill already exists at ${result.target} — left untouched\n`);
  } else if (result.action === 'source-missing') {
    lines.err.push(`habit-hooks: could not find packaged SKILL.md — skipping\n`);
  }
}

async function maybeInstallSkill(prompter: Prompter, lines: Lines): Promise<void> {
  const yes = await prompter.ask("Install the bundled 'habit-hooks-review' skill into ~/.claude/skills/?", {
    defaultYes: false,
  });
  if (!yes) return;
  reportSkillResult(installReviewerSkill(), lines);
}

function noteMissingDeps(cwd: string, lines: Lines): void {
  const missing: string[] = [];
  if (!existsSync(join(cwd, 'node_modules', 'jscpd'))) missing.push('jscpd');
  if (!existsSync(join(cwd, 'node_modules', 'knip'))) missing.push('knip');
  if (missing.length === 0) return;
  lines.out.push(`\nNote: ${missing.join(' and ')} not installed; install for full default rule coverage.\n`);
}

function printSnippet(lines: Lines): void {
  lines.out.push('\n--- paste into CLAUDE.md / AGENTS.md ---\n');
  lines.out.push(AGENT_SNIPPET);
  lines.out.push('--- end snippet ---\n');
}

async function runPrompts(cwd: string, prompter: Prompter, lines: Lines): Promise<void> {
  await maybeAddHabitHooksScript(cwd, prompter, lines);
  await maybeAddCiScript(cwd, prompter, lines);
  await maybeInstallHook(cwd, prompter, lines);
  await maybeInstallSkill(prompter, lines);
}

export async function runInit(cwd: string, opts: InitOptions): Promise<InitResult> {
  const lines: Lines = { out: [], err: [], exit: 0 };
  if (!writeConfigStep(cwd, lines)) {
    return { stdout: lines.out.join(''), stderr: lines.err.join(''), exitCode: lines.exit };
  }
  writeBaselineStep(cwd, lines);
  await runPrompts(cwd, opts.prompter, lines);
  noteMissingDeps(cwd, lines);
  printSnippet(lines);
  return { stdout: lines.out.join(''), stderr: lines.err.join(''), exitCode: lines.exit };
}
