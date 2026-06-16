import { JSCPD_SMELL } from '../config/tool-smells.js';
import type { Issue, Sensor } from './types.js';

const SMELL = 'needs-extraction';
const INPUT_SMELLS = ['oversized-file', JSCPD_SMELL] as const;

function fileOf(issue: Issue): string | null {
  const file = issue.details.file;
  return typeof file === 'string' ? file : null;
}

function filesWith(issues: Issue[], smell: string): Set<string> {
  const files = new Set<string>();
  for (const issue of issues) {
    if (issue.smell !== smell) continue;
    const file = fileOf(issue);
    if (file !== null) files.add(file);
  }
  return files;
}

function needsExtractionIssue(file: string): Issue {
  return {
    smell: SMELL,
    details: {
      file,
      line: 1,
      column: 1,
      message: 'File is both oversized and duplicated; extract the duplicated block into a shared module.',
      source: 'composite:oversized-file+duplicated-code',
    },
  };
}

function combine(deps: Issue[]): Issue[] {
  const duplicated = filesWith(deps, JSCPD_SMELL);
  return [...filesWith(deps, 'oversized-file')].filter((file) => duplicated.has(file)).map(needsExtractionIssue);
}

// The composite sensor: a real multi sensor that reads oversized-file +
// duplicated-code from ctx.deps and emits needs-extraction for any file that has
// both (docs/architecture.md "Combinations"). All combination logic stays here
// in the sensor layer; the mapper never sees it.
export function needsExtractionSensor(): Sensor {
  return {
    id: SMELL,
    produces: [SMELL],
    dependsOn: [...INPUT_SMELLS],
    run: (ctx) => Promise.resolve(combine(ctx.deps)),
  };
}

// `replace` mode: once needs-extraction fires for a file, drop that file's two
// input smells so only the consolidated finding shows. Default (augment) keeps
// all three. Operates on the merged bag before the mapper runs.
export function applyReplaceMode(issues: Issue[], replace: boolean): Issue[] {
  if (!replace) return issues;
  const extracted = filesWith(issues, SMELL);
  const suppressed = new Set<string>(INPUT_SMELLS);
  return issues.filter((issue) => !(suppressed.has(issue.smell) && extracted.has(fileOf(issue) ?? '')));
}
