const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

// Running one of the project's own Node CLIs — eslint, knip — as a script handed
// to THIS node, never as the name a package manager put on PATH.
//
// Windows is what forces it. npm installs a CLI there as a `.cmd` shim, and Node
// has refused to spawn a `.cmd` or `.bat` since its CVE-2024-27980 mitigation
// (`IsWindowsBatchFile` in `src/spawn_sync.cc`, still there in Node 22): the
// spawn answers EINVAL unless `shell: true`. `shell: true` is not the way out —
// it hands our argv to `cmd.exe` to re-parse, and our arguments are filenames
// straight out of the checked-out branch, which this repo treats as hostile
// (`test_a_filename_can_never_execute_a_command`: a file added by a pull request
// from a fork would otherwise run its author's command on a reviewer's machine).
// Spawning the bare name is no better: `CreateProcess` appends only `.exe`, so
// the shim is not reached at all and an installed tool answers "command not
// found". A `.cmd` cannot be spawned and a bare name cannot find one, so the
// shim is never involved: the package's `bin` names a JavaScript file, and
// `process.execPath` is the node already running. One code path on both
// platforms — off Windows it spawns the very file `node_modules/.bin` links to.
//
// The tool is the project's own dependency, resolved from the project, as
// `comment.cjs` resolves ts-morph and the shipped `eslint.config.mjs` resolves
// its parser. A tool installed only globally is therefore no longer reached;
// that is the same contract this plugin already states (`npm install --save-dev
// eslint knip ts-morph`), and the shipped eslint config could never have used a
// global install anyway, since it resolves its plugins from the project.

const NODE_MODULES = "node_modules";
const MANIFEST = "package.json";

// What a shell exits with for a command it could not find. Paired with the
// phrase below it is what the runner recognises
// (`part_output.COMMAND_NOT_FOUND`), so a tool nobody installed — the one
// failure with an obvious fix — is told how to fix it rather than arriving as a
// module-resolution error the runner has never heard of (#114).
const COMMAND_NOT_FOUND_EXIT = 127;

// Where the package manager put the tool: the same `node_modules/<tool>` the
// `.bin` shim is created beside, found by the upward walk node itself does, so a
// monorepo's hoisted install and a pnpm symlink both answer. Asked of the
// filesystem rather than of `require.resolve`, which answers through the
// package's own `exports` — knip publishes neither `./package.json` nor its
// `bin/`, so the resolver cannot name the file the shim runs.
function toolManifest(tool, from) {
  let directory = from;
  for (;;) {
    const manifest = path.join(directory, NODE_MODULES, tool, MANIFEST);
    if (fs.existsSync(manifest)) return manifest;
    const parent = path.dirname(directory);
    if (parent === directory) return null;
    directory = parent;
  }
}

// The JavaScript file `node_modules/.bin/<tool>` runs, or null when this project
// has no such tool. `bin` is either a path (the package's own name) or a map of
// command name to path.
function entryScript(tool, from) {
  const manifest = toolManifest(tool, from);
  if (manifest === null) return null;
  const bin = JSON.parse(fs.readFileSync(manifest, "utf8")).bin;
  const entry = typeof bin === "string" ? bin : bin?.[tool];
  return entry == null ? null : path.resolve(path.dirname(manifest), entry);
}

// A tool nobody installed, answered in the shape a spawn answers in, so the
// caller has one kind of result to read rather than two.
function notInstalled(tool) {
  return {
    status: COMMAND_NOT_FOUND_EXIT,
    stdout: "",
    stderr: `${tool}: command not found\n`,
  };
}

// No ceiling on what a tool may print. `spawnSync` caps each captured stream at
// 1 MB unless told otherwise, and answers a tool that prints more with ENOBUFS:
// a truncated stdout, a `null` status, and an error the caller has to notice.
// Forty files of ordinary lint findings cross that, and the sensor that ran the
// tool is then left with nothing it can parse (#142).
//
// The 1 MB was never a decision, only the default nobody overrode. Every other
// place habit-hooks reads a tool's output is unbounded — the plugins' five
// Python helpers all capture with `subprocess.run`, the core drains its pipes
// with `Popen.communicate()`, and `comment.cjs` holds its whole ts-morph result
// in memory — so lifting it is what makes the Node helpers behave like the rest
// of the tool rather than a special case.
const NO_CEILING = Infinity;

