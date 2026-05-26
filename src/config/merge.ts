import type { Rule } from '../types.js';
import {
  isRuleDefinition,
  type HabitHooksConfig,
  type RuleDefinition,
  type RuleOverride,
} from './schema.js';

type MergedEntry = RuleOverride;

function pickDefined<T extends object>(source: T): Partial<T> {
  const result: Partial<T> = {};
  for (const key of Object.keys(source) as (keyof T)[]) {
    if (source[key] !== undefined) result[key] = source[key];
  }
  return result;
}

function stripMetaFields(override: RuleOverride): Omit<RuleOverride, 'disabled'> {
  const { disabled, ...rest } = override;
  void disabled;
  return rest;
}

function applyOverride(base: Rule, override: RuleOverride): Rule {
  return { ...base, ...pickDefined(stripMetaFields(override)) };
}

function pickRuleCore(def: RuleDefinition): Pick<Rule, 'source' | 'sourceRuleId' | 'severity' | 'changedFilesOnly'> {
  return {
    source: def.source,
    sourceRuleId: def.sourceRuleId,
    severity: def.severity ?? 'suggested',
    changedFilesOnly: def.changedFilesOnly ?? false,
  };
}

function pickRuleDisplay(id: string, def: RuleDefinition): Pick<Rule, 'title' | 'description' | 'eslintOptions' | 'include' | 'exclude'> {
  return {
    title: def.title ?? id,
    description: def.description ?? '',
    eslintOptions: def.eslintOptions,
    include: def.include,
    exclude: def.exclude,
  };
}

function buildCustomRule(id: string, def: RuleDefinition): Rule {
  return { id, ...pickRuleCore(def), ...pickRuleDisplay(id, def) };
}

function mergeEntry(existing: MergedEntry | undefined, entry: MergedEntry): MergedEntry {
  if (!existing || isRuleDefinition(existing) || isRuleDefinition(entry)) return entry;
  return { ...existing, ...entry };
}

function mergeOverrideMaps(
  sources: (HabitHooksConfig['rules'] | undefined)[],
): Map<string, MergedEntry> {
  const merged = new Map<string, MergedEntry>();
  for (const source of sources) {
    if (!source) continue;
    for (const [id, entry] of Object.entries(source)) {
      merged.set(id, mergeEntry(merged.get(id), entry));
    }
  }
  return merged;
}

function resolveDefaultRule(rule: Rule, entry: MergedEntry | undefined): Rule | null {
  if (entry === undefined) return rule;
  if (isRuleDefinition(entry)) return buildCustomRule(rule.id, entry);
  if (entry.disabled === true) return null;
  return applyOverride(rule, entry);
}

function resolveNewRule(id: string, entry: MergedEntry): Rule | null {
  if (!isRuleDefinition(entry)) {
    throw new Error(
      `Invalid habit-hooks config: rules.${id} is not a built-in rule and is missing 'source'`,
    );
  }
  if (entry.disabled === true) return null;
  return buildCustomRule(id, entry);
}

function applyDefaults(
  defaultRules: Rule[],
  entries: Map<string, MergedEntry>,
  seen: Set<string>,
): Rule[] {
  return defaultRules.flatMap((rule) => {
    seen.add(rule.id);
    const resolved = resolveDefaultRule(rule, entries.get(rule.id));
    return resolved ? [resolved] : [];
  });
}

function collectNewRules(
  entries: Map<string, MergedEntry>,
  seen: Set<string>,
): Rule[] {
  return [...entries].flatMap(([id, entry]) => {
    if (seen.has(id)) return [];
    const resolved = resolveNewRule(id, entry);
    return resolved ? [resolved] : [];
  });
}

export function mergeRules(
  defaultRules: Rule[],
  ...overrideSources: (HabitHooksConfig['rules'] | undefined)[]
): Rule[] {
  const entries = mergeOverrideMaps(overrideSources);
  const seen = new Set<string>();
  return [...applyDefaults(defaultRules, entries, seen), ...collectNewRules(entries, seen)];
}
