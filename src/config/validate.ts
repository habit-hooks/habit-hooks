import type { Severity, RuleSource } from '../types.js';
import type {
  CommentCheckConfig,
  HabitHooksConfig,
  NeedsExtractionConfig,
  RuleDefinition,
  RuleOverride,
  ScopeConfig,
} from './schema.js';
import {
  fail,
  isPlainObject,
  validateOptionalString,
  validateOptionalStringArray,
} from './validate-primitives.js';
import { validateFiles, validateSensors } from './validate-sensors.js';

const SEVERITIES: readonly Severity[] = ['enforced', 'suggested'];
const SOURCES: readonly RuleSource[] = ['eslint', 'jscpd', 'knip', 'custom'];

function validateOptionalBoolean(value: unknown, path: string): void {
  if (value === undefined) return;
  if (typeof value !== 'boolean') fail(path, 'a boolean');
}

function validateSeverity(value: unknown, path: string): void {
  if (value === undefined) return;
  if (typeof value !== 'string' || !SEVERITIES.includes(value as Severity)) {
    fail(path, `'enforced' or 'suggested'`);
  }
}

function validateSource(value: unknown, path: string): void {
  if (typeof value !== 'string' || !SOURCES.includes(value as RuleSource)) {
    fail(path, `one of 'eslint', 'jscpd', 'knip', 'custom'`);
  }
}

function validateRuleOverrideFields(entry: Record<string, unknown>, base: string): void {
  validateSeverity(entry.severity, `${base}.severity`);
  validateOptionalBoolean(entry.changedFilesOnly, `${base}.changedFilesOnly`);
  validateOptionalString(entry.title, `${base}.title`);
  validateOptionalString(entry.description, `${base}.description`);
  validateOptionalBoolean(entry.disabled, `${base}.disabled`);
  validateOptionalStringArray(entry.include, `${base}.include`);
  validateOptionalStringArray(entry.exclude, `${base}.exclude`);
  validateOptionalString(entry.fix, `${base}.fix`);
}

function validateRuleDefinitionFields(
  entry: Record<string, unknown>,
  base: string,
): void {
  if (typeof entry.id !== 'string') fail(`${base}.id`, 'a string');
  validateSource(entry.source, `${base}.source`);
  validateOptionalString(entry.sourceRuleId, `${base}.sourceRuleId`);
}

function validateRuleEntry(value: unknown, base: string): RuleOverride | RuleDefinition {
  if (!isPlainObject(value)) fail(base, 'an object');
  const entry = value;
  validateRuleOverrideFields(entry, base);
  if ('source' in entry) {
    validateRuleDefinitionFields(entry, base);
  }
  return entry as RuleOverride | RuleDefinition;
}

function validateEntryMap(value: unknown, field: string): HabitHooksConfig['rules'] {
  if (value === undefined) return undefined;
  if (!isPlainObject(value)) fail(field, 'an object keyed by smell key');
  const result: Record<string, RuleOverride | RuleDefinition> = {};
  for (const [key, entry] of Object.entries(value)) {
    result[key] = validateRuleEntry(entry, `${field}.${key}`);
  }
  return result;
}

function validateScope(value: unknown): ScopeConfig | undefined {
  if (value === undefined) return undefined;
  if (!isPlainObject(value)) fail('scope', 'an object');
  validateOptionalBoolean(value.onlyChangedFiles, 'scope.onlyChangedFiles');
  validateOptionalBoolean(value.autoBranchOffMain, 'scope.autoBranchOffMain');
  validateOptionalString(value.branchBase, 'scope.branchBase');
  validateOptionalString(value.mainBranch, 'scope.mainBranch');
  validateOptionalStringArray(value.exclude, 'scope.exclude');
  return value as ScopeConfig;
}

function validatePositiveInteger(value: unknown, path: string): void {
  if (value === undefined) return;
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    fail(path, 'a positive integer');
  }
}

function validateCommentCheck(value: unknown): CommentCheckConfig | undefined {
  if (value === undefined) return undefined;
  if (!isPlainObject(value)) fail('commentCheck', 'an object');
  validatePositiveInteger(value.maxSingleLineChars, 'commentCheck.maxSingleLineChars');
  validatePositiveInteger(value.maxBlockChars, 'commentCheck.maxBlockChars');
  return value as CommentCheckConfig;
}

function validateLanguage(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value !== 'string' || value.length === 0) {
    fail('language', 'a non-empty string');
  }
  return value;
}

function validateNeedsExtraction(value: unknown): NeedsExtractionConfig | undefined {
  if (value === undefined) return undefined;
  if (!isPlainObject(value)) fail('needsExtraction', 'an object');
  validateOptionalBoolean(value.replace, 'needsExtraction.replace');
  return value as NeedsExtractionConfig;
}

interface ValidatedParts {
  prompts?: string;
  language: string | undefined;
  smells: HabitHooksConfig['smells'];
  rules: HabitHooksConfig['rules'];
  scope: ScopeConfig | undefined;
  commentCheck: CommentCheckConfig | undefined;
  needsExtraction: NeedsExtractionConfig | undefined;
  sensors: HabitHooksConfig['sensors'];
  files: string[] | undefined;
}

function assembleConfig(parts: ValidatedParts): HabitHooksConfig {
  const config: HabitHooksConfig = {};
  for (const [key, value] of Object.entries(parts)) {
    if (value !== undefined) (config as Record<string, unknown>)[key] = value;
  }
  return config;
}

function validateParts(value: Record<string, unknown>): ValidatedParts {
  return {
    prompts: typeof value.prompts === 'string' ? value.prompts : undefined,
    language: validateLanguage(value.language),
    smells: validateEntryMap(value.smells, 'smells'),
    rules: validateEntryMap(value.rules, 'rules'),
    scope: validateScope(value.scope),
    ...validateRemainingParts(value),
  };
}

function validateRemainingParts(value: Record<string, unknown>) {
  return {
    commentCheck: validateCommentCheck(value.commentCheck),
    needsExtraction: validateNeedsExtraction(value.needsExtraction),
    sensors: validateSensors(value.sensors),
    files: validateFiles(value.files),
  };
}

export function validateConfig(value: unknown): HabitHooksConfig {
  if (!isPlainObject(value)) fail('config', 'an object');
  validateOptionalString(value.prompts, 'prompts');
  return assembleConfig(validateParts(value));
}
