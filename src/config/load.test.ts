import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { loadConfig } from './load.js';

let workDir: string;

beforeEach(() => {
  workDir = mkdtempSync(join(tmpdir(), 'hh-cfg-'));
});

afterEach(() => {
  rmSync(workDir, { recursive: true, force: true });
});

describe('loadConfig', () => {
  it('returns empty config and null sourcePath when no file present', async () => {
    const loaded = await loadConfig(workDir);
    expect(loaded.config).toEqual({});
    expect(loaded.sourcePath).toBeNull();
  });

  it('loads a .json config', async () => {
    const cfg = { prompts: './prompts', rules: { 'too-many-parameters': { severity: 'suggested' } } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(cfg));
    const loaded = await loadConfig(workDir);
    expect(loaded.config.prompts).toBe('./prompts');
    expect(loaded.config.rules?.['too-many-parameters']).toEqual({ severity: 'suggested' });
    expect(loaded.sourcePath).toContain('habit-hooks.config.json');
  });

  it('loads a .mjs config', async () => {
    const content = `export default { rules: { 'high-complexity': { severity: 'enforced' } } };\n`;
    writeFileSync(join(workDir, 'habit-hooks.config.mjs'), content);
    const loaded = await loadConfig(workDir);
    expect(loaded.config.rules?.['high-complexity']).toEqual({ severity: 'enforced' });
  });

  it('loads a .js config (ESM)', async () => {
    const content = `export default { rules: { 'high-complexity': { severity: 'suggested' } } };\n`;
    writeFileSync(join(workDir, 'habit-hooks.config.js'), content);
    const loaded = await loadConfig(workDir);
    expect(loaded.config.rules?.['high-complexity']).toEqual({ severity: 'suggested' });
  });

  it('loads a .ts config via jiti', async () => {
    const content = `const config = { rules: { 'too-many-parameters': { severity: 'suggested' as const } } };\nexport default config;\n`;
    writeFileSync(join(workDir, 'habit-hooks.config.ts'), content);
    const loaded = await loadConfig(workDir);
    expect(loaded.config.rules?.['too-many-parameters']).toEqual({ severity: 'suggested' });
  });

  it('prefers .ts over other formats when multiple exist', async () => {
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify({ prompts: 'json' }));
    writeFileSync(
      join(workDir, 'habit-hooks.config.ts'),
      `export default { prompts: 'ts' };\n`,
    );
    const loaded = await loadConfig(workDir);
    expect(loaded.config.prompts).toBe('ts');
    expect(loaded.sourcePath).toContain('.ts');
  });

  it('throws naming the field path on bad severity', async () => {
    const bad = { rules: { 'too-many-parameters': { severity: 'wrong' } } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /rules\.too-many-parameters\.severity must be 'enforced' or 'suggested'/,
    );
  });

  it('throws naming the field path on bad include type', async () => {
    const bad = { rules: { 'too-many-parameters': { include: 'src/**' } } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /rules\.too-many-parameters\.include must be an array of strings/,
    );
  });

  it('validates and round-trips the smells field', async () => {
    const cfg = { smells: { 'too-many-parameters': { severity: 'suggested', fix: 'shared/style.md' } } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(cfg));
    const loaded = await loadConfig(workDir);
    expect(loaded.config.smells?.['too-many-parameters']).toEqual({ severity: 'suggested', fix: 'shared/style.md' });
  });

  it('throws naming the smells field path on a bad severity', async () => {
    const bad = { smells: { 'too-many-parameters': { severity: 'wrong' } } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /smells\.too-many-parameters\.severity must be 'enforced' or 'suggested'/,
    );
  });

  it('throws when rules is not an object', async () => {
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify({ rules: [] }));
    await expect(loadConfig(workDir)).rejects.toThrow(/rules must be an object/);
  });

  it('throws when commentCheck is not an object', async () => {
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify({ commentCheck: 'nope' }));
    await expect(loadConfig(workDir)).rejects.toThrow(/commentCheck must be an object/);
  });

  it('throws when commentCheck.maxSingleLineChars is zero', async () => {
    const bad = { commentCheck: { maxSingleLineChars: 0 } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /commentCheck\.maxSingleLineChars must be a positive integer/,
    );
  });

  it('throws when commentCheck.maxSingleLineChars is negative', async () => {
    const bad = { commentCheck: { maxSingleLineChars: -3 } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /commentCheck\.maxSingleLineChars must be a positive integer/,
    );
  });

  it('throws when commentCheck.maxBlockChars is a float', async () => {
    const bad = { commentCheck: { maxBlockChars: 1.5 } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /commentCheck\.maxBlockChars must be a positive integer/,
    );
  });

  it('throws when commentCheck.maxBlockChars is not a number', async () => {
    const bad = { commentCheck: { maxBlockChars: 'twenty' } };
    writeFileSync(join(workDir, 'habit-hooks.config.json'), JSON.stringify(bad));
    await expect(loadConfig(workDir)).rejects.toThrow(
      /commentCheck\.maxBlockChars must be a positive integer/,
    );
  });
});