// What `tool` printed for `args`, as `spawnSync` reports it. The spawn takes no
// options from the caller: there is one right answer to each of these for every
// tool this seam runs, and a caller free to override them is a caller free to
// put the 1 MB ceiling back, or to ask for a Buffer, which `complaint` would
// then read as a tool that said nothing at all.
function run(tool, args) {
  const script = entryScript(tool, process.cwd());
  if (script === null) return notInstalled(tool);
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
    maxBuffer: NO_CEILING,
  });
}

// The run produced no answer worth reading. Both tools this seam runs exit 1
// for "I found something to report" — the commonest successful run there is —
// so breakage starts above it. A `null` status is a run that never reached an
// exit at all: killed by a signal, or refused before it began, which sets
// `error` as well.
function broke(result) {
  return result.error != null || result.status === null || result.status > 1;
}

function spoke(output) {
  return typeof output === "string" && output.trim() !== "";
}

function howItEnded(result) {
  if (result.signal != null) return `killed by ${result.signal}`;
  return `exited ${result.status}`;
}

// Why the run is unusable, in words a reader can act on — never an empty
// string, which is the bug this whole seam exists to make impossible (#142),
// and never more than a sentence unless the tool itself wrote one.
//
// Only two things can be the complaint. The tool's own words, wherever it got
// any out, because a tool that diagnosed itself is the one thing a reader can
// act on; every tool this seam runs writes them to stderr. Otherwise this seam
// speaks for it, and then it must say WHICH tool — `spawnSync <path> ENOBUFS`
// names the node that was spawned, never the tool that failed. Blank stderr is
// not words: whitespace forwarded verbatim is the empty complaint again.
//
// What the tool half-printed to *stdout* is never either. It is a report cut
// off mid-write, not a diagnosis: an OOM-killed eslint hands back the first few
// megabytes of a JSON array, which says nothing about why it died and buries the
// one sentence that would. `sensors/diagnosis.py` bounds what any notice carries,
// so the cost is capped either way — but a reader would still be given a
// truncated report where a reason belongs.
function complaint(tool, result) {
  return said(tool, result, `${howItEnded(result)} without a word of its own`);
}

// The tool's own words if it got any out, and ours named for it if not.
function said(tool, result, ours) {
  if (spoke(result.stderr)) return result.stderr;
  if (result.error != null) return `${tool}: ${result.error.message}\n`;
  return `${tool}: ${ours}\n`;
}

// What to say when a run this seam calls FINE still left nothing to work with.
// A tool that exited 0 or 1 has reported, as far as the spawn can tell, and
// only its caller can find out that what it printed is not readable.
//
// Windows is what makes that a real failure rather than a tidy-up. It has no
// signals: `process.kill` there is `TerminateProcess`, so a tool cut down
// mid-report leaves an ordinary exit 1 — the same code eslint and knip use for
// "I found something to report" — and its half-written array then reaches
// `JSON.parse` as an unhandled `SyntaxError`. That is #142's own class one
// branch further along, and the reason it is answered here rather than in
// either caller.
//
// A tool that printed nothing at all gets the ordinary complaint: "without a
// word of its own" is true of it, and false of one that flushed half a
// megabyte before it died.
function unreadableOutput(tool, result) {
  if (!spoke(result.stdout)) return complaint(tool, result);
  const ours = `${howItEnded(result)}, and what it printed is not a report this sensor can read`;
  return said(tool, result, ours);
}

// The JSON a tool printed, or null when there is nothing there this sensor can
// read — empty, cut short, or not a string at all. `JSON.parse` throwing is the
// one failure a sensor must never let escape: the runner needs a sentence, and
// a stack trace is the non-answer this whole seam exists to stop.
function readJsonReport(stdout) {
  if (typeof stdout !== "string") return null;
  try {
    return JSON.parse(stdout);
  } catch {
    return null;
  }
}

module.exports = { run, broke, complaint, unreadableOutput, readJsonReport };
