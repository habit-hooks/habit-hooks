import { loadGuidance } from './prompts/loader.js';
import type { Rule, Violation } from './types.js';

function guidanceFor(rule: Rule): string {
  return rule.guidance ?? loadGuidance(rule.id);
}

const MAX_PER_GROUP = 10;

export interface ReportResult {
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
  return `❌ ${rule.title}\n${rule.description}\n${guidanceFor(rule)}`;
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
    return '✅ Habit Hooks: clean';
  }
  const noun = total === 1 ? 'violation' : 'violations';
  return `❌ Habit Hooks: ${total} ${noun}`;
}

function appendRuleSection(
  acc: { sections: string[]; exitCode: 0 | 1 },
  rule: Rule,
  group: Violation[] | undefined,
): void {
  if (!group || group.length === 0) return;
  acc.sections.push('');
  acc.sections.push(renderGroup(rule, group));
  if (rule.severity === 'enforced') acc.exitCode = 1;
}

export function report(violations: Violation[], rules: Rule[]): ReportResult {
  const groups = groupByRule(violations);
  const acc = {
    sections: [renderHeader(violations.length)],
    exitCode: 0 as 0 | 1,
  };
  for (const rule of rules) appendRuleSection(acc, rule, groups.get(rule.id));
  return { stdout: `${acc.sections.join('\n')}\n`, exitCode: acc.exitCode };
}
