import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { commentCheck } from './comment-check.js';
import type { Rule } from '../types.js';

const RULE: Rule = {
  id: 'comment:non-essential',
  source: 'custom',
  severity: 'suggested',
  changedFilesOnly: false,
  title: 'Comment found',
  description: '',
};

function write(dir: string, name: string, content: string): string {
  const path = join(dir, name);
  writeFileSync(path, content);
  return path;
}

describe('commentCheck', () => {
  let dir: string;

  beforeEach(() => {
    dir = mkdtempSync(join(tmpdir(), 'hh-comments-'));
  });
  afterEach(() => {
    rmSync(dir, { recursive: true, force: true });
  });

  it('flags a long single-line comment', async () => {
    const file = write(dir, 'a.ts', '// This explains add and is too long\nexport const a = 1;\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toHaveLength(1);
    expect(violations[0]?.message).toContain('single-line');
  });

  it('ignores short single-line comments (< 10 chars)', async () => {
    const file = write(dir, 'b.ts', '// hi\nexport const b = 1;\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toEqual([]);
  });

  it('flags a block comment >= 15 chars', async () => {
    const file = write(dir, 'c.ts', '/* a long block comment here */\nexport const c = 1;\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toHaveLength(1);
    expect(violations[0]?.message).toContain('block-line');
  });

  it('flags a JSDoc comment >= 15 chars distinctly', async () => {
    const file = write(dir, 'd.ts', '/** documents the next function */\nexport const d = 1;\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toHaveLength(1);
    expect(violations[0]?.message).toContain('JSDoc-line');
  });

  it('ignores eslint-disable comments (single)', async () => {
    const file = write(dir, 'e.ts', '// eslint-disable-next-line no-console\nconsole.log(1);\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toEqual([]);
  });

  it('ignores eslint-disable comments (block)', async () => {
    const file = write(dir, 'f.ts', '/* eslint-disable no-console */\nconsole.log(1);\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toEqual([]);
  });

  it('ignores configured executable annotations', async () => {
    const file = write(dir, 'g.ts', '// @keep-this comment for tooling\nexport const g = 1;\n');
    const ruleWithOpts: Rule = {
      ...RULE,
      eslintOptions: { executableAnnotations: ['@keep-this'] },
    };
    const violations = await commentCheck.run([file], [ruleWithOpts]);
    expect(violations).toEqual([]);
  });

  it('returns empty when no files supplied', async () => {
    const violations = await commentCheck.run([], [RULE]);
    expect(violations).toEqual([]);
  });

  it('ignores shebang lines (parsed as ShebangTrivia, not SingleLineCommentTrivia)', async () => {
    const file = write(dir, 'shebang.ts', '#!/usr/bin/env node\nexport const x = 12345;\n');
    const violations = await commentCheck.run([file], [RULE]);
    expect(violations).toEqual([]);
  });
});
