import { Project, SyntaxKind, type Node, type SourceFile } from 'ts-morph';
import type { Check, Rule, Violation } from '../types.js';

const RULE_ID = 'comment:non-essential';
const MIN_SINGLE = 10;
const MIN_BLOCK = 15;
const DEFAULT_EXECUTABLE_ANNOTATIONS: readonly string[] = [];

type CommentKind = 'single' | 'block' | 'JSDoc';

interface CommentCheckOptions {
  executableAnnotations?: readonly string[];
}

function getOptions(rules: Rule[]): CommentCheckOptions {
  const rule = rules.find((r) => r.id === RULE_ID);
  if (!rule) return {};
  const opts = rule.eslintOptions;
  if (!opts || typeof opts !== 'object' || Array.isArray(opts)) return {};
  return opts as CommentCheckOptions;
}

function isExcludedComment(text: string, annotations: readonly string[]): boolean {
  if (text.includes('eslint-disable')) return true;
  if (annotations.some((a) => text.includes(a))) return true;
  return false;
}

function isReportableSingle(text: string, annotations: readonly string[]): boolean {
  if (!text.startsWith('//')) return false;
  if (isExcludedComment(text, annotations)) return false;
  return text.length >= MIN_SINGLE;
}

function isReportableBlock(text: string, annotations: readonly string[]): boolean {
  if (!text.startsWith('/*')) return false;
  if (isExcludedComment(text, annotations)) return false;
  return text.length >= MIN_BLOCK;
}

function truncate(text: string): string {
  const collapsed = text.replace(/\s+/g, ' ').trim();
  return collapsed.length > 50 ? `${collapsed.substring(0, 50)}...` : collapsed;
}

function makeViolation(file: string, comment: Node, kind: CommentKind): Violation {
  return {
    ruleId: RULE_ID,
    file,
    line: comment.getStartLineNumber(),
    message: `${kind}-line comment: "${truncate(comment.getText())}"`,
  };
}

function classifyBlock(text: string): CommentKind {
  return text.startsWith('/**') ? 'JSDoc' : 'block';
}

function collectSingles(
  source: SourceFile,
  annotations: readonly string[],
  file: string,
): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.SingleLineCommentTrivia)
    .filter((c) => isReportableSingle(c.getText().trim(), annotations))
    .map((c) => makeViolation(file, c, 'single'));
}

function collectBlocks(
  source: SourceFile,
  annotations: readonly string[],
  file: string,
): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.MultiLineCommentTrivia)
    .filter((c) => isReportableBlock(c.getText().trim(), annotations))
    .map((c) => makeViolation(file, c, classifyBlock(c.getText().trim())));
}

function collectJsDoc(
  source: SourceFile,
  annotations: readonly string[],
  file: string,
): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.JSDoc)
    .filter((c) => isReportableBlock(c.getText().trim(), annotations))
    .map((c) => makeViolation(file, c, 'JSDoc'));
}

function findCommentsInFile(source: SourceFile, opts: CommentCheckOptions): Violation[] {
  const annotations = opts.executableAnnotations ?? DEFAULT_EXECUTABLE_ANNOTATIONS;
  const file = source.getFilePath();
  return [
    ...collectSingles(source, annotations, file),
    ...collectBlocks(source, annotations, file),
    ...collectJsDoc(source, annotations, file),
  ];
}

function buildProject(files: string[]): Project {
  const project = new Project({ skipAddingFilesFromTsConfig: true });
  project.addSourceFilesAtPaths(files);
  return project;
}

export const commentCheck: Check = {
  id: 'comment',
  async run(files, rules) {
    if (files.length === 0) return [];
    const opts = getOptions(rules);
    const project = buildProject(files);
    return project.getSourceFiles().flatMap((s) => findCommentsInFile(s, opts));
  },
};
