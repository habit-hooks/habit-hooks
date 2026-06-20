import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { existsSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';

const repoRoot = join(dirname(fileURLToPath(import.meta.url)), '..');
const mapperPath = join(repoRoot, 'dist', 'mapper-cli.js');

const SAMPLE_GUIDES = `export default {
  "issue56": (details) => {
    return prompt("Fix issue56");
  },
};
`;

const SAMPLE_SENSOR = JSON.stringify({ issues: [{ smell: 'issue56' }] });

function pipeThroughMapper(workDir: string, sensorJson: string) {
  writeFileSync(join(workDir, 'sample_sensor.json'), sensorJson);
  return spawnSync('bash', ['-c', `cat sample_sensor.json | node "${mapperPath}" --guides ./sample_guides.ts`], {
    cwd: workDir,
    encoding: 'utf8',
  });
}

describe('mapper cli', () => {
  let workDir: string;

  beforeAll(() => {
    if (!existsSync(mapperPath)) {
      const build = spawnSync('npm', ['run', 'build'], { cwd: repoRoot, encoding: 'utf8' });
      if (build.status !== 0) throw new Error(`build failed: ${build.stderr}`);
    }
  }, 60_000);

  beforeEach(() => {
    workDir = mkdtempSync(join(tmpdir(), 'mapper-cli-'));
    writeFileSync(join(workDir, 'sample_guides.ts'), SAMPLE_GUIDES);
    writeFileSync(join(workDir, 'sample_sensor.json'), SAMPLE_SENSOR);
  });

  afterEach(() => {
    rmSync(workDir, { recursive: true, force: true });
  });

  it('coaches the issue and exits 1 (not everything fixed)', () => {
    const result = pipeThroughMapper(workDir, SAMPLE_SENSOR);
    expect(result.stdout.trim()).toBe('❌ Fix issue56');
    expect(result.status).toBe(1);
  });

  it('exits 0 with no output when there are no issues', () => {
    const result = pipeThroughMapper(workDir, JSON.stringify({ issues: [] }));
    expect(result.stdout).toBe('');
    expect(result.status).toBe(0);
  });

  it('errors and exits 2 when --guides is missing', () => {
    const result = spawnSync('node', [mapperPath], { cwd: workDir, input: SAMPLE_SENSOR, encoding: 'utf8' });
    expect(result.status).toBe(2);
    expect(result.stderr).toMatch(/--guides/);
  });
});
