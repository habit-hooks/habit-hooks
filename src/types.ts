export type Severity = 'enforced' | 'suggested';
export type RuleSource = 'eslint' | 'jscpd' | 'knip' | 'custom';

export interface Rule {
  id: string;
  source: RuleSource;
  sourceRuleId?: string;
  severity: Severity;
  changedFilesOnly: boolean;
  title: string;
  description: string;
  sourceOptions?: unknown;
  include?: string[];
  exclude?: string[];
  guidance?: string;
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
}

export interface Check {
  id: string;
  run(files: string[], rules: Rule[], cwd?: string): Promise<Violation[]>;
}
