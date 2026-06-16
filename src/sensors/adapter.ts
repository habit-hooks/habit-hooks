import { runTool } from '../wrap/shell.js';
import { isSpawnFailure, recordSpawnFailure, spawnFailureWarning, type SensorSink } from '../wrap/notices.js';
import type { Issue, Sensor, SensorContext } from './types.js';

// The declarative adapter (docs/sensors.md): when a tool already emits JSON, a
// sensor can declare how to read it instead of shipping a wrapper script. Up to
// two levels of array nesting are supported — a flat list (ruff) or an outer
// `group` of entries each holding an inner `items` array (eslint).

export interface AdapterSpec {
  id: string; // sensor id; also the provenance prefix written to details.source
  command: string; // shell command; `${files}` expands to the scoped file list
  group?: string; // outer array path (e.g. "[]"); omit for a flat list
  items: string; // inner array path (e.g. "[]" or "messages[]")
  fields: Record<string, string>; // bag field <- dot-path ("group." reads the outer entry)
  map?: Record<string, string>; // raw smell value -> canonical smell key
}

type Json = unknown;

function getByPath(value: Json, path: string): Json {
  if (path === '') return value;
  return path.split('.').reduce<Json>((acc, key) => {
    if (acc !== null && typeof acc === 'object') return (acc as Record<string, Json>)[key];
    return undefined;
  }, value);
}

// A path ending in "[]" denotes an array; "[]" alone is the value itself.
function resolveArray(value: Json, path: string): Json[] {
  const base = path.endsWith('[]') ? path.slice(0, -2) : path;
  const resolved = getByPath(value, base);
  return Array.isArray(resolved) ? resolved : [];
}

function readField(issue: Json, group: Json, path: string): Json {
  if (path.startsWith('group.')) return getByPath(group, path.slice('group.'.length));
  return getByPath(issue, path);
}

function buildDetails(spec: AdapterSpec, issue: Json, group: Json): { rawSmell: string; details: Record<string, unknown> } {
  const details: Record<string, unknown> = {};
  let rawSmell = '';
  for (const [field, path] of Object.entries(spec.fields)) {
    const value = readField(issue, group, path);
    if (field === 'smell') rawSmell = String(value);
    else if (value !== undefined) details[field] = value;
  }
  return { rawSmell, details };
}

function extractOne(spec: AdapterSpec, issue: Json, group: Json): Issue {
  const { rawSmell, details } = buildDetails(spec, issue, group);
  details.source = `${spec.id}:${rawSmell}`;
  return { smell: spec.map?.[rawSmell] ?? rawSmell, details };
}

export function extractIssues(root: Json, spec: AdapterSpec): Issue[] {
  if (spec.group !== undefined) {
    return resolveArray(root, spec.group).flatMap((group) =>
      resolveArray(group, spec.items).map((issue) => extractOne(spec, issue, group)),
    );
  }
  return resolveArray(root, spec.items).map((issue) => extractOne(spec, issue, null));
}

export interface DeclarativeSensorSpec extends AdapterSpec {
  produces: string[];
}

// Split the command on whitespace and expand the `${files}` token into the
// scoped file list (the preset commands are unquoted, so a simple split suffices).
function buildArgv(command: string, files: string[]): { bin: string; args: string[] } {
  const tokens = command.split(/\s+/).filter((token) => token.length > 0);
  const expanded = tokens.flatMap((token) => (token === '${files}' ? files : [token]));
  return { bin: expanded[0] ?? '', args: expanded.slice(1) };
}

function parseJson(stdout: string): Json {
  const trimmed = stdout.trim();
  if (trimmed.length === 0) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

async function runDeclarative(spec: DeclarativeSensorSpec, ctx: SensorContext, sink: SensorSink): Promise<Issue[]> {
  if (ctx.files.length === 0) return [];
  const { bin, args } = buildArgv(spec.command, ctx.files);
  const result = await runTool({ bin, args, cwd: ctx.cwd });
  if (isSpawnFailure(result)) {
    recordSpawnFailure(sink, spawnFailureWarning(spec.id, ctx.cwd, result.warnings));
    return [];
  }
  return extractIssues(parseJson(result.stdout), spec);
}

// Wrap a JSON-emitting tool as a leaf sensor via the declarative spec. A spawn
// or timeout failure fails the run (docs/sensors.md): the message is shown and
// recorded as a failure, with zero issues for that tool.
export function declarativeSensor(spec: DeclarativeSensorSpec, sink: SensorSink): Sensor {
  return { id: spec.id, produces: spec.produces, run: (ctx) => runDeclarative(spec, ctx, sink) };
}
