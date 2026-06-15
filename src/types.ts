export type Severity = 'enforced' | 'suggested';
export type RuleSource = 'eslint' | 'jscpd' | 'knip' | 'custom';

export interface CommentCheckThresholds {
  maxSingleLineChars: number;
  maxBlockChars: number;
}

export interface Rule {
  id: string;
  source: RuleSource;
  sourceRuleId?: string;
  severity: Severity;
  changedFilesOnly: boolean;
  title: string;
  description: string;
  include?: string[];
  exclude?: string[];
  fix?: string;
  guidance?: string;
  commentCheck?: CommentCheckThresholds;
}

export interface CoachingPrompt {
  id: string;
  title: string;
  description: string;
  severity: Severity;
  guidancePath: string;
}

export interface Violation {
  ruleId: string;
  file: string;
  line: number;
  column?: number;
  message: string;
  source?: string;
}

export interface CheckOutcome {
  violations: Violation[];
  stderr?: string[];
}

export interface Check {
  id: string;
  run(_files: string[], _rules: Rule[], _cwd?: string): Promise<Violation[] | CheckOutcome>;
}
