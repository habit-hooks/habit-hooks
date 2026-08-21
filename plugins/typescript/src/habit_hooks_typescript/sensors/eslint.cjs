const path = require("node:path");
const projectTool = require("./project_tool.cjs");

const ESLINT = "eslint";

// The eslint rule IDs this plugin coaches, and the canonical smell each maps to.
// A Map rather than an object literal so a lookup is safe however odd the key
// is: a plain object answers `SMELL_BY_RULE["constructor"]` with a function off
// Object.prototype, which would leave a finding with no smell at all. This is
// the JavaScript shape of the jq hazard #83 named — there, indexing the same map
// with a null rule ID aborted jq and took every eslint finding in the run with
// it. A Map has no prototype chain and answers `undefined` for anything absent.
const SMELL_BY_RULE = new Map(
  Object.entries({
    "max-lines-per-function": "oversized-function",
    "max-params": "too-many-parameters",
    "@typescript-eslint/max-params": "too-many-parameters",
    complexity: "high-complexity",
    "max-depth": "deep-nesting",
    "max-lines": "oversized-file",
    "no-unused-vars": "unused-variable",
    "@typescript-eslint/no-unused-vars": "unused-variable",
    eqeqeq: "loose-equality",
    "no-var": "var-declaration",
    "prefer-const": "non-const-binding",
    "no-duplicate-imports": "duplicate-import",
    "no-warning-comments": "warning-comment",
    "@typescript-eslint/no-explicit-any": "explicit-any",
    "@typescript-eslint/no-non-null-assertion": "non-null-assertion",
    "@typescript-eslint/no-inferrable-types": "redundant-type-annotation",
  }),
);

// A rule the map does not name is forwarded under its own ID. This is the
// deliberate exception to "a sensor emits vocabulary smells only" (#111): knip's
// issue keys are knip's, but an eslint rule ID comes from a config the project
// wrote, so forwarding it saves them running lint separately.

// A message eslint raises about a FILE rather than about a rule carries no rule
// ID — an ignored file in the scope, an `eslint-disable` directive nothing used
// — and is not a smell. A `fatal` message has no rule ID either and is exactly
// what this smell exists to report, so it is the one kept.
const PARSE_ERROR = "parse-error";

// A smell about the FILE, whose guide lists files rather than lines
// (`includes/file_level_issues.md`). eslint still positions its message —
// `max-lines` reports at the first line past the limit — but that is where its
// counter tripped, not where the problem is, and carrying it is what stopped
// the same file being recognised as one observation when the generic
// `line-count` sensor reported the same smell about it (#140).
//
// `parse-error` is file-level too and is deliberately absent: its position is
// where parsing actually failed, and no other sensor reports it about a file
// eslint can read, so there is nothing to reconcile and real information to
// lose.
const FILE_LEVEL_SMELLS = new Set(["oversized-file"]);

// The config this plugin ships, beside the sensors directory it runs from.
const SHIPPED_CONFIG = path.join(__dirname, "..", "eslint.config.mjs");

// eslint's own words for the single failure that means "this project wrote no
// config", and the only handle its CLI offers on that question.
const NO_CONFIG_FOUND = "couldn't find an eslint.config";

// What the scope may hand this sensor that eslint has nothing to say about.
const LINTABLE = /\.(tsx?|jsx?|[cm]js)$/;

// Where the sensor's own arguments stop and the scoped files begin, in the argv
// `sensors/eslint.toml` spells. Read from the END: this one is the runner's, and
// a project's own `[sensors.eslint] args` may spell one too.
const FILES_FOLLOW = "--";

const UNSEPARATED_ARGV =
  "eslint sensor: its argv must spell '--' between the sensor's arguments and " +
  "the scoped files — see sensors/eslint.toml\n";

