import { createRequire } from 'node:module';
import { ESLint, type Linter } from 'eslint';
import tseslint from 'typescript-eslint';
import type { Check, Rule, Violation } from '../types.js';

const TS_PLUGIN_NAME = '@typescript-eslint/eslint-plugin';
const TS_PLUGIN_NAMESPACE = '@typescript-eslint';
const CORE_UNUSED = 'no-unused-vars';
const TS_UNUSED = '@typescript-eslint/no-unused-vars';

interface TsPluginProbe {
  available: boolean;
  plugin: ESLint.Plugin | null;
}

let probeCache: Map<string, Promise<TsPluginProbe>> = new Map();

function resolvePluginPath(cwd: string): string | null {
  try {
    const require = createRequire(`${cwd}/__noop.js`);
    return require.resolve(TS_PLUGIN_NAME);
  } catch {
    return null;
  }
}

async function loadTsPlugin(cwd: string): Promise<TsPluginProbe> {
  const resolved = resolvePluginPath(cwd);
  if (resolved === null) {
    process.stderr.write(
      `habit-hooks: ${TS_PLUGIN_NAME} not found in ${cwd}; falling back to core no-unused-vars and skipping TS-only rules\n`,
    );
    return { available: false, plugin: null };
  }
  const mod = (await import(resolved)) as { default?: ESLint.Plugin } & ESLint.Plugin;
  const plugin = (mod.default ?? mod) as ESLint.Plugin;
  return { available: true, plugin };
}

function probeTsPlugin(cwd: string): Promise<TsPluginProbe> {
  const cached = probeCache.get(cwd);
  if (cached) return cached;
  const promise = loadTsPlugin(cwd);
  probeCache.set(cwd, promise);
  return promise;
}

function isTsNamespacedRule(sourceRuleId: string): boolean {
  return sourceRuleId.startsWith(`${TS_PLUGIN_NAMESPACE}/`);
}

function adaptRulesForProbe(rules: Rule[], probe: TsPluginProbe): Rule[] {
  return rules.flatMap((rule) => {
    if (rule.source !== 'eslint' || !rule.sourceRuleId) return [rule];
    if (probe.available && rule.sourceRuleId === CORE_UNUSED) {
      return [{ ...rule, sourceRuleId: TS_UNUSED }];
    }
    if (!probe.available && isTsNamespacedRule(rule.sourceRuleId)) return [];
    return [rule];
  });
}

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

function pluginsBlock(probe: TsPluginProbe): Record<string, ESLint.Plugin> {
  if (!probe.available || probe.plugin === null) return {};
  return { [TS_PLUGIN_NAMESPACE]: probe.plugin };
}

function buildOverrideConfig(rules: Rule[], probe: TsPluginProbe): Linter.Config[] {
  const plugins = pluginsBlock(probe);
  return [
    {
      files: ['**/*.ts', '**/*.tsx'],
      languageOptions: { parser: tseslint.parser },
      plugins,
    },
    { plugins, rules: buildRuleConfig(rules) },
  ];
}

function createESLint(rules: Rule[], cwd: string | undefined, probe: TsPluginProbe): ESLint {
  return new ESLint({
    cwd,
    overrideConfigFile: true,
    overrideConfig: buildOverrideConfig(rules, probe),
  });
}

async function lintFiles(eslint: ESLint, files: string[]): Promise<ESLint.LintResult[]> {
  if (files.length === 0) return [];
  return eslint.lintFiles(files);
}

function toViolation(rule: Rule, filePath: string, message: Linter.LintMessage): Violation {
  return {
    ruleId: rule.id,
    file: filePath,
    line: message.line,
    column: message.column,
    message: message.message,
  };
}

function tryMapMessage(
  message: Linter.LintMessage,
  filePath: string,
  index: Map<string, Rule>,
): Violation | null {
  if (!message.ruleId) return null;
  const rule = index.get(message.ruleId);
  if (!rule) return null;
  return toViolation(rule, filePath, message);
}

function collectViolations(
  results: ESLint.LintResult[],
  index: Map<string, Rule>,
): Violation[] {
  return results.flatMap((result) =>
    result.messages
      .map((m) => tryMapMessage(m, result.filePath, index))
      .filter((v): v is Violation => v !== null),
  );
}

export function resetTsProbeCache(): void {
  probeCache = new Map();
}

export const eslintCheck: Check = {
  id: 'eslint',
  async run(files, rules, cwd) {
    const probeCwd = cwd ?? process.cwd();
    const probe = await probeTsPlugin(probeCwd);
    const adaptedRules = adaptRulesForProbe(rules, probe);
    const eslint = createESLint(adaptedRules, cwd, probe);
    const index = buildSourceRuleIndex(adaptedRules);
    const results = await lintFiles(eslint, files);
    return collectViolations(results, index);
  },
};
