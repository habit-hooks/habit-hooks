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

// What `tool` printed for `args`, as `spawnSync` reports it.
function run(tool, args, options = {}) {
  const script = entryScript(tool, process.cwd());
  if (script === null) return notInstalled(tool);
  return spawnSync(process.execPath, [script, ...args], {
    encoding: "utf8",
    ...options,
  });
}

module.exports = { run };