// Only eslint can say whether the project has a config, because its lookup runs
// from each linted FILE's directory (eslint 10 `lib/config/config-loader.js`) —
// a config below the directory habit-hooks was invoked in is eslint's answer
// while being invisible to any walk from there. So this matches nothing broader
// than that one failure: eslint exits non-zero for findings AND for breakage, so
// a fallback keyed on "it failed" would lend our config to a run that broke for
// the project's own reasons and then call itself complete. Should the wording
// ever change, a config-less project fails loudly rather than being mis-linted
// quietly, which is the direction to be wrong in.
function wantedAConfig(result) {
  return projectTool.broke(result) && (result.stderr || "").includes(NO_CONFIG_FOUND);
}

// `--no-warn-ignored` stops the commonest rule-less message being raised at all.
function runEslint(args) {
  return projectTool.run(ESLINT, ["-f", "json", "--no-warn-ignored", ...args]);
}

// The bare run names no config, so eslint answers from wherever its own lookup
// reaches. `args` are the project's `[sensors.eslint] args` and go into it: a
// project whose config sits where that lookup cannot reach it says so with
// `--config`, and passing it here is what makes this run succeed — so the
// fallback is never entered and ours is never named. They go into the fallback
// too, because they are the project's whichever config is in force, and last,
// because eslint takes the last `--config` it is given.
function lint(args, files) {
  const bare = runEslint([...args, ...files]);
  if (!wantedAConfig(bare)) return bare;
  return runEslint(["--config", SHIPPED_CONFIG, ...args, ...files]);
}

function smellOf(message) {
  if (message.fatal) return PARSE_ERROR;
  return SMELL_BY_RULE.get(message.ruleId) ?? message.ruleId;
}

function isReportable(message) {
  return message.ruleId != null || message.fatal;
}

function reported(file, message) {
  const smell = smellOf(message);
  // The keys stay whichever way, null where there is no position to give: every
  // eslint issue's details carry them, and a key that disappears reads
  // downstream as a different shape rather than as a missing value.
  const positioned = !FILE_LEVEL_SMELLS.has(smell);
  return {
    smell,
    key: file,
    details: {
      file,
      line: positioned ? (message.line ?? null) : null,
      column: positioned ? (message.column ?? null) : null,
      message: message.message,
      source: `eslint:${message.ruleId ?? "fatal"}`,
    },
  };
}

function bySmellName(one, other) {
  if (one.smell === other.smell) return 0;
  return one.smell < other.smell ? -1 : 1;
}

// One finding per smell, each keeping its messages in the order eslint reported
// them, and the findings themselves in smell order.
function grouped(reports) {
  const bySmell = new Map();
  for (const report of reports) {
    const finding = bySmell.get(report.smell) ?? {
      smell: report.smell,
      details: {},
      issues: [],
    };
    finding.issues.push({ key: report.key, details: report.details });
    bySmell.set(report.smell, finding);
  }
  return [...bySmell.values()].sort(bySmellName);
}

function findings(report) {
  return grouped(
    report.flatMap((file) =>
      file.messages
        .filter(isReportable)
        .map((message) => reported(file.filePath, message)),
    ),
  );
}

function emit(payload) {
  process.stdout.write(JSON.stringify(payload));
  return 0;
}

function refuse(complaint) {
  process.stderr.write(complaint);
  return 2;
}

function main() {
  const argv = process.argv.slice(2);
  const boundary = argv.lastIndexOf(FILES_FOLLOW);
  if (boundary < 0) return refuse(UNSEPARATED_ARGV);
  const files = argv.slice(boundary + 1).filter((file) => LINTABLE.test(file));
  if (files.length === 0) return emit([]);
  const result = lint(argv.slice(0, boundary), files);
  if (projectTool.broke(result) || result.stdout.trim() === "") {
    return refuse(projectTool.complaint(ESLINT, result));
  }
  return emit(findings(JSON.parse(result.stdout)));
}

// Not process.exit(): stdout is a pipe under the runner and writes to it are
// async, so exiting here truncates the payload at the pipe buffer.
process.exitCode = main();
