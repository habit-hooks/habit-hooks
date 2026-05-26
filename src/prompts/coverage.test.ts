import { describe, expect, it } from 'vitest';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { defaultRules } from '../config/defaults.js';
import { loadGuidance } from './loader.js';

const here = dirname(fileURLToPath(import.meta.url));

function slugify(ruleId: string): string {
  return ruleId.replace(/[:/]/g, '-').replace(/@/g, '');
}

function expectedSlugs(): Set<string> {
  return new Set(defaultRules.map((r) => slugify(r.id)));
}

function actualSlugs(): Set<string> {
  return new Set(
    readdirSync(here)
      .filter((f) => f.endsWith('.md'))
      .filter((f) => f !== 'REVIEW.md')
      .map((f) => f.slice(0, -'.md'.length)),
  );
}

describe('prompts coverage', () => {
  it('every default rule has a corresponding markdown file', () => {
    for (const rule of defaultRules) {
      expect(() => loadGuidance(rule.id), `missing prompt for ${rule.id}`).not.toThrow();
    }
  });

  it('no orphan markdown files exist (every md maps to a rule)', () => {
    const expected = expectedSlugs();
    const actual = actualSlugs();
    const orphans = [...actual].filter((slug) => !expected.has(slug));
    expect(orphans).toEqual([]);
  });

  it('REVIEW.md exists for reviewers', () => {
    const files = readdirSync(here);
    expect(files).toContain('REVIEW.md');
  });

  it('prompts directory path is correct', () => {
    expect(here.endsWith(join('src', 'prompts'))).toBe(true);
  });
});
