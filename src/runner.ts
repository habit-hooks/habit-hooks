import { dirname, isAbsolute, resolve } from 'node:path';
import { filterFilesForRule } from './rule-files.js';
import { discoverFiles } from './discover.js';
import { loadConfig, loadConfigFromPath } from './config/load.js';
import { collectConfigWarnings } from './config/warnings.js';
import { buildRules } from './rules/registry.js';
import { lookupPrompt } from './prompts/registry.js';
import { resolvePackagedDir } from './prompts/packaged-dir.js';
import { resolveScope, type ResolvedScope, type ScopeFlags, type ScopeMode } from './git/resolve-scope.js';
import { loadBaseline, type BaselineFile } from './baseline/store.js';
import { partitionBySnooze } from './baseline/filter.js';
import { createSnoozeIndex, type SnoozeIndex } from './baseline/snooze-index.js';
import { SensorRunner, satisfiableSensors } from './sensors/runner.js';
import { applyReplaceMode } from './sensors/needs-extraction.js';
import { issueToViolation, violationToIssue } from './sensors/preset.js';
import { buildDefaultSensors } from './sensors/registry.js';
import { buildSensors } from './sensors/build-sensors.js';
import { mapIssues, type MapperDirs, type RoutingLookup } from './mapper/mapper.js';
import { guide } from './guide/guide.js';
import type { SensorSink } from './wrap/notices.js';
import type { Sensor } from './sensors/types.js';
import type { HabitHooksConfig, SensorSpec } from './config/schema.js';
import type { Rule, Violation } from './types.js';

export interface RunResult {
  stdout: string;
  stderr: string[];
  exitCode: number;
  violations: Violation[];
  scopeMode: ScopeMode;
}

export interface RunOptions {
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
  language: string;
  promptsDir?: string;
  configWarnings: string[];
  needsExtractionReplace: boolean;
  sensorSpecs: Record<string, SensorSpec> | undefined;
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

interface ResolvedInputs {
  cwd: string;
  config: HabitHooksConfig;
  configDir: string;
  files: string[];
  scope: ResolvedScope;
  baseline: BaselineFile | null;
}

function buildRunContext(inputs: ResolvedInputs): RunContext {
  const { cwd, config, configDir, files, scope, baseline } = inputs;
  const promptsDir = resolvePromptsDir(config, configDir);
  const language: string = config.language ?? 'typescript';
  const configWarnings = collectConfigWarnings(config, language);
  const snoozeIndex = createSnoozeIndex(cwd);
  const needsExtractionReplace = config.needsExtraction?.replace === true;
  return { cwd, files, scope, baseline, snoozeIndex, language, promptsDir, configWarnings, needsExtractionReplace, sensorSpecs: config.sensors };
}

async function buildContext(cwd: string, options: RunOptions): Promise<{ ctx: RunContext; rules: Rule[] }> {
  const { config, configDir } = await resolveConfig(cwd, options);
  const rules = buildRules(config, configDir);
  const language: string = config.language ?? 'typescript';
  const files = await discoverFiles(cwd, language, { exclude: config.scope?.exclude, files: config.files });
  const scope = resolveScope(options.scopeFlags ?? {}, config.scope, cwd);
  const baseline = resolveBaseline(cwd, options);
  return { ctx: buildRunContext({ cwd, config, configDir, files, scope, baseline }), rules };
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

// When the consumer declares sensors, that set is authoritative; otherwise fall
// back to the language preset. Remove this fallback branch with the 1.0.0 release.
function assembleSensors(ctx: RunContext, rulesById: Map<string, Rule>, sink: SensorSink): Sensor[] {
  const input = { sink, cwd: ctx.cwd, rulesById };
  if (ctx.sensorSpecs !== undefined) return buildSensors(ctx.sensorSpecs, input);
  return buildDefaultSensors(ctx.language, input);
}

// Active sensors detect over the full discovered file set and their issues are
// merged; rule-scoped file filtering is applied afterwards so the sensor stage
// stays a pure smell detector (docs/sensors.md).
async function detect(ctx: RunContext, rules: Rule[]): Promise<{ violations: Violation[]; sink: SensorSink }> {
  const sink: SensorSink = { notices: [], failures: [] };
  const rulesById = new Map(rules.map((r) => [r.id, r] as const));
  const all = assembleSensors(ctx, rulesById, sink);
  const active = satisfiableSensors(all.filter((sensor) => sensorActive(sensor, rulesById, ctx)));
  const issues = await new SensorRunner(active).run({ files: ctx.files, cwd: ctx.cwd });
  const combined = applyReplaceMode(issues, ctx.needsExtractionReplace);
  return { violations: combined.map(issueToViolation), sink };
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
// (prompt registry) supplies severity/title for supplemental smells, so their
// enforced severity survives. Unknown smells -> uncoached.
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
  const rendered = await guide({ result: mapped, dirs, cwd });
  const exitCode = detected.sink.failures.length > 0 ? 1 : rendered.exitCode;
  const stderr = [...ctx.configWarnings, ...detected.sink.notices];
  return { stdout: rendered.stdout, exitCode, violations, stderr, scopeMode: ctx.scope.mode };
}
