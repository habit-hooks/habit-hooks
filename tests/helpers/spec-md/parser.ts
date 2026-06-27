export interface CommandUnit {
  command: string;
  expectedStdout: string | null;
  expectedExit: number;
}

export interface Example {
  title: string;
  units: CommandUnit[];
}

interface Fence {
  info: string;
  body: string;
}

const FENCE_START = /^```(.*)$/;
const OUTCOME_SUCCESS = '**Expected outcome:** Success';
const OUTCOME_FAILS = /^\*\*Expected outcome:\*\* Fails with (\d+)$/;

function isHeading(line: string, maxLevel: number): boolean {
  const match = /^(#{1,6})\s/.exec(line);
  return match !== null && match[1].length <= maxLevel;
}

function exampleHeadingTitle(line: string): string | null {
  const match = /^###\s+(.*)$/.exec(line);
  return match === null ? null : match[1].trim();
}

function splitExamples(lines: string[]): { title: string; body: string[] }[] {
  const examples: { title: string; body: string[] }[] = [];
  let current: { title: string; body: string[] } | null = null;
  let inFence = false;
  for (const line of lines) {
    if (FENCE_START.exec(line) !== null) inFence = !inFence;
    const title = inFence ? null : exampleHeadingTitle(line);
    if (title !== null) {
      current = { title, body: [] };
      examples.push(current);
    } else if (!inFence && current !== null && isHeading(line, 3)) {
      current = null;
    } else if (current !== null) {
      current.body.push(line);
    }
  }
  return examples;
}

function readFence(lines: string[], start: number): { fence: Fence; next: number } | null {
  const openMatch = FENCE_START.exec(lines[start]);
  if (openMatch === null) return null;
  const info = openMatch[1].trim();
  const body: string[] = [];
  let i = start + 1;
  while (i < lines.length && FENCE_START.exec(lines[i]) === null) {
    body.push(lines[i]);
    i += 1;
  }
  return { fence: { info, body: body.join('\n') }, next: i + 1 };
}

function readOutcome(lines: string[], from: number): { exit: number; consumed: number } {
  for (let i = from; i < lines.length; i += 1) {
    const line = lines[i].trim();
    if (FENCE_START.exec(lines[i]) !== null) break;
    if (line === OUTCOME_SUCCESS) return { exit: 0, consumed: i + 1 };
    const fails = OUTCOME_FAILS.exec(line);
    if (fails !== null) return { exit: Number(fails[1]), consumed: i + 1 };
  }
  return { exit: 0, consumed: from };
}

function readOptionalStdout(lines: string[], from: number): { stdout: string | null; next: number } {
  for (let i = from; i < lines.length; i += 1) {
    if (lines[i].trim() === '') continue;
    const fence = readFence(lines, i);
    if (fence !== null && fence.fence.info === 'text') {
      return { stdout: fence.fence.body, next: fence.next };
    }
    break;
  }
  return { stdout: null, next: from };
}

function nextBashFence(lines: string[], from: number): { fence: Fence; start: number; next: number } | null {
  for (let i = from; i < lines.length; i += 1) {
    if (lines[i].trim() === '') continue;
    const fence = readFence(lines, i);
    if (fence === null) continue;
    if (fence.fence.info === 'bash') return { fence: fence.fence, start: i, next: fence.next };
  }
  return null;
}

function parseUnits(body: string[]): CommandUnit[] {
  const units: CommandUnit[] = [];
  let cursor = 0;
  while (cursor < body.length) {
    const bash = nextBashFence(body, cursor);
    if (bash === null) break;
    const stdout = readOptionalStdout(body, bash.next);
    const outcome = readOutcome(body, stdout.next);
    units.push({ command: bash.fence.body, expectedStdout: stdout.stdout, expectedExit: outcome.exit });
    cursor = Math.max(outcome.consumed, stdout.next);
  }
  return units;
}

export function parseSpec(markdown: string): Example[] {
  const lines = markdown.split('\n');
  return splitExamples(lines).map(({ title, body }) => ({ title, units: parseUnits(body) }));
}
