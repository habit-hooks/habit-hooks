import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SKILL_NAMES = ['habit-hooks-review', 'habit-hooks-prompting'] as const;
const SKILL_FILE = 'SKILL.md';

export type SkillAction = 'installed' | 'conflict' | 'source-missing' | 'kept';

export interface SkillResult {
  name: string;
  action: SkillAction;
  source?: string;
  target?: string;
}

function packageRoot(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, '..', '..', '..');
}

function findSkillSource(name: string): string | null {
  const root = packageRoot();
  const candidates = [
    join(root, 'src', 'skills', name, SKILL_FILE),
    join(root, '..', 'src', 'skills', name, SKILL_FILE),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

function targetDir(name: string): string {
  return join(homedir(), '.claude', 'skills', name);
}

function targetPath(name: string): string {
  return join(targetDir(name), SKILL_FILE);
}

function installSkill(name: string): SkillResult {
  const source = findSkillSource(name);
  if (source === null) return { name, action: 'source-missing' };
  const target = targetPath(name);
  if (existsSync(target)) return { name, action: 'conflict', source, target };
  mkdirSync(targetDir(name), { recursive: true });
  copyFileSync(source, target);
  return { name, action: 'installed', source, target };
}

export function installSkills(): SkillResult[] {
  return SKILL_NAMES.map((name) => installSkill(name));
}
