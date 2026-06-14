import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { scaffoldConfig, type ScaffoldResult } from './scaffold-config.js';
import { scaffoldBaseline } from './scaffold-baseline.js';
import { scaffoldEslintConfig } from './scaffold-eslint-config.js';
import { scaffoldKnipConfig } from './scaffold-knip-config.js';
import { scaffoldJscpdConfig } from './scaffold-jscpd-config.js';
import { detectToolStates, type ToolName, type ToolState } from './detect.js';
import {
  buildInstallCommand,
  detectPackageManager,
  packagesFor,
} from './install-commands.js';
import { addCiScript, addHabitHooksScript } from './package-scripts.js';
import { installPreCommitHook } from './git-hook.js';
import { installSkills } from './skill.js';
import { AGENT_SNIPPET } from './snippet.js';
import {
  reportHookResult,
  reportScriptResult,
  reportSkillResults,
  type Lines,
} from './reporters.js';
import type { Prompter } from './prompts.js';

interface InitOptions {
  prompter: Prompter;
  dryRun?: boolean;
}

interface InitResult {
  stdout: string;
  stderr: string;
  exitCode: number;
}

interface Ctx {
  cwd: string;
  lines: Lines;
  dryRun: boolean;
}

function noteScaffold(ctx: Ctx, result: ScaffoldResult, label: string): void {
  if (result.created) ctx.lines.out.push(`wrote ${result.path}\n`);
  else ctx.lines.out.push(`${label} already present at ${result.path}\n`);
}

function dryRunPath(ctx: Ctx, filename: string, label: string): void {
  const path = join(ctx.cwd, filename);
  if (existsSync(path)) ctx.lines.out.push(`${label} already present at ${path}\n`);
  else ctx.lines.out.push(`[dry-run] would write ${path}\n`);
}

const SCAFFOLDERS: Record<ToolName, (_cwd: string) => ScaffoldResult> = {
  eslint: scaffoldEslintConfig,
  knip: scaffoldKnipConfig,
  jscpd: scaffoldJscpdConfig,
};

const DEFAULT_FILENAMES: Record<ToolName, string> = {
  eslint: 'eslint.config.js',
  knip: 'knip.json',
  jscpd: '.jscpd.json',
};

const KNIP_STARTER_NOTE =
  'knip.json written with starter entry points. Edit `entry` in knip.json to match your project.\n';

function noteKnipStarter(ctx: Ctx, result: ScaffoldResult): void {
  if (result.created) ctx.lines.out.push(KNIP_STARTER_NOTE);
}

function scaffoldFor(ctx: Ctx, tool: ToolName): void {
  if (ctx.dryRun) {
    dryRunPath(ctx, DEFAULT_FILENAMES[tool], `${tool} config`);
    return;
  }
  const result = SCAFFOLDERS[tool](ctx.cwd);
  noteScaffold(ctx, result, `${tool} config`);
  if (tool === 'knip') noteKnipStarter(ctx, result);
}

function noteToolPresent(ctx: Ctx, tool: ToolName): void {
  ctx.lines.out.push(`${tool} already installed and configured\n`);
}

function noteConfigured(ctx: Ctx, tool: ToolName): void {
  ctx.lines.out.push(`${tool} config already present (binary missing)\n`);
}

function handleTool(ctx: Ctx, tool: ToolName, state: ToolState): void {
  if (state.installed && state.configured) {
    noteToolPresent(ctx, tool);
    return;
  }
  if (state.configured) noteConfigured(ctx, tool);
  else scaffoldFor(ctx, tool);
}

function collectMissingTools(matrix: Record<ToolName, ToolState>): ToolName[] {
  return (Object.keys(matrix) as ToolName[]).filter((t) => !matrix[t].installed);
}

function printInstallCommand(ctx: Ctx, missing: ToolName[]): void {
  if (missing.length === 0) return;
  const packages = missing.flatMap((t) => packagesFor(t));
  const command = buildInstallCommand(detectPackageManager(ctx.cwd), packages);
  ctx.lines.out.push(`\nTo install missing tools, run:\n  ${command}\n`);
}

function runToolSteps(ctx: Ctx): void {
  const matrix = detectToolStates(ctx.cwd);
  for (const tool of Object.keys(matrix) as ToolName[]) {
    handleTool(ctx, tool, matrix[tool]);
  }
  printInstallCommand(ctx, collectMissingTools(matrix));
}

function writeConfigStep(ctx: Ctx): void {
  if (ctx.dryRun) {
    dryRunPath(ctx, 'habit-hooks.config.js', 'habit-hooks config');
    return;
  }
  noteScaffold(ctx, scaffoldConfig(ctx.cwd), 'habit-hooks config');
}

function writeBaselineStep(ctx: Ctx): void {
  if (ctx.dryRun) {
    dryRunPath(ctx, '.habit-hooks-baseline.json', 'baseline');
    return;
  }
  const result = scaffoldBaseline(ctx.cwd);
  if (result.created) ctx.lines.out.push(`wrote ${result.path}\n`);
  else ctx.lines.out.push(`baseline already present at ${result.path}\n`);
}

async function maybeAddHabitHooksScript(ctx: Ctx, prompter: Prompter): Promise<void> {
  if (ctx.dryRun) return;
  const yes = await prompter.ask("Add 'habit-hooks' to package.json scripts?", { defaultYes: true });
  if (!yes) return;
  reportScriptResult('habit-hooks', addHabitHooksScript(ctx.cwd), ctx.lines);
}

async function maybeAddCiScript(ctx: Ctx, prompter: Prompter): Promise<void> {
  if (ctx.dryRun) return;
  const yes = await prompter.ask("Wire 'npm run ci' as the full quality gate?", { defaultYes: true });
  if (!yes) return;
  reportScriptResult('ci', addCiScript(ctx.cwd), ctx.lines);
}

async function maybeInstallHook(ctx: Ctx, prompter: Prompter): Promise<void> {
  if (ctx.dryRun) return;
  const yes = await prompter.ask('Install a git pre-commit hook?', { defaultYes: false });
  if (!yes) return;
  reportHookResult(installPreCommitHook(ctx.cwd), ctx.lines);
}

async function maybeInstallSkill(ctx: Ctx, prompter: Prompter): Promise<void> {
  if (ctx.dryRun) return;
  const yes = await prompter.ask(
    'Install the bundled habit-hooks skills into ~/.claude/skills/?',
    { defaultYes: false },
  );
  if (!yes) return;
  reportSkillResults(installSkills(), ctx.lines);
}

function printSnippet(lines: Lines): void {
  lines.out.push('\n--- paste into CLAUDE.md / AGENTS.md ---\n');
  lines.out.push(AGENT_SNIPPET);
  lines.out.push('--- end snippet ---\n');
}

async function runPrompts(ctx: Ctx, prompter: Prompter): Promise<void> {
  await maybeAddHabitHooksScript(ctx, prompter);
  await maybeAddCiScript(ctx, prompter);
  await maybeInstallHook(ctx, prompter);
  await maybeInstallSkill(ctx, prompter);
}

function toResult(lines: Lines): InitResult {
  return { stdout: lines.out.join(''), stderr: lines.err.join(''), exitCode: lines.exit };
}

export async function runInit(cwd: string, opts: InitOptions): Promise<InitResult> {
  const ctx: Ctx = { cwd, lines: { out: [], err: [], exit: 0 }, dryRun: opts.dryRun === true };
  runToolSteps(ctx);
  writeConfigStep(ctx);
  writeBaselineStep(ctx);
  await runPrompts(ctx, opts.prompter);
  printSnippet(ctx.lines);
  return toResult(ctx.lines);
}
