import type { RuleSource, Severity } from '../types.js';

export interface RuleOverride {
  severity?: Severity;
  changedFilesOnly?: boolean;
  title?: string;
  description?: string;
  disabled?: boolean;
  include?: string[];
  exclude?: string[];
  fix?: string;
}

export interface RuleDefinition extends RuleOverride {
  id: string;
  source: RuleSource;
  sourceRuleId?: string;
}

export interface ScopeConfig {
  onlyChangedFiles?: boolean;
  autoBranchOffMain?: boolean;
  branchBase?: string;
  mainBranch?: string;
  exclude?: string[];
}

export interface CommentCheckConfig {
  maxSingleLineChars?: number;
  maxBlockChars?: number;
}

// When `replace` is true, a `needs-extraction` finding suppresses its two input
// smells (oversized-file, duplicated-code) for that file. Default (augment)
// shows all three.
export interface NeedsExtractionConfig {
  replace?: boolean;
}

export type Language = 'typescript' | 'python';

// A user-declared sensor (issue #16), discriminated by which key it sets:
// `use` -> code-backed (a registered built-in factory; produces/dependsOn come
// from the factory). Otherwise `command` is required; the presence of any
// adapter key (items/fields/group/map) makes it declarative, else it is a
// wrapper script that prints bag JSON itself. The three modes are mutually
// exclusive — validation rejects mixing `use` with command-mode keys.
export interface UseSensorSpec {
  use: string;
}

export interface WrapperSensorSpec {
  command: string;
  produces: string[];
  dependsOn?: string[];
}

export interface DeclarativeSpec {
  command: string;
  produces: string[];
  items: string;
  fields: Record<string, string>;
  group?: string;
  map?: Record<string, string>;
  dependsOn?: string[];
}

export type SensorSpec = UseSensorSpec | WrapperSensorSpec | DeclarativeSpec;

export interface HabitHooksConfig {
  prompts?: string;
  // Open string at runtime: built-ins (typescript/python) get a default preset +
  // default file globs; any other value relies on `files` + `sensors`. Default: typescript.
  language?: string;
  // `smells` is the canonical smell-keyed mapping (docs/mapper.md); `rules` is a
  // transitional alias accepted for back-compat. Both merge, smells last.
  smells?: Record<string, RuleOverride | RuleDefinition>;
  rules?: Record<string, RuleOverride | RuleDefinition>;
  scope?: ScopeConfig;
  commentCheck?: CommentCheckConfig;
  needsExtraction?: NeedsExtractionConfig;
  // User-declared sensors keyed by sensor id; `files` overrides discovery globs.
  sensors?: Record<string, SensorSpec>;
  files?: string[];
}

export function isRuleDefinition(
  entry: RuleOverride | RuleDefinition,
): entry is RuleDefinition {
  return 'source' in entry && typeof (entry as RuleDefinition).source === 'string';
}
