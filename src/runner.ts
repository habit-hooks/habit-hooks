import { dirname, relative } from 'node:path';
import fg from 'fast-glob';
import picomatch from 'picomatch';
import { loadConfig, loadConfigFromPath } from './config/load.js';
import { buildRules } from './rules/registry.js';
import { report } from './reporter.js';
import { resolveScope, type ResolvedScope, type ScopeFlags } from './git/resolve-scope.js';
import { loadBaseline, type BaselineFile } from './baseline/store.js';
import { partitionBySnooze } from './baseline/filter.js';
import { SensorRunner } from './sensors/runner.js';
import { buildPresetSensors, issueToViolation } from './sensors/preset.js';
import type { HabitHooksConfig } from './config/schema.js';
import type { Rule, Violation } from './types.js';

const COMMENT_SMELL = 'non-essential-comment';

interface RunResult {
  stdout: string;
  stderr: string[];
  exitCode: number;
  violations: Violation[];
}

interface RunOptions {
  configPath?: string;
  scopeFlags?: ScopeFlags;
  applyBaseline?: boolean;
}

interface RunContext {
  cwd: string;
  files: string[];
  scope: ResolvedScope;
  baseline: BaselineFile | null;
}

async function discoverFiles(cwd: string): Promise<string[]> {
  return fg(['**/*.{ts,tsx,js,mjs,cjs}'], {
    cwd,
    absolute: true,
    ignore: ['**/node_modules/**', '**/dist/**', '**/coverage/**'],
    dot: false,
  });
}

function buildMatcher(patterns: string[] | undefined): ((_path: string) => boolean) | null {
  if (!patterns || patterns.length === 0) return null;
  return picomatch(patterns);
}

function filterFilesForRule(rule: Rule, files: string[], cwd: string): string[] {
  const includeMatcher = buildMatcher(rule.include);
  const excludeMatcher = buildMatcher(rule.exclude);
  if (!includeMatcher && !excludeMatcher) return files;
  return files.filter((file) => {
    const rel = relative(cwd, file);
    if (includeMatcher && !includeMatcher(rel)) return false;
    if (excludeMatcher && excludeMatcher(rel)) return false;
    return true;
  });
}

function applyScopeToRule(rule: Rule, files: string[], scope: ResolvedScope): string[] {
  if (!rule.changedFilesOnly) return files;
  const changed = scope.changedFiles;
  if (changed === null) return files;
  return files.filter((file) => changed.has(file));
}

function applyBaselineToRule(files: string[], ctx: RunContext): string[] {
  if (ctx.baseline === null) return files;
  return partitionBySnooze(files, ctx.baseline, ctx.cwd).active;
}

function resolveFilesForRule(rule: Rule, ctx: RunContext): string[] {
  const filtered = filterFilesForRule(rule, ctx.files, ctx.cwd);
  const scoped = applyScopeToRule(rule, filtered, ctx.scope);
  return applyBaselineToRule(scoped, ctx);
}

async function resolveConfig(
  cwd: string,
  options: RunOptions,
): Promise<{ config: HabitHooksConfig; configDir: string }> {
  if (options.configPath !== undefined) {
    const loaded = await loadConfigFromPath(options.configPath);
    return { config: loaded.config, configDir: dirname(options.configPath) };
  }
  const loaded = await loadConfig(cwd);
  const configDir = loaded.sourcePath ? dirname(loaded.sourcePath) : cwd;
  return { config: loaded.config, configDir };
}

function resolveBaseline(cwd: string, options: RunOptions): BaselineFile | null {
  if (options.applyBaseline === false) return null;
  return loadBaseline(cwd);
}

async function buildContext(cwd: string, options: RunOptions): Promise<{ ctx: RunContext; rules: Rule[] }> {
  const { config, configDir } = await resolveConfig(cwd, options);
  const rules = buildRules(config, configDir);
  const files = await discoverFiles(cwd);
  const scope = resolveScope(options.scopeFlags ?? {}, config.scope, cwd);
  const baseline = resolveBaseline(cwd, options);
  return { ctx: { cwd, files, scope, baseline }, rules };
}

// Detection runs every preset sensor over the full discovered file set and
// merges their issues; rule-scoped file filtering is applied afterwards so the
// sensor stage stays a pure smell detector (docs/sensors.md).
async function detect(ctx: RunContext, rules: Rule[]): Promise<{ violations: Violation[]; notices: string[] }> {
  const notices: string[] = [];
  const commentRule = rules.find((r) => r.id === COMMENT_SMELL);
  const runner = new SensorRunner(buildPresetSensors({ notices, commentRule }));
  const issues = await runner.run({ files: ctx.files, cwd: ctx.cwd });
  return { violations: issues.map(issueToViolation), notices };
}

function allowedFilesBySmell(rules: Rule[], ctx: RunContext): Map<string, Set<string>> {
  const map = new Map<string, Set<string>>();
  for (const rule of rules) map.set(rule.id, new Set(resolveFilesForRule(rule, ctx)));
  return map;
}

// A violation whose smell has a configured rule is kept only when its file is in
// that rule's resolved set; an uncoached smell (no rule) is never file-filtered,
// matching the legacy per-source dispatch.
function filterViolations(violations: Violation[], rules: Rule[], ctx: RunContext): Violation[] {
  const allowed = allowedFilesBySmell(rules, ctx);
  return violations.filter((v) => {
    const set = allowed.get(v.ruleId);
    return set === undefined ? true : set.has(v.file);
  });
}

export async function run(cwd: string, options: RunOptions = {}): Promise<RunResult> {
  const { ctx, rules } = await buildContext(cwd, options);
  const detected = await detect(ctx, rules);
  const violations = filterViolations(detected.violations, rules, ctx);
  const reported = report(violations, rules);
  return { ...reported, violations, stderr: detected.notices };
}
