const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

// The knip issue keys this plugin coaches, and the canonical smell each maps to.
// Everything else knip reports (types, nsExports, duplicates, a future key, …)
// is surfaced under its own key as an uncoached smell rather than dropped — the
// same pass-through the eslint sensor gives an unmapped rule ID.
const SMELL_BY_KEY = {
  files: "unused-file",
  exports: "unused-export",
  dependencies: "unused-dependency",
  devDependencies: "unused-dependency",
  optionalPeerDependencies: "unused-dependency",
  classMembers: "unused-class-member",
};

// Test-only dead code — code the --production pass finds unused once test
// references are ignored — is a smell of its own: the fix is to delete the code
// AND the test, not just the code, so it must not be merged into unused-file /
// unused-export where that distinction (and its coaching) is lost.
const PRODUCTION_SMELL = "test-only-dead-code";

// The dead-code keys the --production pass is allowed to contribute. Its
// dependency findings are re-reported noise — the default pass already owns
// those — so only genuine dead code crosses over.
const DEAD_CODE_KEYS = new Set([
  "files",
  "exports",
  "types",
  "nsExports",
  "nsTypes",
  "classMembers",
  "enumMembers",
]);

// The production markers are read from a plain-JSON knip config; a jsonc/ts/js
// config that JSON.parse cannot read falls back to a single (default) pass
// rather than risk mangling glob patterns like ``src/**/*`` while stripping
// comments.
const JSON_CONFIG_FILES = ["knip.json", ".knip.json"];

// A file the --production pass must never call dead, because that pass ignores
// test entries and would otherwise report every test file as unused.
const TEST_FILE = /(\.(test|spec)\.[cm]?[jt]sx?$)|(^|\/)tests?\//;

function isTestFile(file) {
  return TEST_FILE.test(file);
}

function runKnip(extraArgs) {
  return spawnSync("knip", ["--reporter", "json", ...extraArgs], {
    encoding: "utf8",
    maxBuffer: 64 * 1024 * 1024,
  });
}

function knipCrashed(result) {
  return result.error != null || result.status === null || result.status > 1;
}

// knip 5's JSON emits per-file arrays for most issue types but object maps for
// classMembers/enumMembers ({ parentSymbol: [occurrence, …] }) and arrays of
// arrays for duplicates. Flatten every shape to a plain occurrence list so a
// map never reaches ``.map`` (which threw and crashed the whole sensor).
function occurrences(value) {
  if (Array.isArray(value)) {
    return value.flatMap((item) => (Array.isArray(item) ? item : [item]));
  }
  if (value && typeof value === "object") {
    return Object.values(value).flat();
  }
  return [];
}

// Every occurrence knip reported, tagged with the knip key that produced it and
// the file it lives in. Unused files come from the top-level ``files`` array —
// knip never puts them in an issue row — so they are read there, not from a key.
function rawOccurrences(report) {
  const rows = (report.files || []).map((file) => ({ knipKey: "files", file, name: file }));
  for (const issue of report.issues || []) {
    for (const [knipKey, value] of Object.entries(issue)) {
      if (knipKey === "file" || knipKey === "owners") continue;
      for (const occurrence of occurrences(value)) {
        rows.push({
          knipKey,
          file: issue.file,
          name: occurrence.name,
          line: occurrence.line,
          col: occurrence.col,
        });
      }
    }
  }
  return rows;
}

function signature(row) {
  return `${row.knipKey}\n${row.file}\n${row.name ?? ""}`;
}

function issueFrom(row, source) {
  const details = { file: row.file, source };
  if (row.name !== undefined) details.name = row.name;
  if (row.line !== undefined) details.line = row.line;
  if (row.col !== undefined) details.col = row.col;
  return { key: row.name ?? row.file, details };
}

function add(grouped, smell, issue) {
  const finding = grouped.get(smell) || { smell, details: {}, issues: [] };
  finding.issues.push(issue);
  grouped.set(smell, finding);
}

// The default pass is authoritative for every issue type; the --production pass
// contributes only the dead code the default pass did not already name, and
// never a test file (which that pass reports spuriously by design).
function findings(defaultReport, productionReport) {
  const defaultRows = rawOccurrences(defaultReport);
  const grouped = new Map();
  for (const row of defaultRows) {
    const smell = SMELL_BY_KEY[row.knipKey] || row.knipKey;
    add(grouped, smell, issueFrom(row, `knip:${row.knipKey}`));
  }
  if (productionReport) {
    const alreadyDead = new Set(defaultRows.map(signature));
    for (const row of rawOccurrences(productionReport)) {
      if (!DEAD_CODE_KEYS.has(row.knipKey)) continue;
      if (alreadyDead.has(signature(row))) continue;
      if (isTestFile(row.file)) continue;
      add(grouped, PRODUCTION_SMELL, issueFrom(row, `knip:production:${row.knipKey}`));
    }
  }
  return [...grouped.values()];
}

function readJsonConfig() {
  for (const name of JSON_CONFIG_FILES) {
    const file = path.resolve(name);
    if (!fs.existsSync(file)) continue;
    try {
      return JSON.parse(fs.readFileSync(file, "utf8"));
    } catch {
      return null;
    }
  }
  const pkg = path.resolve("package.json");
  if (fs.existsSync(pkg)) {
    try {
      return JSON.parse(fs.readFileSync(pkg, "utf8")).knip ?? null;
    } catch {
      return null;
    }
  }
  return null;
}

function marksProduction(patterns) {
  return (
    Array.isArray(patterns) &&
    patterns.some((pattern) => typeof pattern === "string" && pattern.endsWith("!"))
  );
}

// A gated second pass only runs when the config marks production patterns with a
// trailing ``!`` on BOTH entry and project — the precondition without which knip
// --production analyses nothing. Detected here exactly as knip requires it.
function configMarksProduction() {
  const config = readJsonConfig();
  return (
    config != null && marksProduction(config.entry) && marksProduction(config.project)
  );
}

function report(result) {
  return JSON.parse(result.stdout);
}

function main() {
  const base = runKnip([]);
  if (knipCrashed(base)) {
    process.stderr.write(base.stderr || String(base.error));
    return 2;
  }
  let production = null;
  if (configMarksProduction()) {
    const pass = runKnip(["--production"]);
    if (knipCrashed(pass)) {
      process.stderr.write(pass.stderr || String(pass.error));
      return 2;
    }
    production = report(pass);
  }
  process.stdout.write(JSON.stringify(findings(report(base), production)));
  return 0;
}

// Not process.exit(): stdout is a pipe under the runner and writes to it are
// async, so exiting here truncates the payload at the pipe buffer.
process.exitCode = main();
