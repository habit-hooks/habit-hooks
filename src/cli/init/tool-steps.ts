import { scaffoldEslintConfig } from './scaffold-eslint-config.js';
import { scaffoldKnipConfig } from './scaffold-knip-config.js';
import { scaffoldJscpdConfig } from './scaffold-jscpd-config.js';
import { detectToolStates, toolsForLanguage, type ToolName, type ToolState } from './detect.js';
import { buildInstallCommand, detectPackageManager, packagesFor } from './install-commands.js';
import { dryRunPath, noteScaffold, type Ctx } from './ctx.js';
import type { ScaffoldResult } from './scaffold-config.js';

const SCAFFOLDERS: Partial<Record<ToolName, (_cwd: string) => ScaffoldResult>> = {
  eslint: scaffoldEslintConfig,
  knip: scaffoldKnipConfig,
  jscpd: scaffoldJscpdConfig,
};

const DEFAULT_FILENAMES: Partial<Record<ToolName, string>> = {
  eslint: 'eslint.config.js',
  knip: 'knip.json',
  jscpd: '.jscpd.json',
};

function hasScaffolder(tool: ToolName): boolean {
  return SCAFFOLDERS[tool] !== undefined;
}

const KNIP_STARTER_NOTE =
  'knip.json written with starter entry points. Edit `entry` in knip.json to match your project.\n';

function noteKnipStarter(ctx: Ctx, result: ScaffoldResult): void {
  if (result.created) ctx.lines.out.push(KNIP_STARTER_NOTE);
}

function scaffoldFor(ctx: Ctx, tool: ToolName): void {
  const scaffolder = SCAFFOLDERS[tool];
  const filename = DEFAULT_FILENAMES[tool];
  if (scaffolder === undefined || filename === undefined) return;
  if (ctx.dryRun) {
    dryRunPath(ctx, filename, `${tool} config`);
    return;
  }
  const result = scaffolder(ctx.cwd);
  noteScaffold(ctx, result, `${tool} config`);
  if (tool === 'knip') noteKnipStarter(ctx, result);
}

function handleTool(ctx: Ctx, tool: ToolName, state: ToolState): void {
  if (state.installed && state.configured) {
    ctx.lines.out.push(`${tool} already installed and configured\n`);
    return;
  }
  if (state.configured) ctx.lines.out.push(`${tool} config already present (binary missing)\n`);
  else scaffoldFor(ctx, tool);
}

function collectMissingTools(tools: ToolName[], matrix: Record<ToolName, ToolState>): ToolName[] {
  return tools.filter((t) => !matrix[t].installed);
}

function printInstallCommand(ctx: Ctx, missing: ToolName[]): void {
  if (missing.length === 0) return;
  const packages = missing.flatMap((t) => packagesFor(t));
  const command = buildInstallCommand(detectPackageManager(ctx.cwd), packages);
  ctx.lines.out.push(`\nTo install missing tools, run:\n  ${command}\n`);
}

export function runToolSteps(ctx: Ctx): void {
  const tools = toolsForLanguage(ctx.language).filter(hasScaffolder);
  // TODO(phase-3b): remove the python short-circuit — Python scaffolding +
  // completion guidance wires in here. jscpd has a scaffolder and is in the
  // python tool set, so this language check (not tools.length) is what keeps
  // .jscpd.json from being written into a Python project today.
  if (ctx.language === 'python' || tools.length === 0) return;
  const matrix = detectToolStates(ctx.cwd);
  for (const tool of tools) handleTool(ctx, tool, matrix[tool]);
  printInstallCommand(ctx, collectMissingTools(tools, matrix));
}
