export interface RawIssue {
  smell: string;
  [key: string]: unknown;
}

export type GuideFn = (_issue: RawIssue) => unknown;
export type Guides = Record<string, GuideFn>;

export interface MapperRun {
  stdout: string;
  exitCode: 0 | 1;
}

interface SensorPayload {
  issues?: RawIssue[];
}

function parseIssues(json: string): RawIssue[] {
  const data = JSON.parse(json) as SensorPayload;
  return Array.isArray(data.issues) ? data.issues : [];
}

function coach(issue: RawIssue, guides: Guides): string | null {
  const guide = guides[issue.smell];
  if (guide === undefined) return `⚠️ No guide for smell: ${issue.smell}`;
  const prompt = guide(issue);
  return typeof prompt === 'string' && prompt.length > 0 ? `❌ ${prompt}` : null;
}

export function runMapper(sensorJson: string, guides: Guides): MapperRun {
  const lines = parseIssues(sensorJson)
    .map((issue) => coach(issue, guides))
    .filter((line): line is string => line !== null);
  const stdout = lines.length > 0 ? `${lines.join('\n')}\n` : '';
  return { stdout, exitCode: lines.length > 0 ? 1 : 0 };
}
