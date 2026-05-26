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

function buildRegistry(): Map<string, CoachingPrompt> {
  const packagedDir = resolvePackagedDir();
  const map = new Map<string, CoachingPrompt>();
  for (const rule of defaultRules) {
    map.set(rule.id, buildPrompt(rule, packagedDir));
  }
  return map;
}

const registry = buildRegistry();

export function lookupPrompt(ruleId: string): CoachingPrompt | null {
  return registry.get(ruleId) ?? null;
}

export function listPrompts(): CoachingPrompt[] {
  return [...registry.values()];
}
