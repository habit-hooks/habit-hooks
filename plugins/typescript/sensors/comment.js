const { Project, SyntaxKind } = require("ts-morph");

const MAX_SINGLE_LINE_CHARS = 10;
const MAX_BLOCK_CHARS = 15;

function isExempt(text) {
  return text.includes("eslint-disable");
}

function isReportableSingle(text) {
  return (
    text.startsWith("//") && !isExempt(text) && text.length >= MAX_SINGLE_LINE_CHARS
  );
}

function isReportableBlock(text) {
  return (
    text.startsWith("/*") && !isExempt(text) && text.length >= MAX_BLOCK_CHARS
  );
}

function truncate(text) {
  const collapsed = text.replace(/\s+/g, " ").trim();
  return collapsed.length > 50 ? `${collapsed.slice(0, 50)}...` : collapsed;
}

function blockKind(text) {
  return text.startsWith("/**") ? "JSDoc" : "block";
}

function issue(file, comment, kind) {
  return {
    key: file,
    details: {
      file,
      line: comment.getStartLineNumber(),
      message: `${kind}-line comment: "${truncate(comment.getText())}"`,
      source: "comment:non-essential",
    },
  };
}

function commentsInFile(source) {
  const file = source.getFilePath();
  const singles = source
    .getDescendantsOfKind(SyntaxKind.SingleLineCommentTrivia)
    .filter((node) => isReportableSingle(node.getText().trim()))
    .map((node) => issue(file, node, "single"));
  const blocks = source
    .getDescendantsOfKind(SyntaxKind.MultiLineCommentTrivia)
    .filter((node) => isReportableBlock(node.getText().trim()))
    .map((node) => issue(file, node, blockKind(node.getText().trim())));
  const docs = source
    .getDescendantsOfKind(SyntaxKind.JSDoc)
    .filter((node) => isReportableBlock(node.getText().trim()))
    .map((node) => issue(file, node, "JSDoc"));
  return [...singles, ...blocks, ...docs];
}

function findings(files) {
  const project = new Project({ skipAddingFilesFromTsConfig: true });
  project.addSourceFilesAtPaths(files);
  const issues = project.getSourceFiles().flatMap(commentsInFile);
  if (issues.length === 0) return [];
  return [{ smell: "non-essential-comment", details: {}, issues }];
}

function main() {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    process.stdout.write("[]");
    return 0;
  }
  process.stdout.write(JSON.stringify(findings(files)));
  return 0;
}

process.exit(main());
