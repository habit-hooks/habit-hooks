import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  detectTool,
  TOOL_CONFIG_FILENAMES,
  TOOL_PACKAGE_JSON_KEYS,
  type ToolName,
} from '../../detect/tool.js';

export type { ToolName };

export interface ToolState {
  installed: boolean;
  configured: boolean;
}

export type ToolStateMatrix = Record<ToolName, ToolState>;

const TOOLS: ToolName[] = ['eslint', 'knip', 'jscpd'];

function hasPackageJsonKey(cwd: string, key: string): boolean {
  const path = join(cwd, 'package.json');
  if (!existsSync(path)) return false;
  try {
    const pkg = JSON.parse(readFileSync(path, 'utf8')) as Record<string, unknown>;
    return pkg[key] !== undefined;
  } catch {
    return false;
  }
}

function hasConfigFile(cwd: string, tool: ToolName): boolean {
  if (TOOL_CONFIG_FILENAMES[tool].some((name) => existsSync(join(cwd, name)))) return true;
  return hasPackageJsonKey(cwd, TOOL_PACKAGE_JSON_KEYS[tool]);
}

function stateFor(cwd: string, tool: ToolName): ToolState {
  return { installed: detectTool(cwd, tool) !== null, configured: hasConfigFile(cwd, tool) };
}

export function detectToolStates(cwd: string): ToolStateMatrix {
  const matrix: Partial<ToolStateMatrix> = {};
  for (const tool of TOOLS) matrix[tool] = stateFor(cwd, tool);
  return matrix as ToolStateMatrix;
}
