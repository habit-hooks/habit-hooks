import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { installSkills } from './skill.js';
import { reportSkillResults, type Lines } from './reporters.js';

interface Setup {
  home: string;
  originalHome: string | undefined;
}

function makeLines(): Lines {
  return { out: [], err: [], exit: 0 };
}

describe('installSkills', () => {
  let s: Setup;

  beforeEach(() => {
    const home = mkdtempSync(join(tmpdir(), 'hh-skills-'));
    s = { home, originalHome: process.env.HOME };
    process.env.HOME = home;
  });
  afterEach(() => {
    if (s.originalHome === undefined) delete process.env.HOME;
    else process.env.HOME = s.originalHome;
    rmSync(s.home, { recursive: true, force: true });
  });

  it('installs both bundled skills into ~/.claude/skills', () => {
    const results = installSkills();
    expect(results.map((r) => r.name)).toEqual(['habit-hooks-review', 'habit-hooks-prompting']);
    for (const result of results) {
      expect(result.action).toBe('installed');
      expect(existsSync(result.target as string)).toBe(true);
    }
    const reviewer = join(s.home, '.claude', 'skills', 'habit-hooks-review', 'SKILL.md');
    const prompting = join(s.home, '.claude', 'skills', 'habit-hooks-prompting', 'SKILL.md');
    expect(readFileSync(reviewer, 'utf8')).toContain('name: habit-hooks-review');
    expect(readFileSync(prompting, 'utf8')).toContain('name: habit-hooks-prompting');
  });

  it('leaves an existing skill untouched and reports the conflict per skill', () => {
    const promptingDir = join(s.home, '.claude', 'skills', 'habit-hooks-prompting');
    const promptingFile = join(promptingDir, 'SKILL.md');
    const reviewerDir = join(s.home, '.claude', 'skills', 'habit-hooks-review');
    mkdirSync(reviewerDir, { recursive: true });
    writeFileSync(join(reviewerDir, 'SKILL.md'), 'mine\n');
    expect(existsSync(promptingDir)).toBe(false);

    const lines = makeLines();
    reportSkillResults(installSkills(), lines);
    const out = lines.out.join('');
    expect(out).toContain('habit-hooks-review already exists');
    expect(out).toContain('installed habit-hooks-prompting at');
    expect(readFileSync(promptingFile, 'utf8')).toContain('name: habit-hooks-prompting');
  });
});
