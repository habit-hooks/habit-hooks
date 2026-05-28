import type { Check, CheckOutcome, Rule, Violation } from './types.js';

interface EslintFilterContext {
  resolveFilesForRule(_rule: Rule): string[];
  cwd: string;
}

function unionFiles(rules: Rule[], ctx: EslintFilterContext): string[] {
  const seen = new Set<string>();
  for (const rule of rules) {
    for (const file of ctx.resolveFilesForRule(rule)) seen.add(file);
  }
  return [...seen];
}

function ruleAllowsViolation(rule: Rule, file: string, ctx: EslintFilterContext): boolean {
  return ctx.resolveFilesForRule(rule).includes(file);
}

function filterEslintViolations(violations: Violation[], rules: Rule[], ctx: EslintFilterContext): Violation[] {
  const byId = new Map(rules.map((r) => [r.id, r] as const));
  return violations.filter((v) => {
    const rule = byId.get(v.ruleId);
    if (rule === undefined) return true;
    return ruleAllowsViolation(rule, v.file, ctx);
  });
}

function normalizeOutcome(result: Violation[] | CheckOutcome): CheckOutcome {
  if (Array.isArray(result)) return { violations: result };
  return result;
}

export async function runEslintSource(
  rules: Rule[],
  ctx: EslintFilterContext,
  check: Check,
): Promise<CheckOutcome> {
  const selected = rules.filter((rule) => rule.source === 'eslint');
  const files = unionFiles(selected, ctx);
  if (files.length === 0) return { violations: [], stderr: [] };
  const outcome = normalizeOutcome(await check.run(files, selected, ctx.cwd));
  return { violations: filterEslintViolations(outcome.violations, selected, ctx), stderr: outcome.stderr ?? [] };
}
