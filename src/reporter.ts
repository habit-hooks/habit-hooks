import { loadGuidance } from './prompts/loader.js';
import { lookupPrompt } from './prompts/registry.js';
import type { CoachingPrompt, Rule, Violation } from './types.js';

function ruleGuidance(rule: Rule): string | null {
  if (rule.guidance !== undefined) return rule.guidance;
  return loadGuidance(rule.id);
}

function promptToRule(prompt: CoachingPrompt): Rule {
  return {
    id: prompt.id,
    source: 'custom',
    severity: 'suggested',
    changedFilesOnly: false,
    title: prompt.title,
    description: prompt.description,
  };
}

const MAX_PER_GROUP = 10;
const UNCOACHED_RULE_ID = 'uncoached';

interface ReportResult {
  stdout: string;
  exitCode: 0 | 1;
}

function groupByRule(violations: Violation[]): Map<string, Violation[]> {
  const groups = new Map<string, Violation[]>();
  for (const v of violations) {
    const list = groups.get(v.ruleId) ?? [];
    list.push(v);
    groups.set(v.ruleId, list);
  }
  return groups;
}

function renderRuleHeader(rule: Rule): string {
  const guidance = ruleGuidance(rule);
  const tail = guidance === null ? '' : `\n${guidance}`;
  return `❌ ${rule.title}\n${rule.description}${tail}`;
}

function formatViolation(v: Violation): string {
  return `- ${v.file}:${v.line} - ${v.message}`;
}

function renderViolationsList(rule: Rule, violations: Violation[]): string {
  const shown = violations.slice(0, MAX_PER_GROUP);
  const lines = ['Violations:', ...shown.map(formatViolation)];
  const remaining = violations.length - shown.length;
  if (remaining > 0) {
    lines.push(`(${remaining} more ${rule.id} violations)`);
  }
  return lines.join('\n');
}

function renderGroup(rule: Rule, violations: Violation[]): string {
  return `${renderRuleHeader(rule)}\n\n${renderViolationsList(rule, violations)}`;
}

function renderHeader(total: number): string {
  if (total === 0) {
    return '✅ Habit Hooks: automated checks passed.\n\nHabit Hooks catches structural smells, not correctness or design. If no reviewer sub-agent has reviewed this change set, run one before declaring done.';
  }
  const noun = total === 1 ? 'violation' : 'violations';
  return `❌ Habit Hooks: ${total} ${noun}`;
}

interface RenderAcc {
  sections: string[];
  exitCode: 0 | 1;
  consumed: Set<string>;
}

function appendRuleSection(acc: RenderAcc, rule: Rule, group: Violation[] | undefined): void {
  if (!group || group.length === 0) return;
  acc.sections.push('');
  acc.sections.push(renderGroup(rule, group));
  acc.consumed.add(rule.id);
  if (rule.severity === 'enforced') acc.exitCode = 1;
}

function appendKnownRules(acc: RenderAcc, rules: Rule[], groups: Map<string, Violation[]>): void {
  for (const rule of rules) appendRuleSection(acc, rule, groups.get(rule.id));
}

function appendPromptOnlyGroups(acc: RenderAcc, groups: Map<string, Violation[]>): void {
  for (const [ruleId, group] of groups) {
    if (acc.consumed.has(ruleId)) continue;
    const prompt = lookupPrompt(ruleId);
    if (prompt === null) continue;
    appendRuleSection(acc, promptToRule(prompt), group);
  }
}

function collectUncoached(acc: RenderAcc, groups: Map<string, Violation[]>): Violation[] {
  const out: Violation[] = [];
  for (const [ruleId, group] of groups) {
    if (acc.consumed.has(ruleId)) continue;
    out.push(...group);
  }
  return out;
}

function formatUncoachedLine(v: Violation): string {
  return `- ${v.ruleId}: ${v.message} (${v.file}:${v.line})`;
}

function renderUncoachedBody(violations: Violation[]): string {
  const header = loadGuidance(UNCOACHED_RULE_ID);
  const intro = header === null ? '' : `${header}\n\n`;
  return `${intro}${violations.map(formatUncoachedLine).join('\n')}`;
}

function appendUncoachedSection(acc: RenderAcc, uncoached: Violation[]): void {
  if (uncoached.length === 0) return;
  acc.sections.push('');
  acc.sections.push(`⚠️ Uncoached rules\n\n${renderUncoachedBody(uncoached)}`);
}

export function report(violations: Violation[], rules: Rule[]): ReportResult {
  const groups = groupByRule(violations);
  const acc: RenderAcc = {
    sections: [renderHeader(violations.length)],
    exitCode: 0,
    consumed: new Set<string>(),
  };
  appendKnownRules(acc, rules, groups);
  appendPromptOnlyGroups(acc, groups);
  appendUncoachedSection(acc, collectUncoached(acc, groups));
  return { stdout: `${acc.sections.join('\n')}\n`, exitCode: acc.exitCode };
}
