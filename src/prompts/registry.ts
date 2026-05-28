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
    id: 'eslint:boundaries/dependencies',
    title: 'Architectural layering violated',
    description: 'An upper layer reached into a lower one; restore the boundary at the seam.',
  },
  {
    id: 'knip:files',
    title: 'Unused file',
    description: 'A file no consumer imports — either an entry point knip cannot see, or orphan code.',
  },
  {
    id: 'knip:exports',
    title: 'Unused export',
    description: 'An export no consumer references — either internal-by-accident or undeclared public surface.',
  },
  {
    id: 'knip:types',
    title: 'Unused type export',
    description: 'A type export no consumer references — either internal-by-accident or undeclared public surface.',
  },
  {
    id: 'knip:dependencies',
    title: 'Unused dependency',
    description: 'A package.json dependency with no detected import — uninstall, or teach knip about the config that loads it.',
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
