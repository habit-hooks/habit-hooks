import { join } from 'node:path';
import type { CoachingPrompt, Severity } from '../types.js';
import { defaultRules } from '../config/defaults.js';
import { resolvePackagedDir } from './packaged-dir.js';

interface RuleSeed {
  id: string;
  title: string;
  description: string;
  severity?: Severity;
}

const supplementalSeeds: RuleSeed[] = [
  {
    id: 'eslint:fatal',
    title: 'ESLint fatal parse/config error',
    description: 'ESLint could not analyze the file — a parse error, unresolvable config, or a plugin threw.',
    severity: 'enforced',
  },
];

function slugify(ruleId: string): string {
  return ruleId.replace(/[:/]/g, '-').replace(/@/g, '');
}

function buildPrompt(seed: RuleSeed, packagedDir: string): CoachingPrompt {
  return {
    id: seed.id,
    title: seed.title,
    description: seed.description,
    severity: seed.severity ?? 'suggested',
    guidancePath: join(packagedDir, `${slugify(seed.id)}.md`),
  };
}

function addSeedToMap(map: Map<string, CoachingPrompt>, seed: RuleSeed, packagedDir: string): void {
  map.set(seed.id, buildPrompt(seed, packagedDir));
}

function buildRegistry(): Map<string, CoachingPrompt> {
  const packagedDir = resolvePackagedDir();
  const map = new Map<string, CoachingPrompt>();
  for (const rule of defaultRules) addSeedToMap(map, rule, packagedDir);
  for (const seed of supplementalSeeds) addSeedToMap(map, seed, packagedDir);
  return map;
}

const registry = buildRegistry();

export function lookupPrompt(ruleId: string): CoachingPrompt | null {
  return registry.get(ruleId) ?? null;
}

export function listPrompts(): CoachingPrompt[] {
  return [...registry.values()];
}
