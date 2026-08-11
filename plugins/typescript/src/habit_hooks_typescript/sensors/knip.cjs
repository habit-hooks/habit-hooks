const { spawnSync } = require("node:child_process");
const { parseArgs } = require("node:util");
const fs = require("node:fs");
const path = require("node:path");

// The knip issue keys this plugin coaches, and the canonical smell each maps to.
// A sensor emits smells from OUR vocabulary, so translating knip's key set is
// this file's job: a key absent from this map is dropped here rather than
// forwarded under knip's own name, where it would have no guide, no catalogue
// severity and nothing a reader could act on (#111). Dropped today:
// `binaries`, `duplicates`, `catalog` — plus `unlisted` and `unresolved`, which
// name real defects and are waiting on smells of their own (#124).
const SMELL_BY_KEY = {
  files: "unused-file",
  exports: "unused-export",
  types: "unused-export",
  nsExports: "unused-export",
  nsTypes: "unused-export",
  dependencies: "unused-dependency",
  devDependencies: "unused-dependency",
  optionalPeerDependencies: "unused-dependency",
  classMembers: "unused-class-member",
  enumMembers: "unused-class-member",
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

// Every place knip 5 looks for a config (``constants.js``
// KNIP_CONFIG_LOCATIONS), resolved against the project alone — knip's
// ``findFile`` never walks up. Asking the question knip's own way is what stops
// a project being told its config was found when knip would not have found it.
const KNIP_CONFIG_LOCATIONS = [
  "knip.json",
  "knip.jsonc",
  ".knip.json",
  ".knip.jsonc",
  "knip.ts",
  "knip.js",
  "knip.config.ts",
  "knip.config.js",
];

// knip merges a ``knip`` key in the manifest whether or not a config file is
// found, so a project carrying only that has still stated its preferences.
const MANIFEST = "package.json";

// The config this plugin ships, beside the sensors directory it runs from.
const SHIPPED_CONFIG = path.join(__dirname, "..", "knip.json");

// A file the --production pass must never call dead, because that pass ignores
// test entries and would otherwise report every test file as unused.
const TEST_FILE = /(\.(test|spec)\.[cm]?[jt]sx?$)|(^|\/)tests?\//;

function isTestFile(file) {
  return TEST_FILE.test(file);
}

function runKnip(args) {
  return spawnSync("knip", ["--reporter", "json", ...args], {
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
    const smell = SMELL_BY_KEY[row.knipKey];
    if (!smell) continue;
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

// The knip config the project wrote, or null. Existence is the whole test: what
// a config says is knip's business, and a file knip would load is one this
// plugin must not speak over.
function projectConfig() {
  for (const name of KNIP_CONFIG_LOCATIONS) {
    const file = path.resolve(name);
    if (fs.existsSync(file)) return file;
  }
  const manifest = path.resolve(MANIFEST);
  return readJson(manifest)?.knip != null ? manifest : null;
}

// The config the project named through `[sensors.knip] args`, or null. Read with
// knip's own parser and knip's own option spelling (`config`, short `c`), so
// every form knip accepts — `--config x`, `--config=x`, `-c x`, `-cx` — is
// recognised as the answer it is. `strict: false` lets the rest of the args
// through unexamined: what they mean is knip's business, not ours. It also
// answers `true` for a flag with nothing after it, which names no file and so
// names no config: pass it on and let knip's own parser call it the mistake it
// is, rather than resolving a boolean and crashing before knip can.
function namedConfig(args) {
  const options = { config: { type: "string", short: "c" } };
  const named = parseArgs({ args, options, strict: false }).values.config;
  return typeof named === "string" ? path.resolve(named) : null;
}

// The config the run will actually use, and the args that make knip use it. A
// config the project named through the sensor's args is as much its own as one
// knip's discovery would have found, and it is already on the command line — so
// ours is not named beside it, which would only be us deciding between the two.
// Otherwise the project's own is left for discovery to find, and ours is named
// in its absence, and only if it is really there (a sensor vendored on its own
// arrives without it).
function configInForce(args) {
  const named = namedConfig(args);
  if (named !== null) return { file: named, args: [] };
  const own = projectConfig();
  if (own !== null) return { file: own, args: [] };
  if (!fs.existsSync(SHIPPED_CONFIG)) return { file: null, args: [] };
  return { file: SHIPPED_CONFIG, args: ["--config", SHIPPED_CONFIG] };
}

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch {
    return null;
  }
}

// The production markers are read from a plain-JSON knip config; a jsonc/ts/js
// config that JSON.parse cannot read falls back to a single (default) pass
// rather than risk mangling glob patterns like ``src/**/*`` while stripping
// comments.
function settingsIn(file) {
  if (file === null) return null;
  const parsed = readJson(file);
  if (parsed === null) return null;
  return path.basename(file) === MANIFEST ? (parsed.knip ?? null) : parsed;
}

function marksProduction(patterns) {
  return (
    Array.isArray(patterns) &&
    patterns.some((pattern) => typeof pattern === "string" && pattern.endsWith("!"))
  );
}

// A gated second pass only runs when the config marks production patterns with a
// trailing ``!`` on BOTH entry and project — the precondition without which knip
// --production analyses nothing. Detected here exactly as knip requires it, and
// read off the config that is in force: read it off any other and the pass stays
// off in precisely the case it exists for.
function configMarksProduction(file) {
  const settings = settingsIn(file);
  return (
    settings != null &&
    marksProduction(settings.entry) &&
    marksProduction(settings.project)
  );
}

function report(result) {
  return JSON.parse(result.stdout);
}

function main() {
  const args = process.argv.slice(2);
  const config = configInForce(args);
  const base = runKnip([...config.args, ...args]);
  if (knipCrashed(base)) {
    process.stderr.write(base.stderr || String(base.error));
    return 2;
  }
  let production = null;
  if (configMarksProduction(config.file)) {
    const pass = runKnip([...config.args, ...args, "--production"]);
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
