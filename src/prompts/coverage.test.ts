import { describe, expect, it } from 'vitest';
import { readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { defaultRules } from '../config/defaults.js';
import { loadGuidance } from './loader.js';
import { listPrompts } from './registry.js';

const here = dirname(fileURLToPath(import.meta.url));

function slugify(ruleId: string): string {
  return ruleId.replace(/[:/]/g, '-').replace(/@/g, '');
}

const UNCOACHED_SLUG = 'uncoached';

function registeredSlugs(): Set<string> {
  return new Set(listPrompts().map((p) => slugify(p.id)));
}

function expectedSlugs(): Set<string> {
  const slugs = registeredSlugs();
  slugs.add(UNCOACHED_SLUG);
  return slugs;
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
  it('every default rule either has a tuned markdown file or falls back to uncoached', () => {
    expect(loadGuidance(UNCOACHED_SLUG), 'uncoached fallback missing').not.toBeNull();
    for (const rule of defaultRules) {
      const guidance = loadGuidance(rule.id) ?? loadGuidance(UNCOACHED_SLUG);
      expect(guidance, `no guidance resolvable for ${rule.id}`).not.toBeNull();
    }
  });

  it('every registered prompt resolves guidance (tuned file or uncoached fallback)', () => {
    for (const prompt of listPrompts()) {
      const guidance = loadGuidance(prompt.id) ?? loadGuidance(UNCOACHED_SLUG);
      expect(guidance, `no guidance resolvable for ${prompt.id}`).not.toBeNull();
    }
  });

  it('no orphan markdown files exist (every md maps to a registered prompt or the uncoached header)', () => {
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
