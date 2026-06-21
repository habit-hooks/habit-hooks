import type { HookResult } from './git-hook.js';
import type { ScriptResult } from './package-scripts.js';
import type { SkillResult } from './skill.js';

export interface Lines {
  out: string[];
  err: string[];
  exit: number;
}

function emitConflict(lines: Lines, message: string): void {
  lines.err.push(`habit-hooks: ${message}\n`);
  lines.exit = 2;
}

export function reportScriptResult(name: string, result: ScriptResult, lines: Lines): void {
  if (result.action === 'added') lines.out.push(`added '${name}' to package.json scripts\n`);
  else if (result.action === 'kept') lines.out.push(`'${name}' already set as desired in package.json\n`);
  else if (result.action === 'no-package-json') lines.out.push(`skipped '${name}': no package.json in cwd\n`);
  else if (result.action === 'conflict') {
    emitConflict(lines, `refusing to replace '${name}' script (currently: ${result.before ?? '<unknown>'})`);
  }
}

export function reportHookResult(result: HookResult, lines: Lines): void {
  if (result.action === 'installed') lines.out.push(`installed pre-commit hook at ${result.path}\n`);
  else if (result.action === 'kept') lines.out.push(`pre-commit hook already installed at ${result.path}\n`);
  else if (result.action === 'conflict') {
    lines.out.push(`pre-commit hook already exists at ${result.path} — left untouched\n`);
  } else if (result.action === 'no-git') {
    lines.out.push(`skipped pre-commit hook: no .git directory in cwd\n`);
  }
}

function reportSkillResult(result: SkillResult, lines: Lines): void {
  if (result.action === 'installed') lines.out.push(`installed ${result.name} at ${result.target}\n`);
  else if (result.action === 'kept') lines.out.push(`${result.name} already at ${result.target}\n`);
  else if (result.action === 'conflict') {
    lines.out.push(`${result.name} already exists at ${result.target} — left untouched\n`);
  } else if (result.action === 'source-missing') {
    lines.err.push(`habit-hooks: could not find packaged SKILL.md for ${result.name} — skipping\n`);
  }
}

export function reportSkillResults(results: SkillResult[], lines: Lines): void {
  for (const result of results) reportSkillResult(result, lines);
}
