import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { HabitHooksConfig } from './schema.js';
import { validateConfig } from './validate.js';
import { loadTsModule } from './jiti-loader.js';

const CONFIG_FILENAMES = [
  'habit-hooks.config.ts',
  'habit-hooks.config.mjs',
  'habit-hooks.config.js',
  'habit-hooks.config.json',
];

interface LoadedConfig {
  config: HabitHooksConfig;
  sourcePath: string | null;
}

function findConfigFile(cwd: string): string | null {
  for (const name of CONFIG_FILENAMES) {
    const candidate = join(cwd, name);
    if (existsSync(candidate)) return candidate;
  }
  return null;
}

function unwrapDefault(mod: unknown): unknown {
  if (mod && typeof mod === 'object' && 'default' in mod) {
    return (mod as { default: unknown }).default;
  }
  return mod;
}

async function readConfigFile(path: string): Promise<unknown> {
  if (path.endsWith('.json')) {
    return JSON.parse(readFileSync(path, 'utf8'));
  }
  if (path.endsWith('.ts')) {
    return loadTsModule(path);
  }
  const mod = (await import(pathToFileURL(path).href)) as unknown;
  return unwrapDefault(mod);
}

export async function loadConfig(cwd: string): Promise<LoadedConfig> {
  const sourcePath = findConfigFile(cwd);
  if (sourcePath === null) {
    return { config: {}, sourcePath: null };
  }
  const raw = await readConfigFile(sourcePath);
  const config = validateConfig(raw);
  return { config, sourcePath };
}

export async function loadConfigFromPath(path: string): Promise<LoadedConfig> {
  if (!existsSync(path)) {
    throw new Error(`Config file not found: ${path}`);
  }
  const raw = await readConfigFile(path);
  const config = validateConfig(raw);
  return { config, sourcePath: path };
}
