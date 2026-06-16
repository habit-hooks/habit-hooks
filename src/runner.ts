import { dirname, isAbsolute, relative, resolve } from 'node:path';
import picomatch from 'picomatch';
import { discoverFiles } from './discover.js';
import { loadConfig, loadConfigFromPath, RULES_DEPRECATION } from './config/load.js';
import { buildRules } from './rules/registry.js';
import { lookupPrompt } from './prompts/registry.js';
import { resolvePackagedDir } from './prompts/packaged-dir.js';
import { resolveScope, type ResolvedScope, type ScopeFlags } from './git/resolve-scope.js';
import { loadBaseline, type BaselineFile } from './baseline/store.js';
import { partitionBySnooze } from './baseline/filter.js';
import { createSnoozeIndex, type SnoozeIndex } from './baseline/snooze-index.js';
import { SensorRunner } from './sensors/runner.js';
import { buildPresetSensors, issueToViolation, violationToIssue } from './sensors/preset.js';
import { buildPythonPresetSensors } from './sensors/python-preset.js';
import { mapIssues, type MapperDirs, type RoutingLookup } from './mapper/mapper.js';
import { guide } from './guide/guide.js';
import type { Sensor } from './sensors/types.js';
import type { HabitHooksConfig, Language } from './config/schema.js';
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
  snoozeIndex: SnoozeIndex;
  language: Language;
  promptsDir?: string;
  configWarnings: string[];
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
  return partitionBySnooze(files, ctx.baseline, ctx.snoozeIndex).active;
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

function resolvePromptsDir(config: HabitHooksConfig, configDir: string): string | undefined {
  if (config.prompts === undefined) return undefined;
  return isAbsolute(config.prompts) ? config.prompts : resolve(configDir, config.prompts);
}

async function buildContext(cwd: string, options: RunOptions): Promise<{ ctx: RunContext; rules: Rule[] }> {
  const { config, configDir } = await resolveConfig(cwd, options);
  const rules = buildRules(config, configDir);
  const language: Language = config.language ?? 'typescript';
  const files = await discoverFiles(cwd, language);
  const scope = resolveScope(options.scopeFlags ?? {}, config.scope, cwd);
  const baseline = resolveBaseline(cwd, options);
  const promptsDir = resolvePromptsDir(config, configDir);
  const configWarnings = config.rules !== undefined ? [RULES_DEPRECATION] : [];
  const snoozeIndex = createSnoozeIndex(cwd);
  return { ctx: { cwd, files, scope, baseline, snoozeIndex, language, promptsDir, configWarnings }, rules };
}

// A sensor runs only when at least one smell it produces has an active rule
// resolving to a non-empty file set. This reproduces the legacy "a tool runs
// iff its source has an active in-scope rule" gate, so disabling or
// empty-scoping a sensor's smells suppresses the whole tool (including its
// uncoached sibling smells) rather than letting its findings leak through.
function sensorActive(sensor: Sensor, rulesById: Map<string, Rule>, ctx: RunContext): boolean {
  return sensor.produces.some((smell) => {
    const rule = rulesById.get(smell);
    return rule !== undefined && resolveFilesForRule(rule, ctx).length > 0;
  });
}

// Active sensors detect over the full discovered file set and their issues are
// merged; rule-scoped file filtering is applied afterwards so the sensor stage
// stays a pure smell detector (docs/sensors.md).
function presetSensors(ctx: RunContext, rulesById: Map<string, Rule>, notices: string[]): Sensor[] {
  if (ctx.language === 'python') return buildPythonPresetSensors({ notices });
  return buildPresetSensors({ notices, commentRule: rulesById.get(COMMENT_SMELL) });
}

async function detect(ctx: RunContext, rules: Rule[]): Promise<{ violations: Violation[]; notices: string[] }> {
  const notices: string[] = [];
  const rulesById = new Map(rules.map((r) => [r.id, r] as const));
  const all = presetSensors(ctx, rulesById, notices);
  const active = all.filter((sensor) => sensorActive(sensor, rulesById, ctx));
  const issues = await new SensorRunner(active).run({ files: ctx.files, cwd: ctx.cwd });
  return { violations: issues.map(issueToViolation), notices };
}

// Keep a violation when its smell has no rule (uncoached), or its file is not a
// discovered source file (a project-level artifact like pyproject.toml reported
// by a whole-project sensor), or its file is in the rule's resolved set.
function filterViolations(violations: Violation[], rules: Rule[], ctx: RunContext): Violation[] {
  const allowed = new Map(rules.map((rule) => [rule.id, new Set(resolveFilesForRule(rule, ctx))] as const));
  const sourceFiles = new Set(ctx.files);
  return violations.filter((v) => {
    const set = allowed.get(v.ruleId);
    if (set === undefined || !sourceFiles.has(v.file)) return true;
    return set.has(v.file);
  });
}

// Routing for the mapper: the merged smell config wins; otherwise the catalogue
// (prompt registry) supplies severity/title for supplemental smells such as
// `parse-error`, so its `enforced` severity survives. Unknown smells -> uncoached.
function buildRouting(rules: Rule[]): RoutingLookup {
  const byId = new Map(rules.map((r) => [r.id, r] as const));
  return (smell) => {
    const rule = byId.get(smell);
    if (rule !== undefined) {
      return { severity: rule.severity, fix: rule.fix, title: rule.title, description: rule.description };
    }
    const prompt = lookupPrompt(smell);
    if (prompt === null) return undefined;
    return { severity: prompt.severity, title: prompt.title, description: prompt.description };
  };
}

export async function run(cwd: string, options: RunOptions = {}): Promise<RunResult> {
  const { ctx, rules } = await buildContext(cwd, options);
  const detected = await detect(ctx, rules);
  const violations = filterViolations(detected.violations, rules, ctx);
  const dirs: MapperDirs = { overrideDir: ctx.promptsDir, packagedDir: resolvePackagedDir() };
  const mapped = mapIssues(violations.map(violationToIssue), buildRouting(rules), dirs);
  const rendered = guide({ result: mapped, dirs });
  const stderr = [...ctx.configWarnings, ...detected.notices];
  return { stdout: rendered.stdout, exitCode: rendered.exitCode, violations, stderr };
}
