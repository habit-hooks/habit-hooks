import { createRequire } from 'node:module';
import type { Check, Rule, Violation } from '../types.js';

interface JscpdModule {
  detectClones(opts: Record<string, unknown>): Promise<Clone[]>;
}

const require = createRequire(import.meta.url);
const jscpd = require('jscpd') as JscpdModule;

const RULE_ID = 'jscpd:duplication';
const DEFAULT_MIN_TOKENS = 50;
const DEFAULT_MIN_LINES = 5;

interface JscpdOptions {
  minTokens?: number;
  minLines?: number;
}

interface CloneLocation {
  sourceId: string;
  start: { line: number };
  end: { line: number };
}

interface Clone {
  duplicationA: CloneLocation;
  duplicationB: CloneLocation;
}

function getOptions(rules: Rule[]): JscpdOptions {
  const rule = rules.find((r) => r.id === RULE_ID);
  const opts = rule?.eslintOptions;
  if (!opts || typeof opts !== 'object' || Array.isArray(opts)) return {};
  return opts as JscpdOptions;
}

function describe(location: CloneLocation): string {
  return `${location.sourceId}:${location.start.line}-${location.end.line}`;
}

function makeViolation(self: CloneLocation, partner: CloneLocation): Violation {
  return {
    ruleId: RULE_ID,
    file: self.sourceId,
    line: self.start.line,
    message: `duplicates ${describe(partner)}`,
  };
}

function cloneToViolations(clone: Clone, allowed: Set<string>): Violation[] {
  const aAllowed = allowed.has(clone.duplicationA.sourceId);
  const bAllowed = allowed.has(clone.duplicationB.sourceId);
  const violations: Violation[] = [];
  if (aAllowed) violations.push(makeViolation(clone.duplicationA, clone.duplicationB));
  if (bAllowed) violations.push(makeViolation(clone.duplicationB, clone.duplicationA));
  return violations;
}

async function runDetector(files: string[], opts: JscpdOptions): Promise<Clone[]> {
  return jscpd.detectClones({
    path: files,
    minTokens: opts.minTokens ?? DEFAULT_MIN_TOKENS,
    minLines: opts.minLines ?? DEFAULT_MIN_LINES,
    silent: true,
    noTips: true,
    reporters: [],
    gitignore: false,
  });
}

export const jscpdCheck: Check = {
  id: 'jscpd',
  async run(files, rules) {
    if (files.length === 0) return [];
    const opts = getOptions(rules);
    const clones = await runDetector(files, opts);
    const allowed = new Set(files);
    return clones.flatMap((c) => cloneToViolations(c, allowed));
  },
};
