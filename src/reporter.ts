import { loadGuidance } from './prompts/loader.js';
import type { Rule, Violation } from './types.js';

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
  const guidance = loadGuidance(rule.id);
  return `❌ ${rule.title}\n${rule.description}\n${guidance}`;
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

export function report(violations: Violation[], rules: Rule[]): ReportResult {
  const groups = groupByRule(violations);
  const sections: string[] = [renderHeader(violations.length)];
  let exitCode: 0 | 1 = 0;

  for (const rule of rules) {
    const group = groups.get(rule.id);
    if (!group || group.length === 0) continue;
    sections.push('');
    sections.push(renderGroup(rule, group));
    if (rule.severity === 'enforced') exitCode = 1;
  }

  return { stdout: `${sections.join('\n')}\n`, exitCode };
}
