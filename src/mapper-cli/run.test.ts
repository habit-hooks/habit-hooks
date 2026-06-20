import { describe, expect, it } from 'vitest';
import { runMapper, type Guides } from './run.js';

const guides: Guides = {
  issue56: () => 'Fix issue56',
};

describe('runMapper', () => {
  it('coaches each issue with its guide and exits 1', () => {
    const json = JSON.stringify({ issues: [{ smell: 'issue56' }] });
    const result = runMapper(json, guides);
    expect(result.stdout).toBe('❌ Fix issue56\n');
    expect(result.exitCode).toBe(1);
  });

  it('passes the whole issue to the guide as details', () => {
    const seen: unknown[] = [];
    const capture: Guides = {
      issue56: (issue) => {
        seen.push(issue);
        return 'ok';
      },
    };
    const json = JSON.stringify({ issues: [{ smell: 'issue56', details: { file: 'a.ts' } }] });
    runMapper(json, capture);
    expect(seen).toEqual([{ smell: 'issue56', details: { file: 'a.ts' } }]);
  });

  it('exits 0 with no output when there are no issues', () => {
    const result = runMapper(JSON.stringify({ issues: [] }), guides);
    expect(result.stdout).toBe('');
    expect(result.exitCode).toBe(0);
  });

  it('exits 0 when a guide returns nothing (issue already fixed)', () => {
    const fixed: Guides = { issue56: () => undefined };
    const json = JSON.stringify({ issues: [{ smell: 'issue56' }] });
    const result = runMapper(json, fixed);
    expect(result.stdout).toBe('');
    expect(result.exitCode).toBe(0);
  });

  it('warns and exits 1 when a smell has no guide', () => {
    const json = JSON.stringify({ issues: [{ smell: 'unknown' }] });
    const result = runMapper(json, guides);
    expect(result.stdout).toBe('⚠️ No guide for smell: unknown\n');
    expect(result.exitCode).toBe(1);
  });
});
