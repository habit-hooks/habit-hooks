import { afterEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run } from '../runner.js';
import { RULES_DEPRECATION } from './load.js';

describe('rules alias deprecation', () => {
  let dir: string;

  afterEach(() => {
    if (dir) rmSync(dir, { recursive: true, force: true });
  });

  function writeConfig(value: unknown): void {
    dir = mkdtempSync(join(tmpdir(), 'hh-deprecation-'));
    writeFileSync(join(dir, 'habit-hooks.config.json'), JSON.stringify(value));
  }

  it('warns on stderr when a config uses the deprecated rules field', async () => {
    writeConfig({ rules: { 'oversized-function': { disabled: true } } });
    const result = await run(dir);
    expect(result.stderr).toContain(RULES_DEPRECATION);
  });

  it('does not warn when a config uses smells', async () => {
    writeConfig({ smells: { 'oversized-function': { disabled: true } } });
    const result = await run(dir);
    expect(result.stderr).not.toContain(RULES_DEPRECATION);
  });
});
