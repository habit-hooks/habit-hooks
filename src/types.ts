export type Severity = 'enforced' | 'suggested';
export type RuleSource = 'eslint' | 'jscpd' | 'custom';

export interface Rule {
  id: string;
  source: RuleSource;
  sourceRuleId?: string;
  severity: Severity;
  changedFilesOnly: boolean;
  title: string;
  description: string;
  eslintOptions?: unknown;
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
  run(files: string[], rules: Rule[]): Promise<Violation[]>;
}
