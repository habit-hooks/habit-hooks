import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SKILL_NAME = 'habit-hooks-review';
const SKILL_FILE = 'SKILL.md';

export type SkillAction = 'installed' | 'conflict' | 'source-missing' | 'kept';

export interface SkillResult {
  action: SkillAction;
  source?: string;
  target?: string;
}

function packageRoot(): string {
  const here = dirname(fileURLToPath(import.meta.url));
  return resolve(here, '..', '..', '..');
}

function findSkillSource(): string | null {
  const root = packageRoot();
  const candidates = [
    join(root, 'src', 'skills', SKILL_NAME, SKILL_FILE),
    join(root, '..', 'src', 'skills', SKILL_NAME, SKILL_FILE),
  ];
  return candidates.find((p) => existsSync(p)) ?? null;
}

function targetDir(): string {
  return join(homedir(), '.claude', 'skills', SKILL_NAME);
}

function targetPath(): string {
  return join(targetDir(), SKILL_FILE);
}

export function installReviewerSkill(): SkillResult {
  const source = findSkillSource();
  if (source === null) return { action: 'source-missing' };
  const target = targetPath();
  if (existsSync(target)) return { action: 'conflict', source, target };
  mkdirSync(targetDir(), { recursive: true });
  copyFileSync(source, target);
  return { action: 'installed', source, target };
}
