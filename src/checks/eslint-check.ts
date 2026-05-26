import { ESLint, type Linter } from 'eslint';
import tseslint from 'typescript-eslint';
import type { Check, Rule, Violation } from '../types.js';

function buildRuleConfig(rules: Rule[]): Linter.RulesRecord {
  const config: Linter.RulesRecord = {};
  for (const rule of rules) {
    if (rule.source !== 'eslint' || !rule.sourceRuleId) continue;
    const options = Array.isArray(rule.eslintOptions) ? rule.eslintOptions : [];
    config[rule.sourceRuleId] = ['error', ...options];
  }
  return config;
}

function buildSourceRuleIndex(rules: Rule[]): Map<string, Rule> {
  const index = new Map<string, Rule>();
  for (const rule of rules) {
    if (rule.source === 'eslint' && rule.sourceRuleId) {
      index.set(rule.sourceRuleId, rule);
    }
  }
  return index;
}

function createESLint(rules: Rule[]): ESLint {
  return new ESLint({
    overrideConfigFile: true,
    overrideConfig: [
      {
        files: ['**/*.ts', '**/*.tsx'],
        languageOptions: { parser: tseslint.parser },
      },
      { rules: buildRuleConfig(rules) },
    ],
  });
}

async function lintFiles(eslint: ESLint, files: string[]): Promise<ESLint.LintResult[]> {
  if (files.length === 0) return [];
  return eslint.lintFiles(files);
}

function collectViolations(
  results: ESLint.LintResult[],
  index: Map<string, Rule>,
): Violation[] {
  const violations: Violation[] = [];
  for (const result of results) {
    for (const message of result.messages) {
      if (!message.ruleId) continue;
      const rule = index.get(message.ruleId);
      if (!rule) continue;
      violations.push({
        ruleId: rule.id,
        file: result.filePath,
        line: message.line,
        column: message.column,
        message: message.message,
      });
    }
  }
  return violations;
}

export const eslintCheck: Check = {
  id: 'eslint',
  async run(files, rules) {
    const eslint = createESLint(rules);
    const index = buildSourceRuleIndex(rules);
    const results = await lintFiles(eslint, files);
    return collectViolations(results, index);
  },
};
