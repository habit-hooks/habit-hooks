import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  detectTool,
  TOOL_CONFIG_FILENAMES,
  TOOL_PACKAGE_JSON_KEYS,
  type ToolName,
} from '../../detect/tool.js';
import { hasPackageJsonKey } from '../../detect/package-json.js';
import { isOnPath } from '../../detect/path.js';
import type { Language } from '../../config/schema.js';

export type { ToolName };

const TOOLS_BY_LANGUAGE: Record<Language, ToolName[]> = {
  typescript: ['eslint', 'knip', 'jscpd'],
  python: ['ruff', 'deptry', 'jscpd'],
};

export function toolsForLanguage(language: Language): ToolName[] {
  return TOOLS_BY_LANGUAGE[language];
}

export interface ToolState {
  installed: boolean;
  configured: boolean;
}

type ToolStateMatrix = Record<ToolName, ToolState>;

type DetectionKind = 'node' | 'path';

const DETECTION_KIND: Record<ToolName, DetectionKind> = {
  eslint: 'node',
  knip: 'node',
  jscpd: 'node',
  ruff: 'path',
  deptry: 'path',
};

const PATH_BIN_NAME: Partial<Record<ToolName, string>> = {
  ruff: 'ruff',
  deptry: 'deptry',
};

function isInstalled(cwd: string, tool: ToolName): boolean {
  if (DETECTION_KIND[tool] === 'path') return isOnPath(PATH_BIN_NAME[tool] ?? tool);
  return detectTool(cwd, tool) !== null;
}

function hasNodeConfig(cwd: string, tool: ToolName): boolean {
  if (TOOL_CONFIG_FILENAMES[tool].some((name) => existsSync(join(cwd, name)))) return true;
  const key = TOOL_PACKAGE_JSON_KEYS[tool];
  return key !== undefined && hasPackageJsonKey(cwd, key);
}

function readPyproject(cwd: string): string | null {
  const path = join(cwd, 'pyproject.toml');
  if (!existsSync(path)) return null;
  try {
    return readFileSync(path, 'utf8');
  } catch {
    return null;
  }
}

function hasRuffConfig(cwd: string): boolean {
  if (TOOL_CONFIG_FILENAMES.ruff.some((name) => existsSync(join(cwd, name)))) return true;
  const pyproject = readPyproject(cwd);
  return pyproject !== null && /^\[tool\.ruff/m.test(pyproject);
}

function isConfigured(cwd: string, tool: ToolName): boolean {
  if (tool === 'ruff') return hasRuffConfig(cwd);
  if (tool === 'deptry') return readPyproject(cwd) !== null;
  return hasNodeConfig(cwd, tool);
}

function stateFor(cwd: string, tool: ToolName): ToolState {
  return { installed: isInstalled(cwd, tool), configured: isConfigured(cwd, tool) };
}

export function detectToolStates(cwd: string): ToolStateMatrix {
  const tools = Object.keys(DETECTION_KIND) as ToolName[];
  const matrix: Partial<ToolStateMatrix> = {};
  for (const tool of tools) matrix[tool] = stateFor(cwd, tool);
  return matrix as ToolStateMatrix;
}
