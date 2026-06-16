import { isAbsolute, resolve } from 'node:path';
import type { CommentCheckThresholds, Rule } from '../types.js';
import { DEFAULT_COMMENT_CHECK_THRESHOLDS } from '../checks/comment-check.js';
import { defaultConfig, defaultRules } from '../config/defaults.js';
import { mergeRules } from '../config/merge.js';
import { COMMENT_SMELL } from '../config/tool-smells.js';
import type { CommentCheckConfig, HabitHooksConfig } from '../config/schema.js';
import { loadGuidance } from '../prompts/loader.js';

function resolvePromptsDir(config: HabitHooksConfig, configDir: string): string | undefined {
  if (config.prompts === undefined) return undefined;
  return isAbsolute(config.prompts) ? config.prompts : resolve(configDir, config.prompts);
}

function attachGuidanceToRule(rule: Rule, overrideDir: string | undefined): Rule {
  const guidance = loadGuidance(rule.id, { overrideDir });
  if (guidance === null) return rule;
  return { ...rule, guidance };
}

function attachGuidance(rules: Rule[], overrideDir: string | undefined): Rule[] {
  return rules.map((rule) => attachGuidanceToRule(rule, overrideDir));
}

function resolveCommentThresholds(config: CommentCheckConfig | undefined): CommentCheckThresholds {
  return {
    maxSingleLineChars: config?.maxSingleLineChars ?? DEFAULT_COMMENT_CHECK_THRESHOLDS.maxSingleLineChars,
    maxBlockChars: config?.maxBlockChars ?? DEFAULT_COMMENT_CHECK_THRESHOLDS.maxBlockChars,
  };
}

function attachCommentThresholds(rules: Rule[], config: CommentCheckConfig | undefined): Rule[] {
  const thresholds = resolveCommentThresholds(config);
  return rules.map((rule) => (rule.id === COMMENT_SMELL ? { ...rule, commentCheck: thresholds } : rule));
}

export function buildRules(config: HabitHooksConfig, configDir: string): Rule[] {
  const merged = mergeRules(defaultRules, defaultConfig.smells, config.rules, config.smells);
  const overrideDir = resolvePromptsDir(config, configDir);
  const withGuidance = attachGuidance(merged, overrideDir);
  return attachCommentThresholds(withGuidance, config.commentCheck);
}
