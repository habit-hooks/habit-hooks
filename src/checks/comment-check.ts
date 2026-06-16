import { Project, SyntaxKind, type Node, type SourceFile } from 'ts-morph';
import { COMMENT_SMELL } from '../config/tool-smells.js';
import type { Check, CommentCheckThresholds, Rule, Violation } from '../types.js';

export const DEFAULT_COMMENT_CHECK_THRESHOLDS: CommentCheckThresholds = {
  maxSingleLineChars: 10,
  maxBlockChars: 15,
};

type CommentKind = 'single' | 'block' | 'JSDoc';

function isExcludedComment(text: string): boolean {
  return text.includes('eslint-disable');
}

function isReportableSingle(text: string, thresholds: CommentCheckThresholds): boolean {
  if (!text.startsWith('//')) return false;
  if (isExcludedComment(text)) return false;
  return text.length >= thresholds.maxSingleLineChars;
}

function isReportableBlock(text: string, thresholds: CommentCheckThresholds): boolean {
  if (!text.startsWith('/*')) return false;
  if (isExcludedComment(text)) return false;
  return text.length >= thresholds.maxBlockChars;
}

function truncate(text: string): string {
  const collapsed = text.replace(/\s+/g, ' ').trim();
  return collapsed.length > 50 ? `${collapsed.substring(0, 50)}...` : collapsed;
}

function makeViolation(file: string, comment: Node, kind: CommentKind): Violation {
  return {
    ruleId: COMMENT_SMELL,
    source: 'comment:non-essential',
    file,
    line: comment.getStartLineNumber(),
    message: `${kind}-line comment: "${truncate(comment.getText())}"`,
  };
}

function classifyBlock(text: string): CommentKind {
  return text.startsWith('/**') ? 'JSDoc' : 'block';
}

function collectSingles(source: SourceFile, file: string, thresholds: CommentCheckThresholds): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.SingleLineCommentTrivia)
    .filter((c) => isReportableSingle(c.getText().trim(), thresholds))
    .map((c) => makeViolation(file, c, 'single'));
}

function collectBlocks(source: SourceFile, file: string, thresholds: CommentCheckThresholds): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.MultiLineCommentTrivia)
    .filter((c) => isReportableBlock(c.getText().trim(), thresholds))
    .map((c) => makeViolation(file, c, classifyBlock(c.getText().trim())));
}

function collectJsDoc(source: SourceFile, file: string, thresholds: CommentCheckThresholds): Violation[] {
  return source
    .getDescendantsOfKind(SyntaxKind.JSDoc)
    .filter((c) => isReportableBlock(c.getText().trim(), thresholds))
    .map((c) => makeViolation(file, c, 'JSDoc'));
}

function findCommentsInFile(source: SourceFile, thresholds: CommentCheckThresholds): Violation[] {
  const file = source.getFilePath();
  return [
    ...collectSingles(source, file, thresholds),
    ...collectBlocks(source, file, thresholds),
    ...collectJsDoc(source, file, thresholds),
  ];
}

function buildProject(files: string[]): Project {
  const project = new Project({ skipAddingFilesFromTsConfig: true });
  project.addSourceFilesAtPaths(files);
  return project;
}

function resolveThresholds(rules: Rule[]): CommentCheckThresholds {
  const rule = rules.find((r) => r.id === COMMENT_SMELL);
  return rule?.commentCheck ?? DEFAULT_COMMENT_CHECK_THRESHOLDS;
}

export const commentCheck: Check = {
  id: 'comment',
  async run(files, rules) {
    if (files.length === 0) return [];
    const thresholds = resolveThresholds(rules);
    const project = buildProject(files);
    return project.getSourceFiles().flatMap((s) => findCommentsInFile(s, thresholds));
  },
};
