const { createRequire } = require("node:module");
const path = require("node:path");

const MISSING_TS_MORPH =
  "ts-morph is not installed in this project — npm install --save-dev ts-morph";

// Node resolves a bare `require` from THIS file upwards, and this file ships
// wherever habit-hooks is installed — for a consumer, a Python site-packages
// tree with no node_modules anywhere above it. ts-morph is the project's own
// dependency, the same place eslint and knip come from, so it is resolved from
// the project (as `eslint.config.mjs` resolves its parser and plugin).
function tsMorphFromProject() {
  return createRequire(path.join(process.cwd(), "comment.cjs"))("ts-morph");
}

function isAbsent(error) {
  return error.code === "MODULE_NOT_FOUND";
}

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

function commentsInFile(source, SyntaxKind) {
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

function findings(tsMorph, files) {
  const project = new tsMorph.Project({ skipAddingFilesFromTsConfig: true });
  project.addSourceFilesAtPaths(files);
  const issues = project
    .getSourceFiles()
    .flatMap((source) => commentsInFile(source, tsMorph.SyntaxKind));
  if (issues.length === 0) return [];
  return [{ smell: "non-essential-comment", details: {}, issues }];
}

function main() {
  const files = process.argv.slice(2);
  if (files.length === 0) {
    process.stdout.write("[]");
    return 0;
  }
  let tsMorph;
  try {
    tsMorph = tsMorphFromProject();
  } catch (error) {
    // The runner quotes a failed sensor's own stderr back, so a dependency
    // nobody installed reads as one actionable line rather than a stack trace.
    // Anything else — a ts-morph that is present and broken — keeps its own
    // error, which says more than a diagnosis that would be wrong.
    if (!isAbsent(error)) throw error;
    process.stderr.write(`${MISSING_TS_MORPH}\n`);
    return 1;
  }
  process.stdout.write(JSON.stringify(findings(tsMorph, files)));
  return 0;
}

// Not process.exit(): stdout is a pipe under the runner and writes to it are
// async, so exiting here truncates the payload at the pipe buffer.
process.exitCode = main();
